// Lyric motion reel (Red Rose): one scene per sung line, Ruqaa word reveals, petals, warm grade.
// Settings come from clips.json (written by build.py from song.json): title, subtitle, handle, bursts, chorus.
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


// ---------- lines (LINES/LEND from lines.js: words with start times, sung) ----------
const LEAD = 0.12;
const CUTS = LINES.map((l, i) => i === 0 ? 0 : l[0][1] - LEAD);
const TR = 0.42;
const KINDS = ['light', 'whip', 'spin', 'light', 'blurzoom', 'light', 'zoom', 'zoom', 'slideup', 'light', 'spin', 'blurzoom', 'whip', 'light', 'slideup', 'light'];
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
  grade(c, CFG.clips[i].tint || '#ffb070');
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
const PET = (() => { const r = rnd(11), a = []; for (let i = 0; i < 26; i++) a.push({ x: r() * W, y: r() * H, s: 14 + r() * 22, v: 60 + r() * 90, ph: r() * 6, rot: r() * 6, col: r() < .7 ? [178, 24, 44] : [232, 120, 140] }); return a; })();
function petals(c, t, amt) {
  if (amt <= 0) return;
  c.save();
  for (const p of PET) {
    const y = (p.y + p.v * t) % (H + 200) - 100, x = p.x + Math.sin(t * .9 + p.ph) * 60;
    c.save(); c.translate(x, y); c.rotate(p.rot + t * (.6 + p.ph * .1)); c.scale(1, .55 + .45 * Math.sin(t * 2.2 + p.ph));
    c.globalAlpha = .82 * amt; c.fillStyle = `rgb(${p.col})`;
    c.beginPath(); c.ellipse(0, 0, p.s, p.s * .62, 0, 0, Math.PI * 2); c.fill();
    c.globalAlpha = .35 * amt; c.fillStyle = '#fff'; c.beginPath(); c.ellipse(-p.s * .25, -p.s * .15, p.s * .3, p.s * .12, 0, 0, Math.PI * 2); c.fill();
    c.restore();
  }
  c.restore();
}
const DUST = (() => { const r = rnd(4), a = []; for (let i = 0; i < 36; i++) a.push({ x: r() * W, y: r() * H, s: 2 + r() * 6, v: 8 + r() * 30, ph: r() * 6 }); return a; })();
function dust(c, t) {
  c.save(); c.globalCompositeOperation = 'screen';
  for (const d of DUST) {
    const y = (d.y - d.v * t * 3 + H * 10) % H, x = d.x + Math.sin(t * .6 + d.ph) * 30, a = .22 + .22 * Math.sin(t * 2 + d.ph);
    const g = c.createRadialGradient(x, y, 0, x, y, d.s * 3); g.addColorStop(0, `rgba(255,220,180,${a})`); g.addColorStop(1, 'rgba(255,220,180,0)');
    c.fillStyle = g; c.fillRect(x - d.s * 3, y - d.s * 3, d.s * 6, d.s * 6);
  }
  c.restore();
}
function vignette(c) {
  let g = c.createRadialGradient(W / 2, 1260, 120, W / 2, 1260, 720); g.addColorStop(0, 'rgba(12,4,4,.5)'); g.addColorStop(1, 'rgba(12,4,4,0)'); c.fillStyle = g; c.fillRect(0, 600, W, 1300);
  g = c.createRadialGradient(W / 2, H / 2, 640, W / 2, H / 2, 1300); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(20,0,6,.5)'); c.fillStyle = g; c.fillRect(0, 0, W, H);
}
function text(c, s, x, y, font, fill, opts = {}) {
  c.save(); c.font = font; c.direction = opts.dir || 'rtl'; c.textAlign = opts.align || 'center'; c.textBaseline = 'alphabetic';
  if (opts.shadow) { c.shadowColor = opts.shadow; c.shadowBlur = opts.blur || 18; c.shadowOffsetY = opts.oy || 4; }
  c.fillStyle = fill; c.fillText(s, x, y); c.restore();
}
function heart(c, x, y, s, a) {
  c.save(); c.globalAlpha = a; c.translate(x, y); c.scale(s, s); c.fillStyle = '#e9b06a';
  c.beginPath(); c.moveTo(0, 6); c.bezierCurveTo(-14, -4, -8, -16, 0, -8); c.bezierCurveTo(8, -16, 14, -4, 0, 6); c.fill(); c.restore();
}
function layout(c, words, size) {
  c.font = `${size}px ${F_HEAD}`;
  const sp = size * .3, ws = words.map(w => c.measureText(w[0]).width);
  const rows = [[]]; let cur = 0;
  words.forEach((w, i) => { const add = ws[i] + (rows[rows.length - 1].length ? sp : 0); if (cur + add > 900 && rows[rows.length - 1].length) { rows.push([]); cur = 0; } rows[rows.length - 1].push(i); cur += add; });
  return { ws, sp, rows };
}
function lyric(c, t, li) {
  const words = LINES[li]; if (!words) return;
  const end = li + 1 < CUTS.length ? CUTS[li + 1] : CFG.dur - .3;
  const fadeOut = 1 - seg(t, end - .16, end + .04);
  if (fadeOut <= 0) return;
  const size = (CFG.big_lines || []).includes(li) ? 150 : 128, { ws, sp, rows } = layout(c, words, size);
  const lh = size * 1.45, y0 = 1270 - (rows.length - 1) * lh / 2;
  rows.forEach((row, r) => {
    const total = row.reduce((a, i) => a + ws[i], 0) + sp * (row.length - 1);
    let x = W / 2 + total / 2;
    for (const i of row) {
      const wt = words[i][1] - .08, k = eout(seg(t, wt, wt + .45));
      const cx = x - ws[i] / 2, y = y0 + r * lh;
      if (k > 0) {
        c.save(); c.globalAlpha = k * fadeOut;
        c.translate(cx, y + (1 - k) * 34); const sc = 1.18 - .18 * k; c.scale(sc, sc);
        c.filter = k < 1 ? `blur(${((1 - k) * 10).toFixed(1)}px)` : 'none';
        c.font = `${size}px ${F_HEAD}`; c.direction = 'rtl'; c.textAlign = 'center';
        c.shadowColor = 'rgba(30,0,6,.9)'; c.shadowBlur = 34; c.shadowOffsetY = 6; c.fillStyle = '#fff'; c.fillText(words[i][0], 0, 0);
        c.shadowBlur = 8; c.shadowColor = 'rgba(0,0,0,.5)'; c.fillText(words[i][0], 0, 0);
        c.shadowColor = 'transparent';
        const hot = 1 - seg(t, words[i][1] + .25, words[i][1] + 1.0);
        if (hot > 0) { c.globalAlpha = k * fadeOut * hot; const g = c.createLinearGradient(0, -size, 0, 10); g.addColorStop(0, '#ffe3b0'); g.addColorStop(1, '#ff9a7a'); c.fillStyle = g; c.fillText(words[i][0], 0, 0); }
        c.restore();
      }
      x -= ws[i] + sp;
    }
  });
  const kk = eout(seg(t, CUTS[li] + .1, CUTS[li] + .6)) * fadeOut;
  const yb = y0 + (rows.length - 1) * lh + 80;
  c.save(); c.globalAlpha = .75 * kk; c.strokeStyle = '#e9b06a'; c.lineWidth = 2.5; c.lineCap = 'round';
  c.beginPath(); c.moveTo(W / 2 - 150 * kk, yb); c.lineTo(W / 2 - 26, yb); c.moveTo(W / 2 + 26, yb); c.lineTo(W / 2 + 150 * kk, yb); c.stroke(); c.restore();
  heart(c, W / 2, yb, 1.4, .85 * kk);
}
function title(c, t) {
  const a = eout(seg(t, .2, 1.0)) * (1 - seg(t, 4.2, 5.0));
  if (a <= 0) return;
  c.save(); c.globalAlpha = a;
  text(c, CFG.title || '', W / 2, 300, `110px ${F_HEAD}`, '#fff1dc', { shadow: 'rgba(40,0,8,.8)', blur: 26 });
  text(c, CFG.subtitle || '', W / 2, 360, `600 30px ${F_LAT}`, 'rgba(255,230,200,.85)', { dir: 'ltr', shadow: 'rgba(0,0,0,.6)', blur: 10 });
  c.restore();
}
function bars(c, t) {   // soft cinematic bars that breathe in on the chorus
  const ch = CFG.chorus; if (!ch) return; const k = eio(seg(t, ch[0] - .5, ch[0] + .4)) * (1 - eio(seg(t, ch[1] - .2, ch[1] + .6)));
  const h = 40 + 70 * k; c.fillStyle = '#000'; c.fillRect(0, 0, W, h); c.fillRect(0, H - h, W, h);
}

// ---------- frame ----------
window.renderFrame = async function (fr) {
  const t = fr / FPS;
  let i = 0; while (i + 1 < CUTS.length && t >= CUTS[i + 1]) i++;
  let seam = -1;
  for (let j = 1; j < CUTS.length; j++) if (Math.abs(t - CUTS[j]) < TR / 2) seam = j;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.filter = 'none';
  if (seam > 0) {
    await drawClip(A.getContext('2d'), seam - 1, t);
    await drawClip(B.getContext('2d'), seam, t);
    transition(ctx, KINDS[seam % KINDS.length], (t - (CUTS[seam] - TR / 2)) / TR);
  } else {
    await drawClip(A.getContext('2d'), i, t); ctx.drawImage(A, 0, 0);
  }
  vignette(ctx);
  dust(ctx, t);
  // petals: light all through, a burst on «قلبي مع العشاق», «الحب ذنب / أجمل عذاب» and the chorus
  const burst = Math.max(0, ...(CFG.bursts || []).map(([a, b]) => seg(t, a - .1, a + .4) * (1 - seg(t, b - .4, b + .2))));
  petals(ctx, t, .35 + .65 * burst);
  bars(ctx, t);
  title(ctx, t);
  lyric(ctx, t, i);
  if (seam > 0 && t < CUTS[seam]) lyric(ctx, t, seam - 1);
  if (CFG.handle) text(ctx, CFG.handle, W / 2, 1840, `600 28px ${F_LAT}`, 'rgba(255,240,225,.5)', { dir: 'ltr' });
  const fin = 1 - seg(t, 0, .4), fout = seg(t, CFG.dur - 1.2, CFG.dur);
  if (fin > 0 || fout > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.max(fin, fout)})`; ctx.fillRect(0, 0, W, H); }
  return true;
};

(async () => {
  CFG = await (await fetch('clips.json')).json();
  window.FRAMES = Math.round(CFG.dur * FPS);
  await Promise.all([document.fonts.load(`128px ${F_HEAD}`, 'قلبي'), document.fonts.load(`600 40px ${F_LAT}`, 'ABC')]);
  window.ready = true;
})();
