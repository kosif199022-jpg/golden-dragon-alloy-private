// Red Rose fast lane: one engine for measured dua-reel styles. Everything comes from spec.json:
// {dur, style:'dxh'|'day'|'adeiat'|'oaun'|'none', elements:[mimic draw objects], handle, sticker_from, header:{day,date,hday,hmonth}, scenes:[{a,b,fin,fout,gain}], lines:[[t,text]]}
const W = 1080, H = 1920, FPS = 30;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let S = null, C = null;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const STY = {
  dxh: { font: 'AmiriB', ref: 'وقضاء الحاجات', w: 498, h: 93, top: 910, cx: 540, maxw: 980 },
  adeiat: { font: 'AlmaraiXB', ref: 'اللهم في يوم الثلاثاء', w: 458, h: 54, top: 943, cx: 536, maxw: 940 },
  oaun: { font: 'Sultan', ref: 'اللهم أدم علينا نعمة العطاء', w: 770, h: 62, top: 932, cx: 545, maxw: 1000 },
  day: { font: 'Sultan', ref: 'اللهم اجعل لنا من كل هم فرجا', w: 699, h: 94, top: 914, cx: 542, maxw: 1000 },
};
const cache = new Map();
function img(src) {
  if (cache.has(src)) return cache.get(src);
  const p = new Promise(r => { const i = new Image(); i.onload = () => r(i); i.onerror = () => r(null); i.src = src; });
  cache.set(src, p); if (cache.size > 300) cache.delete(cache.keys().next().value);
  return p;
}
async function clipFrame(i, t, alpha) {
  const sc = S.scenes[i], cl = C.clips[i];
  const n = clamp(Math.floor((t - sc.a) * FPS) + 1, 1, cl.frames);
  const im = await img(`fx/c${String(i).padStart(2, '0')}/${String(n).padStart(4, '0')}.jpg`);
  if (!im) return;
  const s = Math.max(W / im.width, H / im.height); ctx.save(); ctx.globalAlpha = alpha;
  if (sc.gain && sc.gain !== 1) ctx.filter = `brightness(${sc.gain})`;
  ctx.drawImage(im, (W - im.width * s) / 2, (H - im.height * s) / 2, im.width * s, im.height * s); ctx.restore();
}
async function footage(i, t) {
  const sc = S.scenes[i];
  // crossfade: scene i fades in over the tail of scene i-1 for sc.xf seconds (clips are cut with spare frames)
  if (sc.xf && i > 0 && t < sc.a + sc.xf) {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    await clipFrame(i - 1, t, 1); await clipFrame(i, t, seg(t, sc.a, sc.a + sc.xf)); return;
  }
  const cl = C.clips[i];
  const n = clamp(Math.floor((t - sc.a) * FPS) + 1, 1, cl.frames);
  const im = await img(`fx/c${String(i).padStart(2, '0')}/${String(n).padStart(4, '0')}.jpg`);
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  if (im) {
    const s = Math.max(W / im.width, H / im.height), dw = im.width * s, dh = im.height * s;
    if (sc.gain && sc.gain !== 1) ctx.filter = `brightness(${sc.gain})`;
    // whip: horizontal motion blur that peaks on the cut (scene.whip seconds, half before and half after)
    const nx = S.scenes[i + 1], wIn = sc.whip && i > 0 ? 1 - seg(t, sc.a, sc.a + sc.whip / 2) : 0,
      wOut = nx && nx.whip ? seg(t, nx.a - nx.whip / 2, nx.a) : 0, wb = Math.max(wIn, wOut);
    if (wb > 0.01) {
      const taps = 12, spread = 260 * wb * wb, dir = wIn > wOut ? -1 : 1;
      ctx.drawImage(im, (W - dw) / 2, (H - dh) / 2, dw, dh);
      for (let k = 0; k < taps; k++) {
        ctx.globalAlpha = 1 / (k + 1); const x = ((k / (taps - 1)) - 0.5) * spread + dir * 60 * wb;
        ctx.drawImage(im, (W - dw) / 2 + x, (H - dh) / 2, dw, dh);
      }
      ctx.globalAlpha = 1;
    } else ctx.drawImage(im, (W - dw) / 2, (H - dh) / 2, dw, dh);
    ctx.filter = 'none';
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
  if (o.outline) { ctx.lineJoin = 'round'; ctx.lineWidth = o.ow || 6; ctx.strokeStyle = o.outline; ctx.strokeText(text, cx, top + f.asc); ctx.shadowColor = 'transparent'; }
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
function oaunHeader(a) {  // measured on the @oaun.11 Wednesday reel (25.11.2026): day right, date on an underline, Hijri left
  const h = S.header;
  ink(h.day, 'Panorama', 122, 762, 460, '#ffffff', { alpha: a, blur: 12, w: 325 });
  ink(h.date, 'PlexSerifB', 46, 760, 615, '#ffffff', { alpha: a, ltr: true, blur: 8, w: 380 });
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 5; ctx.fillStyle = '#fff'; ctx.fillRect(565, 688, 390, 4); ctx.restore();
  ink(h.hday, 'AmiriB', 70, 312, 290, '#35d26a', { alpha: a, blur: 6, outline: 'rgba(20,60,25,.9)', ow: 5, stroke: 2, w: 70 });
  const g = ctx.createLinearGradient(0, 380, 0, 500); g.addColorStop(0, '#fff3a6'); g.addColorStop(.5, '#f2c935'); g.addColorStop(1, '#d99a17');
  ink(h.hmonth, 'Diwani', 120, 330, 380, g, { alpha: a, blur: 8, outline: 'rgba(25,110,45,.95)', ow: 6, stroke: 7, w: 360 });
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
// ---- style «adeiat»: measured on the @adeiat129 Tuesday reel (720x1280 source, coordinates x1.5) ----
function goldFill(y0, y1) {
  const g = ctx.createLinearGradient(0, y0, 0, y1);
  g.addColorStop(0, '#fff1c1'); g.addColorStop(.45, '#e9c46f'); g.addColorStop(.75, '#c8963a'); g.addColorStop(1, '#f2d98f'); return g;
}
function ornament(cx, cy, w, h, flip) {   // gold arabesque medallion (pointed diamond with filigree) beside the Hijri date
  ctx.save(); ctx.translate(cx, cy); if (flip) ctx.scale(-1, 1);
  const shape = (k) => { const W2 = w * k / 2, H2 = h * k / 2; ctx.beginPath(); ctx.moveTo(0, -H2);
    ctx.bezierCurveTo(W2 * .35, -H2 * .55, W2 * 1.05, -H2 * .35, W2, 0); ctx.bezierCurveTo(W2 * 1.05, H2 * .35, W2 * .35, H2 * .55, 0, H2);
    ctx.bezierCurveTo(-W2 * .35, H2 * .55, -W2 * 1.05, H2 * .35, -W2, 0); ctx.bezierCurveTo(-W2 * 1.05, -H2 * .35, -W2 * .35, -H2 * .55, 0, -H2); ctx.closePath(); };
  ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 8; shape(1); ctx.fillStyle = 'rgba(30,22,14,.85)'; ctx.fill(); ctx.shadowBlur = 0;
  const g = goldFill(-h / 2, h / 2); ctx.strokeStyle = g; ctx.fillStyle = g;
  ctx.lineWidth = 3; shape(1); ctx.stroke(); ctx.lineWidth = 1.4; shape(.8); ctx.stroke();
  // filigree: four-petal rosette, scrolls and a stem of dots
  for (let a = 0; a < 4; a++) { ctx.save(); ctx.rotate(a * Math.PI / 2); ctx.beginPath(); ctx.ellipse(0, -w * .16, w * .07, w * .16, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
  ctx.beginPath(); ctx.arc(0, 0, w * .06, 0, Math.PI * 2); ctx.fill();
  for (const sy of [-1, 1]) {
    ctx.beginPath(); ctx.moveTo(0, sy * h * .2); ctx.bezierCurveTo(w * .22, sy * h * .22, w * .2, sy * h * .32, w * .05, sy * h * .3); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, sy * h * .2); ctx.bezierCurveTo(-w * .22, sy * h * .22, -w * .2, sy * h * .32, -w * .05, sy * h * .3); ctx.stroke();
    for (const d of [.36, .41]) { ctx.beginPath(); ctx.arc(0, sy * h * d, 2, 0, Math.PI * 2); ctx.fill(); }
  }
  for (const sx of [-1, 1]) { ctx.beginPath(); ctx.arc(sx * w * .3, 0, 2.2, 0, Math.PI * 2); ctx.fill(); }
  ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, -h / 2 - 12); ctx.lineTo(0, -h / 2); ctx.moveTo(0, h / 2); ctx.lineTo(0, h / 2 + 12); ctx.stroke();
  ctx.restore();
}
function hijriBlock(a) {
  const h = S.header; if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a;
  ornament(70, 205, 72, 150, false); ornament(578, 205, 72, 150, true);
  ctx.restore();
  ink(`${h.hday} ${h.hmonth}`, 'Panorama', 140, 326, 134, goldFill(134, 274), { alpha: a, blur: 10, w: 440, shadow: 'rgba(0,0,0,.8)', outline: 'rgba(60,40,15,.8)', ow: 3 });
  ink(h.hline || '', 'AmiriB', 40, 330, 282, '#f3ead8', { alpha: a, blur: 6, w: 350 });
  ink(h.hyear || '', 'AmiriB', 23, 328, 340, '#f3ead8', { alpha: a, blur: 5, w: 80 });
}
function dayBlock(a) {
  const h = S.header; if (a <= 0) return;
  ink(h.day, 'Panorama', 280, 755, 386, '#ffffff', { alpha: a, blur: 14, w: 350, shadow: 'rgba(0,0,0,.85)', outline: 'rgba(20,14,10,.9)' });
  ink(h.date, 'TajawalM', 88, 730, 682, '#ffffff', { alpha: a, ltr: true, blur: 12, w: 528, shadow: 'rgba(0,0,0,.85)' });
}
let RIB = null;
function ribbon(a) {   // blue brushed band 218..900 x 1065..1133 with hatching; «دعاء يوم ...» in Kufam, white with a navy edge
  if (a <= 0) return;
  if (!RIB) {
    RIB = document.createElement('canvas'); RIB.width = 760; RIB.height = 110; const r = RIB.getContext('2d');
    const x0 = 30, x1 = 712, y0 = 21, y1 = 89;
    const g = r.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, '#2f7fd0'); g.addColorStop(.5, '#1f6cc0'); g.addColorStop(1, '#2a78c8');
    r.fillStyle = g; r.beginPath(); r.moveTo(x0 + 20, y0 + 3);
    for (let x = x0 + 20; x <= x1 - 15; x += 14) r.lineTo(x, y0 + Math.sin(x * .7) * 2.5);
    r.lineTo(x1, y0 + 12); r.lineTo(x1 + 8, y1 - 18); r.lineTo(x1 - 10, y1);
    for (let x = x1 - 10; x >= x0; x -= 14) r.lineTo(x, y1 + Math.cos(x * .5) * 2.5);
    r.lineTo(x0 - 6, y0 + 30); r.closePath(); r.fill();
    r.globalCompositeOperation = 'source-atop'; r.strokeStyle = 'rgba(10,40,90,.55)'; r.lineWidth = 1.4;
    for (let x = -100; x < 800; x += 5) { r.beginPath(); r.moveTo(x, y1 + 4); r.lineTo(x + 40, y0 - 4); r.stroke(); }
    r.strokeStyle = 'rgba(180,215,255,.35)'; for (let x = -98; x < 800; x += 11) { r.beginPath(); r.moveTo(x, y1 + 4); r.lineTo(x + 40, y0 - 4); r.stroke(); }
    // feathered ends like a dry brush
    r.globalCompositeOperation = 'destination-out';
    for (const [xa, xb] of [[0, x0 + 70], [x1 + 20, x1 - 60]]) { const f = r.createLinearGradient(xa, 0, xb, 0); f.addColorStop(0, 'rgba(0,0,0,1)'); f.addColorStop(1, 'rgba(0,0,0,0)'); r.fillStyle = f; r.fillRect(Math.min(xa, xb), 0, Math.abs(xb - xa), 110); }
  }
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,.35)'; ctx.shadowBlur = 8; ctx.drawImage(RIB, 188, 1044); ctx.restore();
  ink(S.ribbon || 'دعاء يوم الثلاثاء', 'Kufam', 105, 565, 1036, '#ffffff', { alpha: a, blur: 6, w: 460, style: '400', outline: 'rgba(15,30,60,.95)', ow: 5 });
}
// ---- measured elements from agent/mimic (spec.elements): exact fonts or traced shapes, drawn on every frame ----
let PATHS = null;
function elements(t) {
  const E = S.elements || []; if (!E.length) return;
  if (!PATHS) PATHS = E.map(e => e.kind === 'traced' ? new Path2D(e.path) : null);
  E.forEach((e, i) => {
    const a = (e.from != null ? seg(t, e.from, e.from + (e.fade ?? .3)) : seg(t, 0.05, 0.55)) * (e.to != null ? 1 - seg(t, e.to - (e.fade ?? .3), e.to) : 1);
    if (a <= 0) return;
    if (e.kind === 'traced') {
      ctx.save(); ctx.globalAlpha = a; ctx.lineJoin = 'round';
      if (e.pop && e.from != null && e.box) {      // enters a little larger and settles (e.pop = extra scale at the start)
        const z = 1 + e.pop * (1 - Math.pow(seg(t, e.from, e.from + (e.popT ?? 0.45)), 0.6)), cx = (e.box[0] + e.box[2]) / 2, cy = (e.box[1] + e.box[3]) / 2;
        ctx.translate(cx, cy); ctx.scale(z, z); ctx.translate(-cx, -cy);
      }
      if (e.shadow) { ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 2; }
      if (e.outline) { ctx.lineWidth = (e.outline_px || 2) * 2; ctx.strokeStyle = e.outline; ctx.stroke(PATHS[i]); ctx.shadowColor = 'transparent'; }
      ctx.fillStyle = e.fill; ctx.fill(PATHS[i], 'evenodd'); ctx.restore();
    } else {
      ink(e.text, 'EL' + i, e.h, e.cx, e.top, e.fill, { alpha: a, ltr: e.ltr, w: e.w, style: String(e.weight || ''),
        outline: e.outline, ow: (e.outline_px || 0) * 2, blur: e.shadow ? 8 : 0, shadow: e.shadow ? 'rgba(0,0,0,.6)' : 'transparent' });
    }
  });
}
let LINE = null;
function line(text, a, o = {}) {
  if (a <= 0 && !o.wipe) return;
  const st = S.line ? { ...STY[S.style], ...S.line, font: S.line.font ? 'LINEF' : STY[S.style].font } : STY[S.style];
  if (!LINE) {
    ctx.save(); ctx.direction = 'rtl'; ctx.font = `100px ${st.font}`; const m = ctx.measureText(st.ref); ctx.restore();
    const k = st.h / (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
    LINE = { px: 100 * k, base: st.top + m.actualBoundingBoxAscent * k, sx: st.w / ((m.actualBoundingBoxLeft + m.actualBoundingBoxRight) * k) };
  }
  ctx.save(); ctx.globalAlpha = a; ctx.direction = 'rtl'; ctx.textAlign = 'center';
  ctx.font = `${LINE.px.toFixed(1)}px ${st.font}`;
  const w = ctx.measureText(text).width * LINE.sx, fk = w > st.maxw ? st.maxw / w : 1;
  const z = (o.big || 1) * (o.pop ?? 1), mid = LINE.base - 0.3 * LINE.px;
  if (o.wipe != null) { const ww = (w * fk * z) + 40, x0 = st.cx - ww / 2; ctx.beginPath(); ctx.rect(x0 + ww * o.wipe, 0, ww, H); ctx.clip(); }
  ctx.translate(st.cx, mid); ctx.scale(LINE.sx * fk * z, fk * z); ctx.translate(-st.cx, -mid);
  ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 2; ctx.fillStyle = '#fff';
  ctx.fillText(text, st.cx, LINE.base); ctx.restore();
}
function handle(a) {
  if (S.handleSpaced) {   // letters set one by one at measured x (e.g. «@ D X H M E N»): {text, xs:[..] or x0/x1, y, size, font, alpha}
    const h = S.handleSpaced, t = [...(h.text || S.handle || '@elkosif').toUpperCase()];
    const xs = h.xs || t.map((_, i) => i === 0 ? h.at : h.x0 + (h.x1 - h.x0) * (i - 1) / Math.max(1, t.length - 2));
    ctx.save(); ctx.globalAlpha = a * (h.alpha ?? 0.9); ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = h.fill || '#fff';
    ctx.shadowColor = 'rgba(0,0,0,.45)'; ctx.shadowBlur = 3; ctx.font = `${h.weight || 400} ${h.size}px ${h.font || 'PlexSerifB'}`;
    t.forEach((c, i) => ctx.fillText(c, xs[i], h.y)); ctx.restore(); return;
  }
  if (S.noHandle) return;
  ctx.save(); ctx.globalAlpha = a * .9; ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 4; ctx.fillStyle = '#fff';
  if (S.style === 'dxh') { ctx.font = '600 25px PlexSerifB'; ctx.letterSpacing = '7px'; ctx.fillText((S.handle || '@elkosif').toUpperCase(), 543, 1100); }
  else if (S.style === 'oaun') { ctx.font = '44px PlexSerifB'; ctx.fillText((S.handle || '@elkosif').toUpperCase(), 540, 1128); }
  else { ctx.font = 'italic 27px PlexSerifI'; ctx.fillStyle = 'rgba(235,235,235,.85)'; ctx.fillText(S.handle || '@elkosif', 540, 1100); }
  ctx.restore();
}
window.renderFrame = async function (fr) {
  const t = fr / FPS;
  let i = 0; while (i + 1 < S.scenes.length && t >= S.scenes[i + 1].a) i++;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  await footage(i, t);
  if (S.style === 'day') dayHeader(seg(t, 0.05, 0.55));
  if (S.style === 'oaun' && !S.noHeader) oaunHeader(seg(t, 0.05, 0.55));
  elements(t);
  if (S.overlay) {   // text lifted from the reference pixel for pixel (agent/mimic/lift.py render): one RGBA frame per video frame
    const ov = await img(`ov/f${String(fr + 1).padStart(4, '0')}.png`); if (ov) ctx.drawImage(ov, 0, 0, W, H);
  }
  if (S.style === 'adeiat') {
    hijriBlock(seg(t, 0, 0.4)); dayBlock(seg(t, 0, 0.4)); ribbon(seg(t, 0, 0.4));
    const cap = S.dua_gate.captions.find(c => t >= c.start && t < c.end);
    if (cap) { const j = S.dua_gate.captions.indexOf(cap), big = S.lines[j][2] === 'big' ? 1.75 : 1;
      const fade = Math.min(.15, (cap.end-cap.start)/2);
      const ain = seg(t,cap.start,cap.start+fade);
      line(cap.text, Math.min(ain,1-seg(t,cap.end-fade,cap.end)), {big,pop:.72+.28*(1-Math.pow(1-ain,3))}); }
    return true;
  }
  if (S.sticker_from != null) sabah(seg(t, S.sticker_from, S.sticker_from + 0.35));
  const cap = S.dua_gate.captions.find(c => t >= c.start && t < c.end);
  if (cap) { const fade = Math.min(.15,(cap.end-cap.start)/2);
    line(cap.text, Math.min(seg(t,cap.start,cap.start+fade),1-seg(t,cap.end-fade,cap.end))); }
  handle(1);
  return true;
};
(async () => {
  S = await (await fetch('spec.json')).json(); C = await (await fetch('clips.json')).json();
  if (S.line && S.line.font) { const f = new FontFace('LINEF', `url(fonts/${S.line.font.split(/[\\/]/).pop()})`); await f.load(); document.fonts.add(f); }
  await Promise.all((S.elements || []).map(async (e, i) => {      // fonts picked by mimic, copied into fonts/ by make.sh
    if (e.kind !== 'text' || !e.font) return;
    const f = new FontFace('EL' + i, `url(fonts/${e.font.split(/[\\/]/).pop()})`); await f.load(); document.fonts.add(f);
  }));
  window.FRAMES = Math.round(S.dur * FPS);
  await Promise.all(['AmiriB', 'Diwani', 'PlexSerifB', 'PlexSerifI', 'Panorama', 'Sultan', 'AlmaraiXB', 'TajawalM', 'Kufam'].map(f => document.fonts.load(`80px ${f}`, 'صباح ABC')));   // missing font must stop the render
  await document.fonts.ready; window.ready = true;
})();
