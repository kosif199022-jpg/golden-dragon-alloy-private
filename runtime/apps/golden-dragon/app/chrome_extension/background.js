// Golden Dragon ↔ Chrome bridge. Long-polls the desktop app on 127.0.0.1 and runs the commands it sends.
// Paired with a token you paste in the popup; nothing runs until the app (on this same computer) sends a command.
const PORT = 47851;
const VER = '1.4.0';
const CMD_LIMIT = 45000;      // no single command may hold the loop longer than this
const MAX_PAR = 4;            // commands that may run at the same time
let inflight = 0;
let running = false;
let beatAt = 0;                // last time the loop made progress (watchdog)
let status = 'off';

const sleep = ms => new Promise(r => setTimeout(r, ms));
function withTimeout(pr, ms, what) {
  return Promise.race([pr, new Promise((_, rej) => setTimeout(() => rej(new Error(`${what} خد أكتر من ${ms / 1000} ثانية واتلغى`)), ms))]);
}
// pending awaits don't count as activity for an MV3 service worker: ping an extension API while busy
setInterval(() => { chrome.runtime.getPlatformInfo().catch(() => {}); }, 20000);
// a hidden offscreen page messages us every 20 s (offscreen.js), which keeps the worker awake even when idle
async function ensureOffscreen() {
  try {
    if (!chrome.offscreen || await chrome.offscreen.hasDocument()) return;
    await chrome.offscreen.createDocument({ url: 'offscreen.html', reasons: [chrome.offscreen.Reason.BLOBS],
      justification: 'Keep the Golden Dragon bridge awake while the desktop app is controlling Chrome' });
  } catch (e) {}
}
chrome.runtime.onMessage.addListener(m => { if (m && m.wbPing) loop(); });

// tabs the app opens go into one «التنين الذهبي» group, so the user's own tabs stay apart
let groupId = null;
async function addToGroup(tabId) {
  try {
    if (groupId != null) { try { await chrome.tabGroups.get(groupId); } catch (e) { groupId = null; } }
    groupId = await chrome.tabs.group(groupId != null ? { groupId, tabIds: [tabId] } : { tabIds: [tabId] });
    await chrome.tabGroups.update(groupId, { title: 'التنين الذهبي', color: 'blue' });
  } catch (e) {}
}

// a thin glowing frame on the page while it is being controlled (removed by the page itself after 4 s of quiet)
function markControlled() {
  let el = document.getElementById('__wb_frame');
  if (!el) {
    el = document.createElement('div'); el.id = '__wb_frame';
    el.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;border:3px solid #2f80ed;' +
      'box-shadow:inset 0 0 18px rgba(47,128,237,.55);border-radius:4px;transition:opacity .4s';
    (document.documentElement || document.body).appendChild(el);
  }
  el.style.opacity = '1'; clearTimeout(window.__wbFrameT);
  window.__wbFrameT = setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 450); }, 4000);
}
async function showControl(tabId) {
  try { await withTimeout(chrome.scripting.executeScript({ target: { tabId }, func: markControlled, injectImmediately: true }), 3000, 'frame'); } catch (e) {}
}
async function getToken() {
  let { token } = await chrome.storage.local.get('token');
  if (!token) {   // a copy made by the app ships config.json with the pairing code, so no pasting is needed
    try { const c = await (await fetch(chrome.runtime.getURL('config.json'))).json(); if (c.token) { token = c.token; await chrome.storage.local.set({ token }); } } catch (e) {}
  }
  return token || '';
}
const setStatus = s => { status = s; chrome.storage.local.set({ status: s, statusAt: Date.now() });
  chrome.action.setBadgeText({ text: s === 'on' ? '●' : s === 'busy' ? '…' : '' });
  chrome.action.setBadgeBackgroundColor({ color: s === 'on' ? '#2e7d4f' : '#a8842f' }); };

async function activeTab() {
  const [t] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return t;
}
// keep Chrome visible while it is being controlled: un-minimize its window and bring it to the front
async function showWin(windowId) {
  try {
    const w = await chrome.windows.get(windowId);
    await chrome.windows.update(windowId, w.state === 'minimized' ? { state: 'normal', focused: true } : { focused: true });
  } catch (e) {}
}
async function tabFor(p) { return p.tab_id ? await chrome.tabs.get(p.tab_id) : await activeTab(); }
function waitLoaded(tabId, ms = 20000) {
  return new Promise(res => {
    const t0 = Date.now();
    const tick = async () => {
      try { const t = await chrome.tabs.get(tabId); if (t.status === 'complete' || Date.now() - t0 > ms) return res(t); } catch (e) { return res(null); }
      setTimeout(tick, 250);
    };
    tick();
  });
}
async function run(tabId, func, args = []) {
  // injectImmediately: heavy pages (Facebook) stay 'loading' for a long time and document_idle may never come
  const [r] = await withTimeout(chrome.scripting.executeScript({ target: { tabId }, func, args, world: 'ISOLATED', injectImmediately: true }), 30000, 'تشغيل السكربت في الصفحة');
  return r ? r.result : null;
}

// ---- page-side helpers (serialized into the page) ----
function snapshot() {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const sel = 'a[href],button,input,textarea,select,[role=button],[role=link],[role=tab],[role=menuitem],[contenteditable=true],summary,label[for]';
  const items = []; let i = 0;
  document.querySelectorAll('[data-bd-idx]').forEach(e => e.removeAttribute('data-bd-idx'));
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    el.setAttribute('data-bd-idx', String(i));
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || el.name || '').trim().replace(/\s+/g, ' ').slice(0, 90);
    const kind = el.tagName.toLowerCase() + (el.type ? ':' + el.type : '');
    items.push(`[${i}] ${kind} ${label}${el.href ? ' → ' + el.href.slice(0, 120) : ''}`);
    if (++i >= 250) break;
  }
  const text = (document.body ? document.body.innerText : '').replace(/\n{3,}/g, '\n\n').slice(0, 30000);
  // media for downloading: big images, video posters/sources, and links that look like posts/reels/videos/photos
  const media = { images: [], videos: [], posts: [] }; const seen = new Set();
  const add = (arr, u, max) => { if (u && !u.startsWith('data:') && !u.startsWith('blob:') && !seen.has(u) && arr.length < max) { seen.add(u); arr.push(u); } };
  for (const im of document.images) { if ((im.naturalWidth || im.width) >= 250 && (im.naturalHeight || im.height) >= 180) add(media.images, im.currentSrc || im.src, 300); }
  for (const v of document.querySelectorAll('video')) { add(media.videos, v.currentSrc || v.src, 100); if (v.poster) add(media.images, v.poster, 300); }
  const postRe = /\/(posts|videos|reel|watch|photo|photos|permalink|story\.php|photo\.php)[\/?.]/;
  for (const a of document.querySelectorAll('a[href]')) { const h = a.href.split('__cft__')[0].replace(/[?&]$/, ''); if (postRe.test(h)) add(media.posts, h, 400); }
  // the app only prints `elements`, so media links ride at the top of that list (kept short so nothing gets clipped)
  const mlines = [`[page] scrollY=${Math.round(scrollY)} scrollH=${document.documentElement.scrollHeight} visibility=${document.visibilityState} ready=${document.readyState}`];
  media.images.slice(0, 40).forEach(u => mlines.push('[img] ' + u));
  media.videos.slice(0, 20).forEach(u => mlines.push('[video] ' + u));
  media.posts.slice(0, 120).forEach(u => mlines.push('[post] ' + u));
  return { url: location.href, title: document.title, text, elements: mlines.concat(items), media, scrollY: Math.round(scrollY), scrollH: document.documentElement.scrollHeight };
}
function clickEl(idx, text) {
  let el = idx != null ? document.querySelector(`[data-bd-idx="${idx}"]`) : null;
  if (!el && text) el = [...document.querySelectorAll('a,button,[role=button],input[type=submit],summary,label')].find(e => (e.innerText || e.value || '').trim().includes(text));
  if (!el) return { ok: false, error: 'العنصر مش موجود. اعمل read تاني.' };
  el.scrollIntoView({ block: 'center' }); el.focus(); el.click();
  return { ok: true, clicked: (el.innerText || el.value || el.tagName).trim().slice(0, 80) };
}
function typeEl(idx, value, submit) {
  const el = idx != null ? document.querySelector(`[data-bd-idx="${idx}"]`) : document.activeElement;
  if (!el) return { ok: false, error: 'الخانة مش موجودة. اعمل read تاني.' };
  el.scrollIntoView({ block: 'center' }); el.focus();
  if (el.isContentEditable) { el.textContent = value; }
  else { const proto = ({ TEXTAREA: HTMLTextAreaElement, SELECT: HTMLSelectElement }[el.tagName] || HTMLInputElement).prototype;
         const setter = Object.getOwnPropertyDescriptor(proto, 'value'); setter ? setter.set.call(el, value) : (el.value = value); }
  el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
  if (submit) { el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
    if (el.form) (el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit()); }
  return { ok: true };
}

// ---- background read: fetch a URL with the user's session and pull media/text out of the HTML, no tab, no focus ----
function parsePage(html, base) {
  const un = s => { try { return JSON.parse('"' + s + '"'); } catch (e) { return s.replace(/\\\//g, '/'); } };
  const lines = []; const t = (html.match(/<title[^>]*>([^<]*)<\/title>/i) || [])[1];
  if (t) lines.push('[title] ' + t.trim());
  const imgs = new Map();   // path -> {u,w,h}, keep the largest copy of every picture
  const keep = (u, w, h) => { const k = u.split('?')[0]; const o = imgs.get(k); if (!o || w * h > o.w * o.h) imgs.set(k, { u, w, h }); };
  for (const m of html.matchAll(/"uri":"(https:\\\/\\\/[^"]*?(?:scontent|fbcdn)[^"]*)","width":(\d+),"height":(\d+)/g)) keep(un(m[1]), +m[2], +m[3]);
  for (const m of html.matchAll(/"height":(\d+),"width":(\d+),"uri":"(https:\\\/\\\/[^"]*?(?:scontent|fbcdn)[^"]*)"/g)) keep(un(m[3]), +m[2], +m[1]);
  const og = (html.match(/<meta property="og:image" content="([^"]+)"/) || [])[1];
  if (og) keep(og.replace(/&amp;/g, '&'), 1, 1);
  [...imgs.values()].filter(x => x.w >= 400 || x.w === 1).sort((a, b) => b.w * b.h - a.w * a.h).slice(0, 60)
    .forEach(x => lines.push(`[img ${x.w}x${x.h}] ${x.u}`));
  const times = [...new Set([...html.matchAll(/"(?:creation_time|publish_time)":(\d{9,11})/g)].map(m => +m[1]))].slice(0, 8);
  times.forEach(s => lines.push('[time] ' + new Date(s * 1000).toISOString()));
  const texts = [...new Set([...html.matchAll(/"message":\{[^{}]*?"text":"((?:[^"\\]|\\.)*)"/g)].map(m => un(m[1])))].filter(x => x.length > 3).slice(0, 12);
  texts.forEach(x => lines.push('[text] ' + x.slice(0, 3000).replace(/\n/g, ' ⏎ ')));
  const links = new Set();
  for (const m of html.matchAll(/"url":"(https:\\\/\\\/www\.facebook\.com\\\/[^"]*?(?:permalink|posts|videos|photo|reel)[^"]*)"/g)) { links.add(un(m[1])); if (links.size >= 60) break; }
  links.forEach(u => lines.push('[post] ' + u));
  for (const m of html.matchAll(/"(?:playable_url_quality_hd|browser_native_hd_url|playable_url|browser_native_sd_url)":"(https:[^"]+)"/g)) { lines.push('[video] ' + un(m[1])); if (lines.length > 200) break; }
  return lines;
}
async function fetchRead(url) {
  const origin = new URL(url).origin;
  const [tab] = await chrome.tabs.query({ url: origin + '/*' });
  let html;
  if (tab) {   // same-origin fetch from inside an open tab of that site (its cookies, its headers); works in background tabs
    html = await run(tab.id, async u => { const r = await fetch(u, { credentials: 'include' }); return r.ok ? await r.text() : 'HTTP ' + r.status; }, [url]);
  } else {
    const r = await fetch(url, { credentials: 'include', signal: AbortSignal.timeout(25000) }); html = r.ok ? await r.text() : 'HTTP ' + r.status;
  }
  if (!html || html.length < 200) throw new Error('الصفحة رجعت فاضية: ' + String(html).slice(0, 80));
  return { tab: tab ? tab.id : null, url, title: 'background read', text: '', elements: [`[page] bytes=${html.length}`].concat(parsePage(html, url)) };
}

// ---- CDP layer (chrome.debugger): real input + rendering for tabs that are not on screen ----
// One attachment per tab, reused across commands and dropped after CDP_IDLE ms without use (so Chrome's
// "debugging this browser" bar goes away by itself). Dialogs are answered automatically so they can't freeze a command.
const CDP_IDLE = 20000;
const cdpTabs = new Map();          // tabId -> { idleT, dialogs: [] }
function cdpSend(tabId, method, params = {}) {
  return withTimeout(new Promise((res, rej) => chrome.debugger.sendCommand({ tabId }, method, params, r => {
    const e = chrome.runtime.lastError; e ? rej(new Error(e.message)) : res(r); })), 15000, 'CDP ' + method);
}
async function cdpAttach(tabId) {
  let s = cdpTabs.get(tabId);
  if (!s) {
    await withTimeout(new Promise((res, rej) => chrome.debugger.attach({ tabId }, '1.3', () => {
      const e = chrome.runtime.lastError; e ? rej(new Error('ماقدرتش أتحكم في التاب (DevTools مفتوح عليه؟): ' + e.message)) : res(); })), 8000, 'debugger attach');
    s = { idleT: null, dialogs: [] }; cdpTabs.set(tabId, s);
    await cdpSend(tabId, 'Page.enable').catch(() => {});
    // the page behaves as focused even when its window is behind other windows
    await cdpSend(tabId, 'Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {});
  }
  clearTimeout(s.idleT);
  s.idleT = setTimeout(() => cdpDetach(tabId), CDP_IDLE);
  return s;
}
function cdpDetach(tabId) {
  const s = cdpTabs.get(tabId); if (!s) return; clearTimeout(s.idleT); cdpTabs.delete(tabId);
  chrome.debugger.detach({ tabId }, () => void chrome.runtime.lastError);
}
chrome.debugger.onDetach.addListener(src => { const s = cdpTabs.get(src.tabId); if (s) { clearTimeout(s.idleT); cdpTabs.delete(src.tabId); } });
chrome.debugger.onEvent.addListener((src, method, params) => {
  if (method !== 'Page.javascriptDialogOpening') return;
  const s = cdpTabs.get(src.tabId);
  // alerts are acknowledged, confirm/prompt/beforeunload are CANCELLED (the safe answer), and the caller is told
  const accept = params.type === 'alert';
  if (s) s.dialogs.push(`${params.type}: ${String(params.message || '').slice(0, 200)} → ${accept ? 'OK' : 'إلغاء'}`);
  chrome.debugger.sendCommand({ tabId: src.tabId }, 'Page.handleJavaScriptDialog', { accept }, () => void chrome.runtime.lastError);
});
const takeDialogs = tabId => { const s = cdpTabs.get(tabId); if (!s || !s.dialogs.length) return undefined; const d = s.dialogs; s.dialogs = []; return d; };
async function onScreen(tab) {     // is this tab actually being painted right now?
  if (!tab.active) return false;
  try { const w = await chrome.windows.get(tab.windowId); return w.state !== 'minimized'; } catch (e) { return false; }
}
// a CDP screenshot makes Chrome produce a frame even for a hidden tab: lazy loaders / IntersectionObservers run on it
async function cdpPaint(tabId, quality = 60) {
  await cdpAttach(tabId);
  const r = await cdpSend(tabId, 'Page.captureScreenshot', { format: 'jpeg', quality, captureBeyondViewport: false });
  return r && r.data;
}
async function cdpClick(tabId, x, y) {
  await cdpAttach(tabId);
  const base = { x: Math.round(x), y: Math.round(y), modifiers: 0 };
  await cdpSend(tabId, 'Input.dispatchMouseEvent', { ...base, type: 'mouseMoved', button: 'none', buttons: 0 });
  await cdpSend(tabId, 'Input.dispatchMouseEvent', { ...base, type: 'mousePressed', button: 'left', buttons: 1, clickCount: 1 });
  await cdpSend(tabId, 'Input.dispatchMouseEvent', { ...base, type: 'mouseReleased', button: 'left', buttons: 0, clickCount: 1 });
}
async function cdpWheel(tabId, deltaY) {
  await cdpAttach(tabId);
  const m = await run(tabId, () => ({ w: innerWidth, h: innerHeight }));
  const step = Math.sign(deltaY) * Math.min(Math.abs(deltaY), (m.h || 800) * 0.9);
  for (let left = Math.abs(deltaY); left > 0; left -= Math.abs(step)) {
    await cdpSend(tabId, 'Input.dispatchMouseEvent', { type: 'mouseWheel', x: Math.round((m.w || 1200) / 2), y: Math.round((m.h || 800) / 2), deltaX: 0, deltaY: step });
    await sleep(120);
  }
}
// page-side: find the element, bring it into view only if it's off screen, and report its centre
function locateEl(idx, text) {
  let el = idx != null ? document.querySelector(`[data-bd-idx="${idx}"]`) : null;
  if (!el && text) el = [...document.querySelectorAll('a,button,[role=button],input[type=submit],summary,label,[role=link],[role=tab],[role=menuitem]')]
    .find(e => (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().includes(text));
  if (!el) return { ok: false, error: idx != null ? 'العنصر ده اتشال من الصفحة (stale). اعمل read تاني.' : 'العنصر مش موجود. اعمل read تاني.' };
  let r = el.getBoundingClientRect();
  if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) { el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' }); r = el.getBoundingClientRect(); }
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const hit = document.elementFromPoint(x, y);
  return { ok: true, x, y, covered: !!hit && hit !== el && !el.contains(hit) && !hit.contains(el),
           label: (el.innerText || el.value || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 80) };
}

// ---- command dispatcher ----
async function handle(cmd) {
  const p = cmd.params || {};
  switch (cmd.action) {
    case 'tabs': return (await chrome.tabs.query({})).map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active, window: t.windowId }));
    // background tab: never steals the user's focus
    case 'open': { const t = await chrome.tabs.create({ url: p.url, active: false }); await addToGroup(t.id); await waitLoaded(t.id); return { id: t.id }; }
    case 'navigate': { const t = await tabFor(p); await chrome.tabs.update(t.id, { url: p.url }); await sleep(300); await waitLoaded(t.id); return { id: t.id }; }
    // switches the tab inside its own window only; the window is not brought to the front
    case 'activate': { const t = await chrome.tabs.update(p.tab_id, { active: true }); return { id: t.id }; }
    case 'close': await chrome.tabs.remove(p.tab_id); return { closed: p.tab_id };
    case 'back': { const t = await tabFor(p); await chrome.tabs.goBack(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'forward': { const t = await tabFor(p); await chrome.tabs.goForward(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'reload': { const t = await tabFor(p); await chrome.tabs.reload(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'read': { if (p.url) return await fetchRead(p.url);      // read with a url = background read, no tab needed
      const t = await tabFor(p);
      if (!(await onScreen(t))) { try { await cdpPaint(t.id, 20); } catch (e) {} }   // hidden tab: draw it once first
      return { tab: t.id, ...(await run(t.id, snapshot)), dialogs: takeDialogs(t.id) }; }
    // trusted click through CDP (React sites like Facebook ignore el.click() sometimes); falls back to el.click()
    case 'click': { const t = await tabFor(p); const loc = await run(t.id, locateEl, [p.index ?? null, p.text || null]);
      if (!loc || !loc.ok) throw new Error(loc ? loc.error : 'click failed');
      let how = 'cdp';
      if (loc.covered) { const r = await run(t.id, clickEl, [p.index ?? null, p.text || null]); how = 'dom (العنصر كان متغطي)'; if (!r || !r.ok) throw new Error(r ? r.error : 'click failed'); }
      else { try { await cdpClick(t.id, loc.x, loc.y); } catch (e) { const r = await run(t.id, clickEl, [p.index ?? null, p.text || null]); how = 'dom'; if (!r || !r.ok) throw new Error(r ? r.error : 'click failed'); } }
      await sleep(600); await waitLoaded(t.id, 8000);
      return { ok: true, clicked: loc.label, via: how, dialogs: takeDialogs(t.id) }; }
    case 'type': { const t = await tabFor(p); const r = await run(t.id, typeEl, [p.index ?? null, p.text || '', !!p.submit]); if (p.submit) { await sleep(800); await waitLoaded(t.id, 10000); }
      if (!r || !r.ok) throw new Error(r ? r.error : 'type failed'); return r; }
    // visible tab: plain scroll. Hidden tab: real wheel events + a forced frame, so infinite feeds keep loading in the background
    case 'scroll': { const t = await tabFor(p); const amt = p.amount || 1;
      if (await onScreen(t)) { await run(t.id, a => window.scrollBy(0, a * window.innerHeight * 0.8), [amt]); return { ok: true }; }
      const h = (await run(t.id, () => innerHeight)) || 800;
      await cdpWheel(t.id, amt * h * 0.8); await cdpPaint(t.id, 20); await sleep(700); await cdpPaint(t.id, 20);
      const pos = await run(t.id, () => ({ y: Math.round(scrollY), h: document.documentElement.scrollHeight }));
      return { ok: true, via: 'cdp-background', scrollY: pos && pos.y, scrollH: pos && pos.h }; }
    // a tab that isn't on screen is photographed through CDP: no tab switch, no window focus
    case 'screenshot': { const t = await tabFor(p);
      if (await onScreen(t)) return { dataUrl: await chrome.tabs.captureVisibleTab(t.windowId, { format: 'jpeg', quality: 75 }), tab: t.id, url: t.url };
      const b64 = await cdpPaint(t.id, 75); return { dataUrl: 'data:image/jpeg;base64,' + b64, tab: t.id, url: t.url, via: 'cdp-background' }; }
    case 'wait': await sleep(Math.min(30000, (p.seconds || 1) * 1000)); return { ok: true };
    default: throw new Error('أمر مش معروف: ' + cmd.action);
  }
}

async function loop() {
  if (running) return; running = true;
  try {
    while (true) {
      await chrome.runtime.getPlatformInfo();           // an extension API call keeps the service worker alive
      const token = await getToken();
      if (!token) { setStatus('no-token'); await sleep(3000); continue; }
      let cmd;
      try {
        beatAt = Date.now();
        const r = await fetch(`http://127.0.0.1:${PORT}/poll?t=${encodeURIComponent(token)}&v=${VER}`, { signal: AbortSignal.timeout(35000) });
        if (r.status === 403) { setStatus('bad-token'); await sleep(4000); continue; }
        cmd = await r.json(); setStatus('on');
      } catch (e) { setStatus('app-off'); await sleep(3000); continue; }
      if (!cmd || cmd.type !== 'cmd') continue;
      // run it in parallel and go straight back to polling (up to MAX_PAR commands at once); Chrome is never focused
      inflight++; setStatus('busy'); beatAt = Date.now();
      (async () => {
        let res;
        try { res = { id: cmd.id, ok: true, data: await withTimeout(handle(cmd), CMD_LIMIT, 'الأمر ' + cmd.action) }; }
        catch (e) { res = { id: cmd.id, ok: false, error: String(e && e.message || e) }; }
        if (!['tabs', 'wait', 'close'].includes(cmd.action) && !(cmd.params || {}).url) {
          try { const p = cmd.params || {}; const t = p.tab_id ? await chrome.tabs.get(p.tab_id) : await activeTab();
                if (t && /^https?:/.test(t.url || '')) await showControl(t.id); } catch (e) {}
        }
        try { await fetch(`http://127.0.0.1:${PORT}/result?t=${encodeURIComponent(token)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(res), signal: AbortSignal.timeout(15000) }); } catch (e) {}
        inflight--; if (!inflight) setStatus('on');
      })();
      while (inflight >= MAX_PAR) await sleep(150);
    }
  } finally { running = false; }
}

ensureOffscreen();
chrome.alarms.create('bd-keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => { if (running && Date.now() - beatAt > CMD_LIMIT + 60000) running = false; loop(); });
chrome.runtime.onStartup.addListener(() => loop());
chrome.runtime.onInstalled.addListener(() => loop());
chrome.storage.onChanged.addListener(c => { if (c.token) loop(); });
loop();
