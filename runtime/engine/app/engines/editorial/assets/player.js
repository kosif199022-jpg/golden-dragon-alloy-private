// Black Dragon editorial player: one EDL (window.EDL) -> a seekable film page, window.__kosif = { duration, seek(t) }.
// Wires the layer modules (engine, picture, captions, typeLayers, split-layout) that build.py inlines before this file.
// Every frame is a pure function of programme time t: shot -> comp canvas -> WebGL post (grain, bloom, grade) -> DOM type.
//
// EDL: { meta: { width, height, fps, duration, fx, typeDefaults, capY },
//        shots: [{ t0, t1, kind: 'presenter'|'insert', source, camera, fx, capY, split: { at, dir, entry, a, b } }],
//        captions: { size, chunks }, type: [layer, ...] }
// source: { type: 'color', color } | { type: 'image', src } | { type: 'frames', dir, count, fps, in }
// camera: { zoom, cx, cy, fy } (numbers or key tracks [[t, v, ease], ...] in programme time); fx values may be tracks too.
const EDL = window.EDL;
const M = EDL.meta;
const W = M.width, H = M.height, FPS = M.fps || 25;
const val = (v, t) => (Array.isArray(v) && Array.isArray(v[0]) ? sample(v, t) : v);

const stage = document.getElementById('stage');
stage.style.setProperty('--stage-w', `${W}px`);
stage.style.setProperty('--stage-h', `${H}px`);
Object.assign(stage.style, { width: `${W}px`, height: `${H}px` });
applyFontTokens();
const out = document.createElement('canvas');
out.width = W; out.height = H;
stage.appendChild(out);
const plane = () => { const p = document.createElement('div'); p.className = 'plane'; Object.assign(p.style, { width: `${W}px`, height: `${H}px` }); stage.appendChild(p); return p; };
const pic = new Picture(out);
const capPlane = plane(), typePlane = plane();
const types = new TypeLayers(typePlane, EDL.type || [], [W, H], M.typeDefaults || {});
const shots = EDL.shots;
const shotAt = t => shots.find(s => t >= s.t0 && t < s.t1) || shots[shots.length - 1];
let caps = null;

// ── media: still images are loaded once; frame sequences on demand (a small cache keeps memory flat)
const stillCache = new Map(), frameCache = new Map();
function image(src, cache = stillCache, limit = Infinity) {
  if (!cache.has(src)) {
    cache.set(src, new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(new Error(`media failed: ${src}`)); im.src = src; }));
    if (cache.size > limit) cache.delete(cache.keys().next().value);
  }
  return cache.get(src);
}
function frameSrc(src, shot, t) {
  const i = clamp(Math.round((t - shot.t0 + (src.in || 0)) * (src.fps || FPS)), 0, src.count - 1);
  return `${src.dir}/${String(i + 1).padStart(5, '0')}.jpg`;
}
async function drawSource(g, src, shot, cam, r, t) {
  if (!src || src.type === 'color') { g.fillStyle = (src && src.color) || '#0b0b0d'; g.fillRect(r.x, r.y, r.w, r.h); return; }
  const im = await (src.type === 'frames' ? image(frameSrc(src, shot, t), frameCache, 48) : image(src.src));
  const SW = im.naturalWidth, SH = im.naturalHeight;
  const c = { w: r.w, h: r.h, zoom: val(cam.zoom ?? 1, t), fy: val(cam.fy ?? 0.5, t), ax: 1 };
  const crop = cropFor(c, [t, val(cam.cx ?? 0.5, t), val(cam.cy ?? 0.5, t)], SW, SH);   // never stretches: cover crop
  g.drawImage(im, crop.sx, crop.sy, crop.sw, crop.sh, r.x, r.y, r.w, r.h);
}

// ── fx: meta.fx under shot.fx; a presenter shot stays clean (no film look, grain only via grainOut)
function fxAt(shot, t, layout) {
  const fx = {};
  for (const [k, v] of Object.entries({ ...(M.fx || {}), ...(shot.fx || {}) })) fx[k] = val(v, t);
  if (layout) fx.grainRect = fx.grainRect || layout.grainRect;
  else if (shot.kind === 'presenter' && !fx.grainRect) fx.grainRect = [0, 0, 0, 0];
  return fx;
}

async function frame(t) {
  const shot = shotAt(t), g = pic.ctx, full = { x: 0, y: 0, w: W, h: H };
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = '#0b0b0d'; g.fillRect(0, 0, W, H);
  let layout = null;
  if (shot.split) {
    layout = splitLayout(shot, t, full);
    for (const [side, r] of [['a', layout.a], ['b', layout.b]]) {
      const p = shot.split[side];
      g.save(); g.beginPath(); g.rect(r.x, r.y, r.w, r.h); g.clip();
      await drawSource(g, p.source, shot, p.camera || {}, r, t);
      g.restore();
    }
  } else {
    await drawSource(g, shot.source, shot, shot.camera || {}, full, t);
  }
  pic.post(t, fxAt(shot, t, layout), FPS);
  if (caps) {
    caps.update(t);
    const c = caps.cur;   // Arabic captions read right to left: the justified line lays its words out from the right
    caps.el.dir = c && c.words.some(w => /[\u0590-\u08FF]/.test(w.w)) ? 'rtl' : 'ltr';
  }
  types.update(t, layout ? layout.typeMotion : null);
}

const stills = shots.flatMap(s => [s.source, s.split && s.split.a.source, s.split && s.split.b.source]).filter(s => s && s.type === 'image').map(s => image(s.src));
window.__kosifReady = Promise.all(stills).then(() => document.fonts.ready).then(() => {
  // captions measure their words with the real fonts, so they are built once the fonts are in
  if (EDL.captions) { caps = new Captions(capPlane, EDL.captions, W, H); caps.yAt = t => shotAt(t).capY ?? M.capY ?? H * 0.68; }
  return frame(0);
});
window.__kosif = { duration: M.duration, seek: async t => { await window.__kosifReady; await frame(t); } };
