/* Black Dragon styles kit (v1.2): the canvas helpers every style shares.
 * A film page = index.html with window.CFG (written by build_style.py) + this file + one style file (styles/*.js).
 * Lessons from the Nov 2026 films, kept on purpose:
 *  - at most 16 images in the cache and no img.decode(): big caches of decoded 1080x1920 frames made headless
 *    Chromium draw runs of black frames;
 *  - a frame that fails to load is retried (4 tries, 150 ms apart), then the shot's last good frame is drawn,
 *    so the canvas never shows an empty frame;
 *  - every frame is drawn from t alone (no Date.now, no Math.random): grain is seeded by the frame number;
 *  - Arabic lines are revealed word by word, right to left;
 *  - the watermark and the credit lines come from the spec (CFG.watermark, CFG.credit), never from code.
 */
'use strict';
const C = window.CFG || {};
const W = 1080, H = 1920, FPS = C.fps || 30, DUR = C.duration || 1;
const cv = document.getElementById('c'), g = cv.getContext('2d');
const S = C.shots || [];
const CACHE_MAX = Math.max(1, Math.min(16, C.cache || 16));
const LAST_MAX = 12;
const CACHE = new Map(), LAST = new Map();

/* ---------- numbers and easing ---------- */
const cl = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const seg = (t, a, b) => (b > a ? cl((t - a) / (b - a)) : (t >= a ? 1 : 0));
const eo = (x) => 1 - Math.pow(1 - x, 3);
const eio = (x) => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const ease = (x) => (x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);
const expo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));

/* ---------- fonts ---------- */
const WEIGHT = { Lalezar: 400 };
const font = (family, size) => `${WEIGHT[family] || 700} ${Math.round(size)}px ${family}`;

/* ---------- frames ---------- */
function load1(src) {
  return new Promise((res) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => res(null);
    im.src = src;
  });
}
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

// Cached image load with retries. The cache is first-in first-out and never holds more than CACHE_MAX entries.
function loadImg(src) {
  if (CACHE.has(src)) return CACHE.get(src);
  const p = (async () => {
    for (let k = 0; k < 4; k++) {
      const im = await load1(k ? `${src}?r=${k}` : src);
      if (im) return im;
      await pause(150);
    }
    return null;
  })();
  CACHE.set(src, p);
  while (CACHE.size > CACHE_MAX) CACHE.delete(CACHE.keys().next().value);
  return p;
}

function keepLast(key, im) {
  LAST.delete(key);
  LAST.set(key, im);
  while (LAST.size > LAST_MAX) LAST.delete(LAST.keys().next().value);
}

// Frame number of shot s at film time t (1-based, clamped to the frames that exist).
function frameNo(s, t) {
  const k = Math.floor((t - s.st) * (s.sp || 1) * (s.fps || FPS) + 1e-6) + 1;
  return Math.min(s.n, Math.max(1, k));
}
const frameUrl = (s, k) => `${s.d}/f${String(k).padStart(4, '0')}.jpg`;

// The image of shot s at time t; a frame that does not load falls back to the shot's last good frame,
// or to an earlier frame of the shot when nothing was drawn from it yet.
async function frameOf(s, t, key) {
  key = key || s.d;
  const k = frameNo(s, t);
  let im = await loadImg(frameUrl(s, k));
  if (im) { keepLast(key, im); return im; }
  im = LAST.get(key) || null;
  for (let j = k - 1; !im && j >= Math.max(1, k - 11); j--) im = await loadImg(frameUrl(s, j));
  return im;
}

// Last shot of the list that has started by time t (shots are sorted by start).
function shotIndex(t, list = S) {
  let i = 0;
  for (let j = 0; j < list.length; j++) if (list[j].st <= t) i = j;
  return i;
}

// Footage that covers a box (default: the whole frame) with a slow push that only ever grows.
// o: x y w h, push (fraction), prog (0..1 push progress, default linear over the shot), scale, dx dy, alpha,
//    filter, clip (default true), key (LAST fallback key)
async function drawShot(s, t, o = {}) {
  if (!s) return false;
  const im = await frameOf(s, cl(t, s.st, s.en + .6), o.key);
  if (!im) return false;
  const x = o.x ?? 0, y = o.y ?? 0, w = o.w ?? W, h = o.h ?? H;
  const p = o.prog ?? seg(t, s.st - .5, s.en + .5);
  const k = Math.max(w / im.width, h / im.height) * (1 + (o.push ?? .06) * p) * (o.scale || 1);
  const iw = im.width * k, ih = im.height * k;
  g.save();
  if (o.clip !== false) { g.beginPath(); g.rect(x, y, w, h); g.clip(); }
  if (o.filter) g.filter = o.filter;
  if (o.alpha != null) g.globalAlpha = cl(o.alpha);
  g.drawImage(im, x + (w - iw) * (s.fx ?? .5) + (o.dx || 0), y + (h - ih) * (s.fy ?? .5) + (o.dy || 0), iw, ih);
  g.restore();
  return true;
}

/* ---------- looks ---------- */
// Film grain: n dots of 2 px; the same pattern for the same frame (seeded by the frame number).
function grain(t, a = .035, n = 1000) {
  if (!(a > 0)) return;
  let s = Math.floor(t * FPS + 1e-6) * 9 + 3;
  const R = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  g.save();
  g.globalAlpha = a;
  for (let i = 0; i < n; i++) {
    g.fillStyle = R() < .5 ? '#000' : '#fff';
    g.fillRect(R() * W, R() * H, 2, 2);
  }
  g.restore();
}

function vignette(k = .45, inner = 500) {
  if (!(k > 0)) return;
  const v = g.createRadialGradient(540, 900, inner, 540, 960, 1250);
  v.addColorStop(0, 'rgba(0,0,0,0)');
  v.addColorStop(1, `rgba(0,0,0,${k})`);
  g.fillStyle = v;
  g.fillRect(0, 0, W, H);
}

const GOLD = ['#fbe3a0', '#d9a944', '#9c6f1c'];       // trio films (nil, beat, wall)
const GOLD_SOFT = ['#f7dd92', '#d9a944', '#a8781f'];  // bint / forty films (chapters, clean)
// Vertical gold gradient between y0 and y1 (in the current transform).
function goldG(y0, y1, stops = GOLD) {
  const gr = g.createLinearGradient(0, y0, 0, y1);
  gr.addColorStop(0, stops[0]);
  gr.addColorStop(.55, stops[1]);
  gr.addColorStop(1, stops[2]);
  return gr;
}

function rr(x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

// Fade from black at the start and towards black at the end (outMax: how dark the last frame gets).
function fades(t, inD = .5, outD = .7, outMax = .9) {
  const a = inD > 0 ? cl(1 - t / inD) : 0, b = outD > 0 ? cl((t - (DUR - outD)) / outD) : 0;
  const k = Math.max(a, b * outMax);
  if (k > 0) { g.fillStyle = `rgba(0,0,0,${k})`; g.fillRect(0, 0, W, H); }
}

function dim(k, color = '0,0,0') {
  if (k > 0) { g.fillStyle = `rgba(${color},${k})`; g.fillRect(0, 0, W, H); }
}

/* ---------- type ---------- */
// One centred line with a soft shadow. o: family, size, fill, alpha, blur, shadow, maxw, baseline
function centerText(text, x, y, o = {}) {
  if (!text) return;
  g.save();
  if (o.alpha != null) g.globalAlpha = cl(o.alpha);
  g.textAlign = 'center';
  g.textBaseline = o.baseline || 'middle';
  g.direction = 'rtl';
  g.font = font(o.family || 'Tajawal', o.size || 50);
  g.shadowColor = o.shadow || 'rgba(0,0,0,.7)';
  g.shadowBlur = o.blur ?? 20;
  g.fillStyle = o.fill || '#fff';
  g.fillText(text, x, y, o.maxw || 1000);
  g.restore();
}

// A line that arrives word by word (right to left), blurred to sharp with a small rise, and leaves the same way.
// o: size, family, fill (colour), gold (gold gradient), soft (white to grey), stagger, rise, maxw
function words(txt, t, a, e, y, o = {}) {
  if (!txt || t < a || t > e) return;
  const size = o.size || 70, ws = String(txt).split(/\s+/).filter(Boolean);
  if (!ws.length) return;
  g.save();
  g.font = font(o.family || 'Tajawal', size);
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  g.textAlign = 'right';
  const sp = g.measureText(' ').width, wd = ws.map((w) => g.measureText(w).width);
  const tot = wd.reduce((p, q) => p + q, 0) + sp * (ws.length - 1);
  const fit = Math.min(1, (o.maxw || 1000) / tot);
  g.translate(540, y);
  g.scale(fit, fit);
  let fill = o.fill || '#fff';
  if (o.gold) fill = goldG(-size * .6, size * .6, o.goldStops || GOLD);
  else if (o.soft) {
    fill = g.createLinearGradient(0, -size / 2, 0, size / 2);
    fill.addColorStop(0, '#fff'); fill.addColorStop(.5, '#fff'); fill.addColorStop(1, '#cfcfd4');
  }
  const stag = o.stagger ?? .09, rise = o.rise ?? 20, outD = o.out ?? .5;
  let x = tot / 2;
  ws.forEach((w, i) => {
    const kin = eo(cl((t - a - i * stag) / .55));
    const kout = eo(cl((t - (e - outD) + (ws.length - 1 - i) * .05) / (outD - .05)));
    const k = kin * (1 - kout);
    g.globalAlpha = k;
    g.filter = `blur(${((1 - k) * 10).toFixed(2)}px)`;
    g.shadowColor = 'rgba(0,0,0,.7)';
    g.shadowBlur = 20;
    g.fillStyle = fill;
    g.fillText(w, x, (1 - kin) * rise - kout * 10);
    x -= wd[i] + sp;
  });
  g.restore();
}

// Draw every spec line (CFG.lines) with words(); per-line font / size / gold / y win over the style's defaults.
function specLines(t, y, size, extra = {}) {
  for (const q of C.lines || []) {
    words(q.t, t, q.s, q.e, q.y || y, { ...extra, size: q.size || size, family: q.font || extra.family,
      gold: q.gold || extra.gold });
  }
}

// The credit lines from the spec, fading in at time a. o: sizes, gap, fade, baseline
// v1.3: never later than DUR - 3, so «مونتاج وإخراج / تابعني على فيسبوك» always holds about 3 s.
// Slots per style (y of the first line): nil/wall/beat 1500, clean 1440, chapters 1420, medal 1560 (README).
function credit(t, a, y = 1560, o = {}) {
  a = Math.max(0, Math.min(a, DUR - 3));
  const L = C.credit || [];
  const k = eo(seg(t, a, a + (o.fade || .8)));
  if (k <= 0 || !L.length) return;
  const sizes = o.sizes || [40, 30], gap = o.gap || 56;
  g.save();
  g.globalAlpha = k;
  g.textAlign = 'center';
  g.textBaseline = o.baseline || 'alphabetic';
  g.direction = 'rtl';
  g.shadowColor = 'rgba(0,0,0,.8)';
  g.shadowBlur = 12;
  L.forEach((ln, i) => {
    g.font = font('Tajawal', sizes[Math.min(i, sizes.length - 1)]);
    g.fillStyle = i ? 'rgba(255,255,255,.8)' : '#fff';
    g.fillText(ln, 540, y + i * gap, 1000);
  });
  g.restore();
}

// The persistent watermark from the spec, bottom left.
function watermark() {
  if (!C.watermark) return;
  g.save();
  g.font = font('Tajawal', 24);
  g.direction = 'ltr';
  g.textAlign = 'left';
  g.textBaseline = 'middle';
  g.fillStyle = 'rgba(255,255,255,.6)';
  g.shadowColor = 'rgba(0,0,0,.8)';
  g.shadowBlur = 6;
  g.fillText(C.watermark, 40, 1885);
  g.restore();
}

/* ---------- page contract ---------- */
// render.cjs contract: window.__kosif = { duration, seek(t) } and window.__kosifReady (a promise, then true).
// Seeks run one after another on the shared canvas; a failed seek does not block the next one.
function boot(render) {
  let chain = Promise.resolve();
  const seek = (t) => {
    const p = chain.then(() => render(Number(t) || 0));
    chain = p.catch(() => {});
    return p;
  };
  const fams = (C.fonts || []).map(([f, w]) => document.fonts.load(`${w} 40px ${f}`).catch(() => null));
  const ready = Promise.all(fams).then(() => seek(0)).then(() => true);
  window.__kosif = { duration: DUR, fps: FPS, seek };
  window.__kosifReady = ready;
  ready.then(() => { window.__kosifReady = true; }, (e) => console.error('first frame failed:', e && e.message));
}
