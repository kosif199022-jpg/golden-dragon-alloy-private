// «وضيئة الوجه» poem motion graphic with الراجل والست (their saved Higgsfield images). 1080x1920, 30 fps.
const W = 1080, H = 1920, FPS = 30, DUR = 22.4;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eio = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eout = t => 1 - Math.pow(1 - t, 3);
let CFG = null, IM = [];

// shots: image, start, end, camera (zoom from->to, pan in px), mood
const SH = [
  { img: 'img/s5.png', a: 0.0, b: 3.8, z: [1.10, 1.24], p: [[0, 40], [0, -20]], rain: 0 },
  { img: 'img/s1.png', a: 3.8, b: 7.85, z: [1.22, 1.08], p: [[30, -10], [-20, 30]], rain: 0 },
  { img: 'img/s3.png', a: 7.85, b: 11.95, z: [1.06, 1.26], p: [[0, 50], [0, -30]], rain: 0 },
  { img: 'img/s4.png', a: 11.95, b: 16.4, z: [1.20, 1.08], p: [[-30, 0], [30, 20]], rain: 0, sun: 1 },
  { img: 'img/s2.png', a: 16.4, b: 22.4, z: [1.06, 1.22], p: [[0, 30], [10, -30]], rain: 0 },
];
const XF = 0.7;
// the four verses (diacritics from the original's captions), word times from the voice
const LY = [
  [0.0, 3.55, [['وَضِيئَةُ', 0.0], ['الوَجْهِ', 0.6], ['لا', 1.12], ['بَدْرٌ', 1.36, 1], ['يُشَابِهُهَا', 1.8]]],
  [3.78, 7.55, [['مُحْمَرَّةُ', 3.8], ['الثَّغْرِ', 4.44], ['لا', 5.1], ['وَرْدٌ', 5.36, 1], ['يُدَانِيهَا', 5.84]]],
  [7.85, 11.7, [['بَيْضَاءُ', 7.87], ['حَمْرَاءُ', 8.48, 1], ['لا', 9.22], ['وَصْفٌ', 9.48], ['يُطَابِقُهَا', 10.06]]],
  [11.98, 21.6, [['كَأَنَّهَا', 12.0], ['الشَّمْسُ', 12.68, 1], ['قَدْ', 13.3], ['مَالَتْ', 13.64], ['خَطَاوِيهَا', 14.28]]],
];
let BEATS = [];
const beatPulse = t => { let p = 0; for (const b of BEATS) { const d = t - b; if (d >= 0 && d < .45) p = Math.max(p, Math.exp(-d * 9)); } return p; };

function img(src) { return new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = src; }); }

function drawShot(k, t, alpha) {
  const s = SH[k], im = IM[k]; if (!im) return;
  const u = eio(seg(t, s.a - XF, s.b + XF));
  const z = s.z[0] + (s.z[1] - s.z[0]) * u, px = s.p[0][0] + (s.p[1][0] - s.p[0][0]) * u, py = s.p[0][1] + (s.p[1][1] - s.p[0][1]) * u;
  const sc = Math.max(W / im.width, H / im.height) * z;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.drawImage(im, (W - im.width * sc) / 2 + px, (H - im.height * sc) / 2 + py, im.width * sc, im.height * sc);
  ctx.restore();
}
// floating golden bokeh
function bokeh(t) {
  ctx.save(); ctx.globalCompositeOperation = 'screen';
  for (let i = 0; i < 26; i++) {
    const r0 = (i * 7919) % 1000 / 1000, r1 = (i * 104729) % 1000 / 1000, r2 = (i * 1299709) % 1000 / 1000;
    const x = (r0 * W + Math.sin(t * .4 + i) * 40) % W, y = H - ((t * (25 + r1 * 40) + r2 * H) % (H + 200)) + 100;
    const R = 6 + r1 * 22, a = .10 + .18 * (.5 + .5 * Math.sin(t * 1.3 + i));
    const g = ctx.createRadialGradient(x, y, 0, x, y, R); g.addColorStop(0, `rgba(255,214,150,${a})`); g.addColorStop(1, 'rgba(255,190,120,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill();
  }
  ctx.restore();
}
function rain(t, a) {
  if (a <= 0) return; ctx.save(); ctx.globalAlpha = a * .45; ctx.strokeStyle = '#cfe3ff'; ctx.lineWidth = 2;
  for (let i = 0; i < 140; i++) {
    const r0 = (i * 7919) % 1000 / 1000, r1 = (i * 15485863) % 1000 / 1000;
    const x = (r0 * (W + 200) - 100 + t * 120) % (W + 200) - 50, y = ((t * (1400 + r1 * 600)) + r1 * H * 3) % (H + 100) - 50;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 10, y + 38 + r1 * 20); ctx.stroke();
  }
  ctx.restore();
}
function grade(t) {
  // warm top-light leak drifting, vignette, top gradient for the lyrics
  ctx.save(); ctx.globalCompositeOperation = 'screen';
  const lx = 300 + Math.sin(t * .35) * 280, g = ctx.createRadialGradient(lx, 120, 0, lx, 120, 900);
  g.addColorStop(0, 'rgba(255,170,90,.20)'); g.addColorStop(1, 'rgba(255,120,60,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore();
  const tg = ctx.createLinearGradient(0, 1250, 0, H); tg.addColorStop(0, 'rgba(8,4,12,0)'); tg.addColorStop(.55, 'rgba(8,4,12,.55)'); tg.addColorStop(1, 'rgba(8,4,12,.72)');
  ctx.fillStyle = tg; ctx.fillRect(0, 1250, W, H - 1250);
  const v = ctx.createRadialGradient(W / 2, H * .52, H * .3, W / 2, H * .52, H * .78); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.55)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}
// word-by-word lyric line: blur-in + rise; key word in shimmering gold
function lyric(t) {
  const L = LY.find(l => t >= l[0] - .05 && t < l[1] + .45); if (!L) return;
  const out = seg(t, L[1], L[1] + .45), y = 1560 - out * 30;
  ctx.save(); ctx.direction = 'rtl'; ctx.textBaseline = 'alphabetic';
  let size = 104; ctx.font = `${size}px AmiriB`;
  { const w0 = L[2].reduce((q, w) => q + ctx.measureText(w[0]).width, 0) + 26 * (L[2].length - 1); if (w0 > 960) { size = Math.floor(size * 960 / w0); ctx.font = `${size}px AmiriB`; } }
  const gap = 26, widths = L[2].map(w => ctx.measureText(w[0]).width), total = widths.reduce((a, b) => a + b, 0) + gap * (L[2].length - 1);
  let x = W / 2 + total / 2;          // right edge, words go right to left
  L[2].forEach((w, i) => {
    const k = eout(seg(t, w[1] - .08, w[1] + .38)); if (k <= 0) { x -= widths[i] + gap; return; }
    const a = k * (1 - out), cx = x - widths[i] / 2, rise = (1 - k) * 46;
    ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center';
    ctx.filter = k < 1 ? `blur(${((1 - k) * 10).toFixed(1)}px)` : 'none';
    ctx.shadowColor = 'rgba(0,0,0,.65)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
    if (w[2]) {
      const pulse = 1 + .06 * beatPulse(t) + .1 * (1 - k);
      ctx.translate(cx, y - rise); ctx.scale(pulse, pulse);
      const gg = ctx.createLinearGradient(-widths[i] / 2, -size, widths[i] / 2, 0);
      const sh = ((t - w[1]) * .6) % 1.6 - .3;
      gg.addColorStop(0, '#f3c77a'); gg.addColorStop(clamp(sh - .12), '#e7a94f'); gg.addColorStop(clamp(sh), '#fff6dc'); gg.addColorStop(clamp(sh + .12), '#e7a94f'); gg.addColorStop(1, '#f6d08a');
      ctx.fillStyle = gg; ctx.fillText(w[0], 0, 0);
      ctx.shadowColor = 'rgba(255,190,90,.75)'; ctx.shadowBlur = 30 * k; ctx.globalAlpha = a * .5; ctx.fillText(w[0], 0, 0);
    } else { ctx.fillStyle = '#fff8ef'; ctx.fillText(w[0], cx, y - rise); }
    ctx.restore(); x -= widths[i] + gap;
  });
  // small heart under the line, beating with the song
  const ha = seg(t, L[0], L[0] + .4) * (1 - out), hs = 1 + .22 * beatPulse(t);
  if (ha > 0) { ctx.save(); ctx.globalAlpha = ha; ctx.translate(W / 2, y + 62); ctx.scale(hs, hs); heart(0, 0, 22, '#fff'); ctx.restore(); }
  ctx.restore();
}
function heart(x, y, s, col) {
  ctx.beginPath(); ctx.moveTo(x, y + s * .55);
  ctx.bezierCurveTo(x - s * 1.4, y - s * .25, x - s * .6, y - s * 1.25, x, y - s * .45);
  ctx.bezierCurveTo(x + s * .6, y - s * 1.25, x + s * 1.4, y - s * .25, x, y + s * .55); ctx.closePath();
  ctx.fillStyle = col; ctx.shadowColor = 'rgba(255,120,140,.8)'; ctx.shadowBlur = 16; ctx.fill();
}
// finale: hearts float up after «وبس»
function finale(t) {
  const a = seg(t, 15.2, 15.8); if (a <= 0) return;
  for (let i = 0; i < 14; i++) {
    const r = (i * 7919) % 1000 / 1000, p = seg(t, 15.2 + r * 3, 22.4);
    if (p <= 0) continue;
    ctx.save(); ctx.globalAlpha = (1 - p) * a; heart(W / 2 + (r - .5) * 700 + Math.sin(p * 6 + i) * 30, 1600 - p * 520, 10 + r * 16, i % 2 ? '#ffd6de' : '#ff8fa8'); ctx.restore();
  }
}
function flash(t) {    // soft white bloom on each cut
  let f = 0; for (const s of SH.slice(1)) f = Math.max(f, Math.exp(-Math.pow((t - s.a) / .22, 2)));
  if (f > .02) { ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = `rgba(255,236,214,${f * .35})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
}
function credit() { ctx.save(); ctx.font = '600 24px PlexSerifB'; ctx.direction = 'ltr'; ctx.textAlign = 'right'; ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 4; ctx.fillText('© Mahmoud Elkosif', 1050, 1890); ctx.restore(); }

window.renderFrame = async function (fr) {
  const t = fr / FPS; ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.filter = 'none';
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  // beat camera breathing
  const bp = beatPulse(t); ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(1 + bp * .012, 1 + bp * .012); ctx.translate(-W / 2, -H / 2);
  SH.forEach((s, k) => {
    if (t < s.a - XF / 2 || t > s.b + XF / 2) return;
    const fin = k === 0 ? 1 : seg(t, s.a - XF / 2, s.a + XF / 2), fout = k === SH.length - 1 ? 1 : 1 - seg(t, s.b - XF / 2, s.b + XF / 2);
    drawShot(k, t, Math.min(fin, fout));
  });
  ctx.restore();
  const sunA = seg(t, 12.4, 13.4) * (1 - seg(t, 15.8, 16.6));
  if (sunA > 0) { ctx.save(); ctx.globalCompositeOperation = 'screen'; const sy = 420 + 120 * seg(t, 12.4, 16.4);
    const g = ctx.createRadialGradient(780, sy, 0, 780, sy, 900); g.addColorStop(0, `rgba(255,220,150,${.55 * sunA})`); g.addColorStop(.25, `rgba(255,170,90,${.25 * sunA})`); g.addColorStop(1, 'rgba(255,120,60,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  bokeh(t); grade(t); flash(t);
  lyric(t); finale(t);
  const fi = 1 - seg(t, 0, .6), fo = seg(t, 21.6, 22.4); if (fi + fo > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.max(fi, fo)})`; ctx.fillRect(0, 0, W, H); }
  credit(); return true;
};
(async () => {
  try { BEATS = await (await fetch('beats.json')).json(); } catch (e) {}
  IM = await Promise.all(SH.map(s => img(s.img)));
  window.FRAMES = Math.round(DUR * FPS);
  await Promise.allSettled(['Ruqaa', 'AmiriB', 'PlexSerifB'].map(f => document.fonts.load(`80px ${f}`, 'وَضِيئَةُ ABC')));
  window.ready = true;
})();
