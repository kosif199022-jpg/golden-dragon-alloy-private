// Black Dragon ↔ Chrome bridge. Long-polls the desktop app on 127.0.0.1 and runs the commands it sends.
// Paired with a token you paste in the popup; nothing runs until the app (on this same computer) sends a command.
const PORT = 47821;
let running = false;
let status = 'off';

const sleep = ms => new Promise(r => setTimeout(r, ms));
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
  const [r] = await chrome.scripting.executeScript({ target: { tabId }, func, args, world: 'ISOLATED' });
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
  return { url: location.href, title: document.title, text, elements: items };
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

// ---- command dispatcher ----
async function handle(cmd) {
  const p = cmd.params || {};
  switch (cmd.action) {
    case 'tabs': return (await chrome.tabs.query({})).map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active, window: t.windowId }));
    case 'open': { const t = await chrome.tabs.create({ url: p.url, active: true }); await waitLoaded(t.id); return { id: t.id }; }
    case 'navigate': { const t = await tabFor(p); await chrome.tabs.update(t.id, { url: p.url }); await sleep(300); await waitLoaded(t.id); return { id: t.id }; }
    case 'activate': { const t = await chrome.tabs.update(p.tab_id, { active: true }); await chrome.windows.update(t.windowId, { focused: true }); return { id: t.id }; }
    case 'close': await chrome.tabs.remove(p.tab_id); return { closed: p.tab_id };
    case 'back': { const t = await tabFor(p); await chrome.tabs.goBack(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'forward': { const t = await tabFor(p); await chrome.tabs.goForward(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'reload': { const t = await tabFor(p); await chrome.tabs.reload(t.id); await sleep(500); await waitLoaded(t.id); return { id: t.id }; }
    case 'read': { const t = await tabFor(p); return { tab: t.id, ...(await run(t.id, snapshot)) }; }
    case 'click': { const t = await tabFor(p); const r = await run(t.id, clickEl, [p.index ?? null, p.text || null]); await sleep(600); await waitLoaded(t.id, 8000);
      if (!r || !r.ok) throw new Error(r ? r.error : 'click failed'); return r; }
    case 'type': { const t = await tabFor(p); const r = await run(t.id, typeEl, [p.index ?? null, p.text || '', !!p.submit]); if (p.submit) { await sleep(800); await waitLoaded(t.id, 10000); }
      if (!r || !r.ok) throw new Error(r ? r.error : 'type failed'); return r; }
    case 'scroll': { const t = await tabFor(p); await run(t.id, a => window.scrollBy(0, a * window.innerHeight * 0.8), [p.amount || 1]); return { ok: true }; }
    case 'screenshot': { const t = await tabFor(p); if (!t.active) { await chrome.tabs.update(t.id, { active: true }); await sleep(300); }
      return { dataUrl: await chrome.tabs.captureVisibleTab(t.windowId, { format: 'jpeg', quality: 75 }), tab: t.id, url: t.url }; }
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
        const r = await fetch(`http://127.0.0.1:${PORT}/poll?t=${encodeURIComponent(token)}&v=1.0.0`);
        if (r.status === 403) { setStatus('bad-token'); await sleep(4000); continue; }
        cmd = await r.json(); setStatus('on');
      } catch (e) { setStatus('app-off'); await sleep(3000); continue; }
      if (!cmd || cmd.type !== 'cmd') continue;
      let res;
      try { setStatus('busy'); res = { id: cmd.id, ok: true, data: await handle(cmd) }; }
      catch (e) { res = { id: cmd.id, ok: false, error: String(e && e.message || e) }; }
      if (!['tabs', 'wait', 'close'].includes(cmd.action)) {
        try { const p = cmd.params || {}; const t = p.tab_id ? await chrome.tabs.get(p.tab_id) : await activeTab(); if (t) await showWin(t.windowId); } catch (e) {}
      }
      try { await fetch(`http://127.0.0.1:${PORT}/result?t=${encodeURIComponent(token)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(res) }); } catch (e) {}
      setStatus('on');
    }
  } finally { running = false; }
}

chrome.alarms.create('bd-keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => loop());
chrome.runtime.onStartup.addListener(() => loop());
chrome.runtime.onInstalled.addListener(() => loop());
chrome.storage.onChanged.addListener(c => { if (c.token) loop(); });
loop();
