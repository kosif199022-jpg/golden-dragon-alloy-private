// Remake of the @youma.design reel: same footage and sound (text removed, light regraded), new lettering and motion.
const W = 1080, H = 1920, FPS = 30, DUR = 27.5;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eout = t => 1 - Math.pow(1 - t, 3);
const KEY = new Set(['عادي', 'عادي...', 'ساكت', 'بكبر', 'معادي']);
// [line start, line end, words [text, time], row (0 = main line, 1 = second line under it)]
const L = [
  [0.0, 1.0, [['انا', 0.0], ['كنت', 0.3], ['عايز', 0.6]], 0],
  [1.0, 3.75, [['ابقى', 1.0], ['عادي...', 1.45]], 0],
  [3.8, 4.78, [['طلب', 3.82], ['عادي', 4.35]], 0],
  [4.8, 6.25, [['والعالم', 4.82], ['بيقولي', 5.75]], 0],
  [6.3, 8.95, [['اكبر', 6.3], ['وانا..', 6.9], ['ساكت', 7.45]], 0],
  [9.0, 10.45, [['بيقولي', 9.0]], 0],
  [10.5, 13.85, [['كل', 10.56], ['دا', 11.3], ['عادي', 11.8]], 0],
  [13.9, 17.45, [['وان', 13.9], ['انا', 14.44], ['بكبر', 14.6]], 0],
  [15.1, 17.45, [['في', 15.1], ['معادي', 15.32]], 1],
  [17.5, 27.5, [['أيوه', 17.5], ['أنا', 18.62], ['بكبر', 18.85]], 0],
  [19.7, 27.5, [['في', 19.7], ['معادي', 20.9]], 1],
];
const cache = new Map();
function img(n) { if (cache.has(n)) return cache.get(n); const p = new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = `fx/${String(n).padStart(4, '0')}.jpg`; }); cache.set(n, p); if (cache.size > 40) cache.delete(cache.keys().next().value); return p; }
function grain(t) {
  const g = (window.G ||= (() => { const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d'), d = x.createImageData(256, 256);
    for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 22; } x.putImageData(d, 0, 0); return c; })());
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; const ox = (t * 977) % 256, oy = (t * 613) % 256;
  ctx.translate(-ox, -oy); ctx.fillStyle = ctx.createPattern(g, 'repeat'); ctx.fillRect(0, 0, W + 256, H + 256); ctx.restore();
}
function light(t) {
  // cinema part: soft projector beam and screen spill; later: drifting warm leak
  if (t < 7.2) {
    const a = (1 - seg(t, 6.6, 7.2)) * (.16 + .04 * Math.sin(t * 23) * Math.sin(t * 7));
    ctx.save(); ctx.globalCompositeOperation = 'screen';
    const g = ctx.createLinearGradient(0, 300, 0, 1500); g.addColorStop(0, `rgba(255,236,200,${a})`); g.addColorStop(1, 'rgba(255,236,200,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(240, 330); ctx.lineTo(840, 330); ctx.lineTo(1180, 1600); ctx.lineTo(-100, 1600); ctx.closePath(); ctx.fill(); ctx.restore();
  } else {
    ctx.save(); ctx.globalCompositeOperation = 'screen'; const x = 540 + Math.sin(t * .3) * 420;
    const g = ctx.createRadialGradient(x, 200, 0, x, 200, 1000); g.addColorStop(0, 'rgba(255,170,100,.10)'); g.addColorStop(1, 'rgba(255,170,100,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore();
  }
  const v = ctx.createRadialGradient(W / 2, H / 2, H * .32, W / 2, H / 2, H * .78); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.5)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  // soft dark bed under the words
  const b = ctx.createLinearGradient(0, 860, 0, 1300); b.addColorStop(0, 'rgba(0,0,0,0)'); b.addColorStop(.5, 'rgba(0,0,0,.28)'); b.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = b; ctx.fillRect(0, 860, W, 440);
}
function line(l, t) {
  const [a, b, words, row] = l; if (t < a - .05 || t > b + .28) return;
  const out = seg(t, b - .22, b + .06), size = row ? 104 : 96, y = (row ? 1158 : 1040) - out * 26;
  ctx.save(); ctx.direction = 'rtl'; ctx.font = `${size}px Ruqaa`; ctx.textAlign = 'center';
  const gap = 28, ws = words.map(w => ctx.measureText(w[0]).width), tot = ws.reduce((p, q) => p + q, 0) + gap * (ws.length - 1);
  let x = W / 2 + tot / 2;
  words.forEach((w, i) => {
    const k = eout(seg(t, w[1] - .06, w[1] + .42)), cx = x - ws[i] / 2; x -= ws[i] + gap;
    if (k <= 0) return;
    const key = KEY.has(w[0]), a2 = k * (1 - out);
    ctx.save(); ctx.globalAlpha = a2; ctx.translate(cx, y + (1 - k) * 38);
    const s = key ? 1 + .14 * (1 - k) + .03 * Math.sin((t - w[1]) * 3) * k : 1; ctx.scale(s, s);
    ctx.filter = k < .98 ? `blur(${((1 - k) * 9).toFixed(1)}px)` : 'none';
    ctx.shadowColor = key ? 'rgba(255,170,80,.75)' : 'rgba(0,0,0,.7)'; ctx.shadowBlur = key ? 28 : 16; ctx.shadowOffsetY = key ? 0 : 3;
    if (key) {
      const g = ctx.createLinearGradient(-ws[i] / 2, 0, ws[i] / 2, 0), sw = ((t - w[1]) * .45) % 1.8 - .4;
      g.addColorStop(0, '#ffd7a0'); g.addColorStop(clamp(sw - .1), '#ffc27a'); g.addColorStop(clamp(sw), '#fffaf0'); g.addColorStop(clamp(sw + .1), '#ffc27a'); g.addColorStop(1, '#ffdcaa');
      ctx.fillStyle = g;
    } else ctx.fillStyle = '#fbf6ee';
    ctx.fillText(w[0], 0, 0); ctx.restore();
  });
  // thin light line drawn right to left under the main line, lasting the line
  if (!row) {
    const p = eout(seg(t, a, Math.min(b, a + 1.2))), len = (tot + 80) * p, la = .7 * (1 - out);
    ctx.save(); ctx.globalAlpha = la; const g = ctx.createLinearGradient(W / 2 + tot / 2 + 40, 0, W / 2 - tot / 2 - 40, 0);
    g.addColorStop(0, 'rgba(255,214,160,0)'); g.addColorStop(.5, 'rgba(255,214,160,.9)'); g.addColorStop(1, 'rgba(255,214,160,0)');
    ctx.fillStyle = g; ctx.fillRect(W / 2 + tot / 2 + 40 - len, y + 34, len, 2.5); ctx.restore();
  }
  ctx.restore();
}
window.renderFrame = async function (fr) {
  const t = fr / FPS; ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.filter = 'none';
  const im = await img(Math.min(825, fr + 1));
  // slow push-in through the whole reel, a small breath on each cut
  const z = 1 + .03 * (t / DUR);
  if (im) { ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.drawImage(im, -W / 2, -H / 2, W, H); ctx.restore(); }
  light(t); L.forEach(l => line(l, t)); grain(t);
  const fo = seg(t, 26.6, 27.5); if (fo > 0) { ctx.fillStyle = `rgba(0,0,0,${fo})`; ctx.fillRect(0, 0, W, H); }
  return true;
};
(async () => { window.FRAMES = Math.round(DUR * FPS); await Promise.allSettled(['Ruqaa', 'AmiriB'].map(f => document.fonts.load(`80px ${f}`, 'انا عادي'))); window.ready = true; })();
