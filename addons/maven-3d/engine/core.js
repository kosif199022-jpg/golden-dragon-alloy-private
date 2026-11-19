// Maven 3D core: renderer, post, sky/time-of-day, camera moves, captions, the shot runner.
// Every frame is a pure function of time: window.seek(t). Import from your story.js.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
export { THREE, RoundedBoxGeometry };

export const W = 1080, H = 1920;
await Promise.all([document.fonts.load('800 84px Pop'), document.fonts.load('400 104px Ar')]).catch(() => { });
export const CFG = await (await fetch('config.json').catch(() => null))?.json().catch(() => ({})) || {};
const TFILE = new URLSearchParams(location.search).get('timing') || 'timing.json';
export const TM = await fetch(TFILE).then(r => r.ok ? r.json() : { words: [['', 0, .1]] }).catch(() => ({ words: [['', 0, .1]] }));
export const WD = TM.words;                                // [[word, start, end], ...] in script spelling
export const LANG = CFG.lang || TM.lang || 'en';
export const ws = i => WD[Math.min(i, WD.length - 1)][1];  // start of word i
export const we = i => WD[Math.min(i, WD.length - 1)][2];  // end of word i
export const C = i => ws(i) - .04;                          // a cut lands 40 ms before word i
// find a word index by text (n-th occurrence), so shots survive script edits: wi('dragon'), wi('dragon', 2)
const norm = s => s.toLowerCase().replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/[^\p{L}\p{N}]/gu, '');
export function wi(word, n = 1) { const k = norm(word); let c = 0; for (let i = 0; i < WD.length; i++) if (norm(WD[i][0]) === k && ++c === n) return i; throw new Error('word not in timing: ' + word); }

// ---------- helpers ----------
let _seed = 7;
export const seed = s => { _seed = s; };
export const rnd = () => { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; };
export const R = (a, b) => a + (b - a) * rnd();
export const pick = a => a[Math.floor(rnd() * a.length)];
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, k) => a + (b - a) * k;
export const eio = k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
export const eo = k => 1 - Math.pow(1 - k, 3);
export const ei = k => k * k * k;
export const V = (x, y, z) => new THREE.Vector3(x, y, z);
export const lerpV = (a, b, k) => V(lerp(a.x, b.x, k), lerp(a.y, b.y, k), lerp(a.z, b.z, k));
export const hash = n => { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); };
export function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat, repeat); }
  return t;
}
export const mat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: .62, metalness: 0, ...o });
export const glow = (c, i = 3) => new THREE.MeshStandardMaterial({ color: '#000', emissive: c, emissiveIntensity: i });
const sh = m => { m.castShadow = m.receiveShadow = true; return m; };
export const box = (w, h, d, m) => sh(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m));
export const rbox = (w, h, d, r, m) => sh(new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, r), m));
export const cyl = (rt, rb, h, m, seg = 24) => sh(new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), m));
export const ball = (r, m, d = 1) => sh(new THREE.Mesh(new THREE.IcosahedronGeometry(r, d), m));
export const at = (o, x, y, z) => { o.position.set(x, y, z); return o; };
export const group = (...kids) => { const g = new THREE.Group(); kids.forEach(k => g.add(k)); return g; };

// ---------- renderer + post ----------
export const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gl'), antialias: true, preserveDrawingBuffer: true });
renderer.setSize(W, H, false); renderer.setPixelRatio(1);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
export const scene = new THREE.Scene();
export const camera = new THREE.PerspectiveCamera(40, W / H, .1, 4000);
const rt = new THREE.WebGLRenderTarget(W, H, { samples: 4, type: THREE.HalfFloatType });
export const composer = new EffectComposer(renderer, rt);
composer.addPass(new RenderPass(scene, camera));
export const bokeh = new BokehPass(scene, camera, { focus: 10, aperture: .002, maxblur: .012 }); composer.addPass(bokeh);
export const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), .45, .55, .86); composer.addPass(bloom);
composer.addPass(new OutputPass());
export const grade = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, sat: { value: 1.25 }, con: { value: 1.08 }, tint: { value: new THREE.Vector3(1, 1, 1) }, vig: { value: .28 }, flash: { value: 0 }, flashCol: { value: new THREE.Vector3(.75, .7, 1) } },
  vertexShader: 'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader: `uniform sampler2D tDiffuse;uniform float sat,con,vig,flash;uniform vec3 tint,flashCol;varying vec2 vUv;
  void main(){vec3 c=texture2D(tDiffuse,vUv).rgb;float l=dot(c,vec3(.299,.587,.114));c=mix(vec3(l),c,sat);c=(c-.5)*con+.5;c*=tint;
  vec2 d=vUv-.5;d.x*=.62;c*=1.-vig*smoothstep(.18,.62,length(d));c+=flash*flashCol;gl_FragColor=vec4(clamp(c,0.,1.),1.);}`
});
composer.addPass(grade);
export function dof(focus, aperture = .004, maxblur = .012) { bokeh.uniforms.focus.value = focus; bokeh.uniforms.aperture.value = aperture; bokeh.uniforms.maxblur.value = maxblur; }
export function gradeSet(sat = 1.25, con = 1.08, tint = [1, 1, 1], vig = .28) { grade.uniforms.sat.value = sat; grade.uniforms.con.value = con; grade.uniforms.tint.value.set(...tint); grade.uniforms.vig.value = vig; }
export function flash(v, col = [.75, .7, 1]) { grade.uniforms.flash.value = Math.max(grade.uniforms.flash.value, v); grade.uniforms.flashCol.value.set(...col); }

// ---------- sky + time of day ----------
const skyU = { top: { value: new THREE.Color() }, hor: { value: new THREE.Color() }, sunDir: { value: V(0, 1, 0) }, sunCol: { value: new THREE.Color() }, stars: { value: 0 } };
export const sky = new THREE.Mesh(new THREE.SphereGeometry(2000, 32, 16), new THREE.ShaderMaterial({
  uniforms: skyU, side: THREE.BackSide, depthWrite: false, fog: false,
  vertexShader: 'varying vec3 vP;void main(){vP=normalize(position);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader: `uniform vec3 top,hor,sunCol,sunDir;uniform float stars;varying vec3 vP;
  float h3(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
  void main(){float h=clamp(vP.y,0.,1.);vec3 c=mix(hor,top,pow(h,.55));float s=max(dot(normalize(vP),normalize(sunDir)),0.);
  c+=sunCol*(pow(s,400.)*3.+pow(s,12.)*.35);vec3 q=floor(vP*260.);float st=step(.9975,h3(q))*smoothstep(.05,.4,vP.y);c+=vec3(st)*stars;gl_FragColor=vec4(c,1.);}`
}));
scene.add(sky);
export const hemi = new THREE.HemisphereLight(0xbfe3ff, 0x6a8f3a, 1.2); scene.add(hemi);
export const sun = new THREE.DirectionalLight(0xffffff, 3); sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096); Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70, near: 1, far: 500 });
sun.shadow.bias = -.0004; sun.shadow.normalBias = .04; scene.add(sun, sun.target);
scene.fog = new THREE.Fog(0x9fd8ff, 160, 900);
// presets: add your own with TOD.name = {...}
export const TOD = {
  day: { top: '#1d63d8', hor: '#a8dcff', sun: '#ffffff', si: 3.1, sd: [.45, .8, .35], hs: '#cfe8ff', hg: '#6f9a40', hi: 1.25, fog: '#b7e2ff', fn: 160, ff: 900, exp: 1.05, cloud: '#ffffff', stars: 0 },
  golden: { top: '#3f6cc4', hor: '#ffc38a', sun: '#ffb46a', si: 2.6, sd: [-.15, .22, -.95], hs: '#ffd7b0', hg: '#6a7a40', hi: 1.0, fog: '#ffcf9e', fn: 160, ff: 900, exp: 1.08, cloud: '#ffe2c8', stars: 0 },
  sunset: { top: '#2b2f7a', hor: '#ff7b4a', sun: '#ff8a3d', si: 2.2, sd: [.9, .12, -.3], hs: '#ffb48a', hg: '#4a3a40', hi: .9, fog: '#ff9a6a', fn: 140, ff: 800, exp: 1.1, cloud: '#ffb0a0', stars: .2 },
  night: { top: '#1b1240', hor: '#6a548f', sun: '#b4a8ff', si: 2.2, sd: [.25, .5, .8], hs: '#9a88e0', hg: '#3a3358', hi: 1.7, fog: '#4a3d6e', fn: 120, ff: 800, exp: 1.35, cloud: '#5a4c78', stars: 1 },
  spooky: { top: '#0d1418', hor: '#3c5a5a', sun: '#9fe0d0', si: 1.4, sd: [-.3, .6, .5], hs: '#6fa8a0', hg: '#1a2420', hi: 1.3, fog: '#2c4444', fn: 15, ff: 140, exp: 1.3, cloud: '#3a4a4a', stars: .4 },
  ice: { top: '#1a1060', hor: '#7a6ad8', sun: '#cfe6ff', si: 2.4, sd: [.3, .7, .4], hs: '#a8c8ff', hg: '#c8d8ff', hi: 1.6, fog: '#8a90e0', fn: 120, ff: 900, exp: 1.2, cloud: '#c0c8ff', stars: .8 },
  storm: { top: '#20242c', hor: '#5a6070', sun: '#c8d0e0', si: 1.2, sd: [.2, .7, .3], hs: '#8890a0', hg: '#30343a', hi: 1.4, fog: '#4a505c', fn: 60, ff: 500, exp: 1.25, cloud: '#4a5060', stars: 0 },
  indoor: { top: '#c9b8a0', hor: '#f0e0c8', sun: '#fff1d8', si: 2.4, sd: [.5, .8, .6], hs: '#fff3e0', hg: '#a08870', hi: 1.5, fog: '#f0e0c8', fn: 200, ff: 1200, exp: 1.1, cloud: '#ffffff', stars: 0 },
};
export const cloudMat = new THREE.SpriteMaterial({ transparent: true, depthWrite: false, fog: false });
export function setTOD(a, b, k = 0) {
  const A = TOD[a], B = TOD[b || a], c = (p, q) => new THREE.Color(p).lerp(new THREE.Color(q), k), L = (p, q) => lerp(p, q, k);
  skyU.top.value.copy(c(A.top, B.top)); skyU.hor.value.copy(c(A.hor, B.hor)); skyU.stars.value = L(A.stars, B.stars);
  const sd = V(L(A.sd[0], B.sd[0]), L(A.sd[1], B.sd[1]), L(A.sd[2], B.sd[2])).normalize();
  skyU.sunDir.value.copy(sd); skyU.sunCol.value.copy(c(A.sun, B.sun)).multiplyScalar(L(A.si, B.si) / 3);
  sun.color.copy(c(A.sun, B.sun)); sun.intensity = L(A.si, B.si); sun.position.copy(sd.clone().multiplyScalar(250)).add(SC); sun.target.position.copy(SC);
  hemi.color.copy(c(A.hs, B.hs)); hemi.groundColor.copy(c(A.hg, B.hg)); hemi.intensity = L(A.hi, B.hi);
  scene.fog.color.copy(c(A.fog, B.fog)); scene.fog.near = L(A.fn, B.fn); scene.fog.far = L(A.ff, B.ff);
  renderer.toneMappingExposure = L(A.exp, B.exp); cloudMat.color.copy(c(A.cloud, B.cloud));
}
// move the shadow box to where the action is (sets far from the origin)
const SC = V(0, 0, 0);
export function shadowAt(x, z, size = 70) { const s = sun.shadow.camera; s.left = s.bottom = -size; s.right = s.top = size; s.updateProjectionMatrix(); const d = sun.position.clone().sub(SC); SC.set(x, 0, z); sun.position.copy(SC).add(d); sun.target.position.copy(SC); }
const FOLLOW = []; export const followCam = o => FOLLOW.push(o);

// ---------- camera ----------
export function look(p, tgt, fov = 40, roll = 0) { camera.position.copy(p); camera.up.set(0, 1, 0); camera.lookAt(tgt); camera.fov = fov; if (roll) camera.rotateZ(roll); }
export const handheld = (t, a = 1) => V(Math.sin(t * 1.7) * .05 + Math.sin(t * 3.1) * .03, Math.sin(t * 2.3) * .04 + Math.sin(t * 4.3) * .015, Math.sin(t * 1.3) * .03).multiplyScalar(a);
// ready-made moves; u is the shot's 0..1 progress
export const CAM = {
  push: (u, from, to, tgt, fov = 40, ease = eo) => look(lerpV(from, to, ease(u)), tgt, fov),
  dolly: (u, from, to, tgtFrom, tgtTo, fov = 40, ease = eio) => look(lerpV(from, to, ease(u)), lerpV(tgtFrom, tgtTo, ease(u)), fov),
  orbit: (u, c, r, a0, a1, y, tgtY = c.y, fov = 40) => { const a = lerp(a0, a1, eio(u)); look(V(c.x + Math.sin(a) * r, y, c.z + Math.cos(a) * r), V(c.x, tgtY, c.z), fov); },
  tiltUp: (u, p, tgtFrom, tgtTo, fov = 50) => look(p, lerpV(tgtFrom, tgtTo, eio(u)), fov),
  punch: (u, face, dist0 = 5.6, dist1 = 4.2, side = .3, fov0 = 36, fov1 = 30) => { const k = eo(u); look(V(face.x + side, face.y - .9, face.z + lerp(dist0, dist1, k)), face, lerp(fov0, fov1, k)); },
  follow: (u, who, back = 7, up = 3, ahead = 6) => { const p = who.position, a = who.rotation.y; look(V(p.x - Math.sin(a) * back, p.y + up, p.z - Math.cos(a) * back), V(p.x + Math.sin(a) * ahead, p.y + 3, p.z + Math.cos(a) * ahead), 46); },
  fly: (u, from, to, tgtFrom, tgtTo, fov = 46) => look(lerpV(from, to, eio(u)), lerpV(tgtFrom, tgtTo, eio(u)), fov, .05 - .1 * u),
};
export const faceOf = (a, dy = 4.7) => V(a.position.x, a.position.y + dy * a.scale.y, a.position.z);

// ---------- captions ----------
const CAPSTYLE = Object.assign({ en: { font: '800 84px Pop', y: 1318, fill: '#fff59d', stroke: '#0d0a10', lw: 17 }, ar: { font: '400 104px Ar', y: 1330, fill: '#fff59d', stroke: '#0d0a10', lw: 18 } }, CFG.captions || {});
function chunks() {
  const out = [], ar = LANG === 'ar', short = w => w.replace(/[^\p{L}\p{N}]/gu, '').length <= (ar ? 2 : 2);
  let i = 0;
  while (i < WD.length) {
    let txt = WD[i][0], st = WD[i][1];
    if (ar) { while (short(WD[i][0]) && i + 1 < WD.length) { i++; txt += ' ' + WD[i][0]; } }   // Arabic: a short word joins the next (في، من، يا)
    else { if (i === 0 && WD.length > 1 && short(WD[1][0]) === false && /^in$/i.test(WD[0][0])) { i++; txt += ' ' + WD[i][0]; }
      while (i + 1 < WD.length && short(WD[i + 1][0])) { i++; txt += ' ' + WD[i][0]; } }   // English: a short word joins the previous (for a, it too)
    out.push([txt, st]); i++;
  }
  for (let k = 0; k < out.length; k++) out[k][2] = k + 1 < out.length ? out[k + 1][1] : WD.at(-1)[2] + .6;
  return out;
}
export const CH = chunks();
const out = document.getElementById('c'), cx = out.getContext('2d');
export let captionsOn = CFG.captionsOn !== false;
function caption(t) {
  if (!captionsOn) return;
  const c = CH.find(c => t >= c[1] - .02 && t < c[2] - .02); if (!c) return;
  const S = CAPSTYLE[LANG] || CAPSTYLE.en; let s = c[0];
  if (LANG === 'en') s = s.replace(/^[A-Z][a-z]/, m => (CFG.keepCaps || []).some(k => s.startsWith(k)) || /^(In|I)\b/.test(s) ? m : m.toLowerCase());
  cx.font = S.font; cx.textAlign = 'center'; cx.textBaseline = 'alphabetic'; cx.lineJoin = 'round'; cx.direction = LANG === 'ar' ? 'rtl' : 'ltr';
  const k = clamp((t - c[1] + .02) / .06), sc = .9 + .1 * k, wmax = 960, m = cx.measureText(s).width, fit = Math.min(1, wmax / m);
  cx.save(); cx.translate(540, S.y); cx.scale(sc * fit, sc * fit);
  cx.shadowColor = 'rgba(0,0,0,.45)'; cx.shadowBlur = 10; cx.shadowOffsetY = 5; cx.strokeStyle = S.stroke; cx.lineWidth = S.lw; cx.strokeText(s, 0, 0);
  cx.shadowColor = 'transparent'; cx.fillStyle = S.fill; cx.fillText(s, 0, 0); cx.restore();
}
// extra 2D overlays per frame (titles, counters): overlay((ctx, t) => {...})
const OVER = []; export const overlay = f => OVER.push(f);

// ---------- the runner ----------
// shots: [[start, end, (t, u) => {...}], ...]; resets: called every frame before the shot (hide things)
const RESET = []; export const onReset = f => RESET.push(f);
const EXTRAS = []; export const extras = list => EXTRAS.push(...list);   // things the camera must not pass through
export function run(SHOTS, opt = {}) {
  const END = opt.end || Math.ceil((WD.at(-1)[2] + (opt.tail ?? 1.0)) * 4) / 4; window.END = END;
  const WHIP = opt.whip ?? .085, AMT = opt.whipAmount ?? .22; SHOTS.forEach(s => { s[1] = Math.min(s[1], END); });
  window.SHOTLIST = SHOTS.map(s => [+s[0].toFixed(2), +s[1].toFixed(2)]);
  window.seek = (t) => {
    grade.uniforms.flash.value = 0; shadowAt(0, 0, 70); RESET.forEach(f => f(t));
    const n = SHOTS.findIndex(s => t >= s[0] && t < s[1]); const i = n < 0 ? SHOTS.length - 1 : n, [a, b, fn] = SHOTS[i];
    fn(t, clamp((t - a) / (b - a)));
    for (const c of EXTRAS) if (c.visible && Math.hypot(c.position.x - camera.position.x, c.position.z - camera.position.z) < 2.6 && camera.position.y < c.position.y + 7) c.visible = false;
    const dir = i % 2 ? 1 : -1, noWhip = opt.noWhip || [];
    if (i > 0 && t - a < WHIP && !noWhip.includes(i)) { const k = 1 - (t - a) / WHIP; camera.rotateY(dir * AMT * k * k); camera.rotateZ(dir * .05 * k); }
    if (i < SHOTS.length - 1 && b - t < WHIP && !noWhip.includes(i + 1)) { const k = 1 - (b - t) / WHIP; camera.rotateY(-dir * AMT * k * k); }
    sky.position.copy(camera.position); FOLLOW.forEach(o => o.position.set(camera.position.x, 0, camera.position.z));
    camera.updateProjectionMatrix(); composer.render();
    cx.clearRect(0, 0, W, H); cx.drawImage(renderer.domElement, 0, 0); OVER.forEach(f => f(cx, t)); caption(t);
  };
  Promise.all([document.fonts.load('800 84px Pop'), document.fonts.load('400 104px Ar')]).then(() => { window.seek(0); window.READY = true; });
}
window.DBG = { THREE, scene, camera, renderer, composer };
