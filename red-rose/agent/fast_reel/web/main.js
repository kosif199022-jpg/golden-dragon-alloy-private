// Red Rose fast lane: one engine for measured dua-reel styles. Everything comes from spec.json:
// {dur, style:'dxh'|'day', handle, sticker_from, header:{day,date,hday,hmonth}, scenes:[{a,b,fin,fout,gain}], lines:[[t,text]]}
const W = 1080, H = 1920, FPS = 30;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let S = null, C = null;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const STY = {
  dxh: { font: 'AmiriB', ref: 'وقضاء الحاجات', w: 498, h: 93, top: 910, cx: 540, maxw: 980 },
  day: { font: 'Sultan', ref: 'اللهم اجعل لنا من كل هم فرجا', w: 699, h: 94, top: 914, cx: 542, maxw: 1000 },
};
const cache = new Map();
function img(src) {
  if (cache.has(src)) return cache.get(src);
  const p = new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = src; });
  cache.set(src, p); if (cache.size > 300) cache.delete(cache.keys().next().value);
  return p;
}
async function footage(i, t) {
  const sc = S.scenes[i], cl = C.clips[i];
  const n = clamp(Math.floor((t - sc.a) * FPS) + 1, 1, cl.frames);
  const im = await img(`fx/c${String(i).padStart(2, '0')}/${String(n).padStart(4, '0')}.jpg`);
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  if (im) {
    const s = Math.max(W / im.width, H / im.height);
    if (sc.gain && sc.gain !== 1) ctx.filter = `brightness(${sc.gain})`;
    ctx.drawImage(im, (W - im.width * s) / 2, (H - im.height * s) / 2, im.width * s, im.height * s); ctx.filter = 'none';
  }
  let k = 1;
  if (sc.fin) k *= seg(t, sc.fin[0], sc.fin[1]);
  if (sc.fout) k *= 1 - seg(t, sc.fout[0], sc.fout[1]);
  if (k < 1) { ctx.fillStyle = `rgba(0,0,0,${1 - k})`; ctx.fillRect(0, 0, W, H); }
}
const fit = new Map();
function ink(text, family, th, cx, top, color, o = {}) {
  const key = family + text + th + (o.w || 0);
  if (!fit.has(key)) {
    ctx.save(); ctx.direction = o.ltr ? 'ltr' : 'rtl'; ctx.font = `${o.style || ''} 100px ${family}`;
    const m = ctx.measureText(text); ctx.restore();
    const h = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent, iw = m.actualBoundingBoxLeft + m.actualBoundingBoxRight;
    fit.set(key, { px: 100 * th / h, asc: m.actualBoundingBoxAscent * th / h, sx: o.w ? o.w / (iw * th / h) : 1 });
  }
  const f = fit.get(key);
  ctx.save(); ctx.globalAlpha = o.alpha ?? 1; ctx.direction = o.ltr ? 'ltr' : 'rtl'; ctx.textAlign = 'center';
  ctx.font = `${o.style || ''} ${f.px.toFixed(1)}px ${family}`;
  ctx.translate(cx, 0); ctx.scale(f.sx, 1); ctx.translate(-cx, 0);
  ctx.shadowColor = o.shadow || 'rgba(0,0,0,.75)'; ctx.shadowBlur = o.blur ?? 10; ctx.shadowOffsetY = 2;
  if (o.stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = o.stroke; ctx.strokeStyle = color; ctx.strokeText(text, cx, top + f.asc); }
  ctx.fillStyle = color; ctx.fillText(text, cx, top + f.asc); ctx.restore();
}
function dayHeader(a) {   // measured on the @alihadkc2ok reel
  const h = S.header;
  ink(h.day, 'Panorama', 162, 830, 311, '#ffffff', { alpha: a, blur: 12, w: 354 });
  ink(h.date, 'PlexSerifB', 58, 783, 535, '#ffffff', { alpha: a, ltr: true, blur: 8, w: 411 });
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 6; ctx.fillStyle = '#fff'; ctx.fillRect(574, 614, 421, 5); ctx.restore();
  ink(h.hday, 'AmiriB', 97, 264, 264, '#fb183b', { alpha: a, blur: 8, stroke: 3, w: 101 });
  ink(h.hmonth, 'Diwani', 137, 240, 424, '#15f68d', { alpha: a, blur: 10, stroke: 6, shadow: 'rgba(0,0,0,.85)', w: 356 });
}
function heart(x, y, s) {
  ctx.beginPath(); ctx.moveTo(x, y + s * .35);
  ctx.bezierCurveTo(x - s * .9, y - s * .25, x - s * .45, y - s * .95, x, y - s * .45);
  ctx.bezierCurveTo(x + s * .45, y - s * .95, x + s * .9, y - s * .25, x, y + s * .35); ctx.closePath();
}
function sabah(a) {      // «صباح الخير» sticker, measured on the @dxhmen reel (box 423..690 x 284..521)
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a; ctx.direction = 'rtl'; ctx.textAlign = 'center';
  ctx.shadowColor = 'rgba(0,0,0,.45)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 2; ctx.lineJoin = 'round'; ctx.strokeStyle = 'rgba(40,25,15,.85)';
  ctx.save(); ctx.translate(556, 0); ctx.scale(1.38, 1); ctx.translate(-556, 0);
  ctx.font = '150px Diwani'; ctx.lineWidth = 6; ctx.strokeText('صباح', 556, 482); ctx.fillStyle = '#fff'; ctx.fillText('صباح', 556, 482); ctx.restore();
  ctx.fillStyle = '#fff'; ctx.font = '74px Diwani'; ctx.lineWidth = 5; ctx.strokeText('الخير', 640, 340); ctx.fillText('الخير', 640, 340);
  ctx.shadowBlur = 4; ctx.lineWidth = 4; heart(492, 476, 36); ctx.stroke(); ctx.lineWidth = 2.5; heart(492, 476, 36); ctx.strokeStyle = '#fff'; ctx.stroke();
  ctx.restore();
}
let LINE = null;
function line(text, a) {
  if (a <= 0) return;
  const st = STY[S.style];
  if (!LINE) {
    ctx.save(); ctx.direction = 'rtl'; ctx.font = `100px ${st.font}`; const m = ctx.measureText(st.ref); ctx.restore();
    const k = st.h / (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
    LINE = { px: 100 * k, base: st.top + m.actualBoundingBoxAscent * k, sx: st.w / ((m.actualBoundingBoxLeft + m.actualBoundingBoxRight) * k) };
  }
  ctx.save(); ctx.globalAlpha = a; ctx.direction = 'rtl'; ctx.textAlign = 'center';
  ctx.font = `${LINE.px.toFixed(1)}px ${st.font}, 'Noto Color Emoji'`;
  const w = ctx.measureText(text).width * LINE.sx, fk = w > st.maxw ? st.maxw / w : 1;
  ctx.translate(st.cx, LINE.base); ctx.scale(LINE.sx * fk, fk); ctx.translate(-st.cx, -LINE.base);
  ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 2; ctx.fillStyle = '#fff';
  ctx.fillText(text, st.cx, LINE.base); ctx.restore();
}
function handle(a) {
  ctx.save(); ctx.globalAlpha = a * .9; ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 4; ctx.fillStyle = '#fff';
  if (S.style === 'dxh') { ctx.font = '600 25px PlexSerifB'; ctx.letterSpacing = '7px'; ctx.fillText((S.handle || '@elkosif').toUpperCase(), 543, 1100); }
  else { ctx.font = 'italic 27px PlexSerifI'; ctx.fillStyle = 'rgba(235,235,235,.85)'; ctx.fillText(S.handle || '@elkosif', 540, 1100); }
  ctx.restore();
}
window.renderFrame = async function (fr) {
  const t = fr / FPS;
  let i = 0; while (i + 1 < S.scenes.length && t >= S.scenes[i + 1].a) i++;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  await footage(i, t);
  if (S.style === 'day') dayHeader(seg(t, 0.05, 0.55));
  if (S.sticker_from != null) sabah(seg(t, S.sticker_from, S.sticker_from + 0.35));
  const L = S.lines; let j = 0; while (j + 1 < L.length && t >= L[j + 1][0] - 0.1) j++;
  const nxt = j + 1 < L.length ? L[j + 1][0] - 0.1 : S.dur + 1;
  line(L[j][1], Math.min(j === 0 ? seg(t, 0, 0.3) : seg(t, L[j][0] - 0.1, L[j][0] + 0.18), 1 - seg(t, nxt - 0.18, nxt)));
  handle(1);
  return true;
};
(async () => {
  S = await (await fetch('spec.json')).json(); C = await (await fetch('clips.json')).json();
  window.FRAMES = Math.round(S.dur * FPS);
  await Promise.all(['AmiriB', 'Diwani', 'PlexSerifB', 'PlexSerifI', 'Panorama', 'Sultan'].map(f => document.fonts.load(`80px ${f}`, 'صباح ABC')));
  await document.fonts.ready; window.ready = true;
})();
