// «ستايل دعاء الترند»: the owner's trending dua reel (Facebook, 151K views, 1.7K shares, 2026-11-23) as a reusable style.
// Everything is from that reel's engine; only spec.json changes: {dur, header:{day,date,hday,hmonth,latin}, handle, lines:[[[word,t],...],...]}.
const W = 1080, H = 1920, FPS = 30;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const F_HEAD = 'ArefRuqaa', F_TEXT = 'NotoNaskh', F_LAT = 'Montserrat';
let CFG = null;

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eio = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eout = t => 1 - Math.pow(1 - t, 3);
function rnd(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

const cache = new Map();
function img(src) {
  if (cache.has(src)) return cache.get(src);
  const p = new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = src; });
  cache.set(src, p);
  if (cache.size > 400) { const k = cache.keys().next().value; cache.delete(k); }
  return p;
}

// ---------- lines (times from the voice, Whisper word stamps) ----------
let LINES = [];
const LEAD = 0.12;                                   // cut lands just before the voice
let CUTS = [];
const TR = 0.36;                                     // transition length, centred on the cut
const KINDS = ['spin', 'zoom', 'light', 'whip', 'spin', 'blurzoom', 'light', 'slideup', 'spin', 'zoom', 'light', 'whip', 'spin'];

// ---------- footage ----------
function grade(c, warm, alpha = 1) {
  c.save(); c.globalCompositeOperation = 'soft-light'; c.globalAlpha = .35 * alpha; c.fillStyle = warm; c.fillRect(0, 0, W, H); c.restore();
}
async function clipFrame(i, t) {
  const cl = CFG.clips[i];
  const local = t - (CUTS[i] - CFG.pad);                       // pad seconds extracted before the cut
  const n = clamp(Math.floor(local * FPS) + 1, 1, cl.frames);
  return img(`fx/c${String(i).padStart(2, '0')}/${String(n).padStart(4, '0')}.jpg`);
}
function clipEnd(i) { return i + 1 < CUTS.length ? CUTS[i + 1] : CFG.dur; }
async function drawClip(c, i, t) {
  const im = await clipFrame(i, t);
  c.save(); c.fillStyle = '#1b1410'; c.fillRect(0, 0, W, H);
  if (im) {
    const cl = CFG.clips[i];
    const p = seg(t, CUTS[i] - TR, clipEnd(i) + TR);
    const z = lerp(cl.z0 || 1.04, cl.z1 || 1.14, eio(p));
    const s = Math.max(W / im.width, H / im.height) * z;
    const w = im.width * s, h = im.height * s;
    const dx = (cl.px || 0) * (p - .5) * 60, dy = (cl.py || 0) * (p - .5) * 60;
    c.drawImage(im, (W - w) / 2 + dx, (H - h) / 2 + dy, w, h);
  }
  grade(c, CFG.clips[i].tint || '#ffb67a');
  c.restore();
}

// ---------- transitions (motion-matched: outgoing accelerates into the seam, incoming decelerates out) ----------
const off = () => { const k = document.createElement('canvas'); k.width = W; k.height = H; return k; };
const A = off(), B = off(), T = off();
function ghosts(dst, src, n, fn) { for (let i = 0; i < n; i++) { dst.save(); fn(dst, i / (n - 1) - .5); dst.globalAlpha = i === (n - 1) / 2 ? 1 : 1 / n * 1.6; dst.drawImage(src, 0, 0); dst.restore(); } }
function transition(c, kind, p) {   // p 0..1 across the seam
  const out = p < .5, k = out ? eio(p * 2) : 1 - eio((p - .5) * 2), src = out ? A : B; // k: 0 calm .. 1 peak
  const dir = out ? 1 : -1;
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
  if (kind === 'spin') {
    const ang = dir * k * 1.1, sc = 1 + k * .35;
    ghosts(c, src, 9, (g, d) => { g.translate(W / 2, H / 2); g.rotate(ang + d * k * .5); g.scale(sc, sc); g.translate(-W / 2, -H / 2); });
  } else if (kind === 'zoom' || kind === 'blurzoom') {
    const sc = out ? 1 + k * 1.6 : 1 + k * .9;
    ghosts(c, src, 9, (g, d) => { const s2 = sc * (1 + d * k * .25); g.translate(W / 2, H / 2); g.scale(s2, s2); g.translate(-W / 2, -H / 2); });
    if (kind === 'blurzoom') { c.save(); c.globalAlpha = k * .25; c.fillStyle = '#fff'; c.fillRect(0, 0, W, H); c.restore(); }
  } else if (kind === 'whip') {
    const x = dir * -k * W * .6;
    ghosts(c, src, 9, (g, d) => g.translate(x + d * k * 260, 0));
  } else if (kind === 'slideup') {
    const y = dir * -k * H * .45;
    ghosts(c, src, 9, (g, d) => g.translate(0, y + d * k * 300));
  } else { // light leak / glow cross
    c.drawImage(A, 0, 0); c.globalAlpha = eio(p); c.drawImage(B, 0, 0); c.globalAlpha = 1;
    const g = c.createRadialGradient(W * .7, H * .35, 50, W * .7, H * .35, 1300);
    const a = Math.sin(p * Math.PI);
    g.addColorStop(0, `rgba(255,236,200,${.95 * a})`); g.addColorStop(.4, `rgba(255,170,90,${.55 * a})`); g.addColorStop(1, 'rgba(255,120,60,0)');
    c.save(); c.globalCompositeOperation = 'screen'; c.fillStyle = g; c.fillRect(0, 0, W, H); c.restore();
  }
}

// ---------- overlays ----------
const DUST = (() => { const r = rnd(4), a = []; for (let i = 0; i < 40; i++) a.push({ x: r() * W, y: r() * H, s: 2 + r() * 7, v: 8 + r() * 30, ph: r() * 6 }); return a; })();
function dust(c, t) {
  c.save(); c.globalCompositeOperation = 'screen';
  for (const d of DUST) {
    const y = (d.y - d.v * t * 3 + H * 10) % H, x = d.x + Math.sin(t * .6 + d.ph) * 30, a = .25 + .25 * Math.sin(t * 2 + d.ph);
    const g = c.createRadialGradient(x, y, 0, x, y, d.s * 3); g.addColorStop(0, `rgba(255,230,190,${a})`); g.addColorStop(1, 'rgba(255,230,190,0)');
    c.fillStyle = g; c.fillRect(x - d.s * 3, y - d.s * 3, d.s * 6, d.s * 6);
  }
  c.restore();
}
function vignette(c) {
  let g = c.createLinearGradient(0, 0, 0, 520); g.addColorStop(0, 'rgba(10,6,4,.62)'); g.addColorStop(1, 'rgba(10,6,4,0)'); c.fillStyle = g; c.fillRect(0, 0, W, 520);
  g = c.createRadialGradient(W / 2, 1180, 150, W / 2, 1180, 760); g.addColorStop(0, 'rgba(8,5,3,.42)'); g.addColorStop(1, 'rgba(8,5,3,0)'); c.fillStyle = g; c.fillRect(0, 600, W, 1200);
  g = c.createRadialGradient(W / 2, H / 2, 700, W / 2, H / 2, 1350); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.35)'); c.fillStyle = g; c.fillRect(0, 0, W, H);
}
function text(c, s, x, y, font, fill, opts = {}) {
  c.save(); c.font = font; c.direction = opts.dir || 'rtl'; c.textAlign = opts.align || 'center'; c.textBaseline = 'alphabetic';
  if (opts.shadow) { c.shadowColor = opts.shadow; c.shadowBlur = opts.blur || 18; c.shadowOffsetY = opts.oy || 4; }
  if (opts.stroke) { c.lineJoin = 'round'; c.lineWidth = opts.sw || 8; c.strokeStyle = opts.stroke; c.strokeText(s, x, y); }
  c.fillStyle = fill; c.fillText(s, x, y); c.restore();
}
function ornament(c, x, y, w, a) {
  c.save(); c.globalAlpha = a; c.strokeStyle = '#e9c77b'; c.lineWidth = 3; c.lineCap = 'round';
  c.beginPath(); c.moveTo(x - w, y); c.lineTo(x - 22, y); c.moveTo(x + 22, y); c.lineTo(x + w, y); c.stroke();
  c.translate(x, y); c.rotate(Math.PI / 4); c.fillStyle = '#e9c77b'; c.fillRect(-9, -9, 18, 18); c.restore();
}
function header(c, t) {
  const k = eout(seg(t, .05, .8));
  c.save(); c.globalAlpha = k; c.translate(0, (1 - k) * -40);
  // right: day name (calligraphic) + Gregorian date
  const dayG = c.createLinearGradient(0, 120, 0, 250); dayG.addColorStop(0, '#fff8e8'); dayG.addColorStop(1, '#f1d394');
  text(c, CFG.header.day, 820, 232, `118px ${F_HEAD}`, dayG, { shadow: 'rgba(0,0,0,.55)', blur: 22 });
  text(c, CFG.header.date, 820, 312, `600 40px ${F_LAT}`, '#fff3dc', { dir: 'ltr', shadow: 'rgba(0,0,0,.6)', blur: 12 });
  // left: Hijri block
  const hg = c.createLinearGradient(80, 140, 420, 280); hg.addColorStop(0, '#7fe3d2'); hg.addColorStop(.5, '#e9c77b'); hg.addColorStop(1, '#7fe3d2');
  text(c, CFG.header.hday, 255, 150, `86px ${F_HEAD}`, '#e9c77b', { shadow: 'rgba(0,0,0,.6)', blur: 14 });
  text(c, CFG.header.hmonth, 255, 252, `96px ${F_HEAD}`, hg, { shadow: 'rgba(0,0,0,.55)', blur: 18 });
  text(c, CFG.header.latin, 255, 306, `600 25px ${F_LAT}`, '#f3e6c8', { dir: 'ltr', shadow: 'rgba(0,0,0,.6)', blur: 10 });
  ornament(c, W / 2, 360, 420, .85);
  c.restore();
}
function lineLayout(c, words, size) {
  c.font = `700 ${size}px ${F_TEXT}`;
  const sp = size * .32, ws = words.map(w => c.measureText(w[0]).width);
  const rows = [[]]; let cur = 0;
  words.forEach((w, i) => { const add = ws[i] + (rows[rows.length - 1].length ? sp : 0); if (cur + add > 940 && rows[rows.length - 1].length) { rows.push([]); cur = 0; } rows[rows.length - 1].push(i); cur += ws[i] + (rows[rows.length - 1].length > 1 ? sp : 0); });
  return { ws, sp, rows };
}
function duaLine(c, t, li) {
  const words = LINES[li]; if (!words) return;
  const start = CUTS[li], end = clipEnd(li);
  const fadeOut = 1 - seg(t, end - .14, end + .02);
  if (fadeOut <= 0) return;
  const size = 98, { ws, sp, rows } = lineLayout(c, words, size);
  const lh = size * 1.75, y0 = 1180 - (rows.length - 1) * lh / 2;
  rows.forEach((row, r) => {
    const total = row.reduce((a, i) => a + ws[i], 0) + sp * (row.length - 1);
    let x = W / 2 + total / 2;
    for (const i of row) {
      const wt = words[i][1] - .06, k = eout(seg(t, wt, wt + .3));
      const cx = x - ws[i] / 2, y = y0 + r * lh + (1 - k) * 26;
      if (k > 0) {
        c.save(); c.globalAlpha = k * fadeOut;
        // soft glow plate
        c.shadowColor = 'rgba(0,0,0,.85)'; c.shadowBlur = 30; c.shadowOffsetY = 5; c.fillStyle = '#fff'; c.font = `700 ${size}px ${F_TEXT}`; c.direction = 'rtl'; c.textAlign = 'center'; c.fillText(words[i][0], cx, y); c.shadowBlur = 10; c.shadowColor = 'rgba(0,0,0,.6)';
        c.font = `700 ${size}px ${F_TEXT}`; c.direction = 'rtl'; c.textAlign = 'center';
        c.fillStyle = '#ffffff'; c.fillText(words[i][0], cx, y);
        c.shadowColor = 'transparent';
        // the word being spoken gets a warm gold tint that settles back to white
        const hot = 1 - seg(t, words[i][1] + .15, words[i][1] + .7);
        if (hot > 0) { c.globalAlpha = k * fadeOut * hot * .9; c.fillStyle = '#ffd98a'; c.fillText(words[i][0], cx, y); }
        c.restore();
      }
      x -= ws[i] + sp;
    }
  });
  // small rule under the line
  const kk = eout(seg(t, start + .05, start + .5)) * fadeOut;
  ornament(c, W / 2, y0 + (rows.length - 1) * lh + 70, 140 * kk, .7 * kk);
}

// ---------- frame ----------
window.renderFrame = async function (fr) {
  const t = fr / FPS;
  let i = 0; while (i + 1 < CUTS.length && t >= CUTS[i + 1]) i++;
  // which seam (if any) are we inside?
  let seam = -1;
  for (let j = 1; j < CUTS.length; j++) if (Math.abs(t - CUTS[j]) < TR / 2) seam = j;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  if (seam > 0) {
    await drawClip(A.getContext('2d'), seam - 1, t);
    await drawClip(B.getContext('2d'), seam, t);
    const p = (t - (CUTS[seam] - TR / 2)) / TR;
    transition(ctx, KINDS[seam % KINDS.length], p);
  } else {
    await drawClip(A.getContext('2d'), i, t); ctx.drawImage(A, 0, 0);
  }
  vignette(ctx);
  dust(ctx, t);
  header(ctx, t);
  duaLine(ctx, t, i);
  if (seam > 0 && t < CUTS[seam]) duaLine(ctx, t, seam - 1);
  text(ctx, CFG.handle || '@elkosif', W / 2, 1860, `600 30px ${F_LAT}`, 'rgba(255,245,225,.55)', { dir: 'ltr' });
  // opening fade from black, closing fade
  const fin = 1 - seg(t, 0, .35), fout = seg(t, CFG.dur - .45, CFG.dur);
  if (fin > 0 || fout > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.max(fin, fout)})`; ctx.fillRect(0, 0, W, H); }
  return true;
};

(async () => {
  CFG = await (await fetch('clips.json')).json(); const SP = await (await fetch('spec.json')).json();
  Object.assign(CFG, { header: SP.header, handle: SP.handle, dur: SP.dur });
  LINES = SP.lines; CUTS = LINES.map((l, i) => i === 0 ? 0 : l[0][1] - LEAD);
  window.FRAMES = Math.round(CFG.dur * FPS);
  await Promise.all([document.fonts.load(`150px ${F_HEAD}`, CFG.header.day), document.fonts.load(`700 80px ${F_TEXT}`, 'اللهم'), document.fonts.load(`600 40px ${F_LAT}`, '2026')]);
  window.ready = true;
})();
