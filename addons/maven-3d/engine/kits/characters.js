// Characters: classic blocky avatars (head 1/4 of height, 2x2 torso, 1x2 limbs, no hands/feet),
// flat cartoon face decals that swap instantly, hair meshes, outfits, accessories, poses, walk/run.
import { THREE, RoundedBoxGeometry, canvasTex, mat, glow, rbox, box, cyl, ball, at, rnd, pick, R, seed, scene, extras, hash } from '../core.js';

// ---------- faces (draw on a 512 canvas; the head front is 1.3 x 1.3 units) ----------
const K = '#141018', EL = 176, ER = 336, EY = 250;
function brow(g, y1, y2, y3, y4, w = 16) { g.strokeStyle = K; g.lineWidth = w; g.beginPath(); g.moveTo(EL - 50, y1); g.lineTo(EL + 40, y2); g.stroke(); g.beginPath(); g.moveTo(ER - 40, y3); g.lineTo(ER + 50, y4); g.stroke(); }
function dots(g, dy = 0) { for (const x of [EL, ER]) { g.fillStyle = K; g.beginPath(); g.ellipse(x, EY + dy, 26, 40, 0, 0, 7); g.fill(); g.fillStyle = '#fff'; g.beginPath(); g.arc(x - 8, EY - 14 + dy, 9, 0, 7); g.fill(); } }
function bigEyes(g, pr = 16, rx = 70, ry = 82, px = 0, py = 0, lid = 0) { for (const x of [EL, ER]) { g.fillStyle = '#fff'; g.strokeStyle = K; g.lineWidth = 14; g.beginPath(); g.ellipse(x, EY, rx, ry, 0, 0, 7); g.fill(); g.stroke(); g.fillStyle = K; g.beginPath(); g.arc(x + (x < 256 ? 4 : -4) + px, EY + py, pr, 0, 7); g.fill(); if (lid) { g.fillStyle = K; g.beginPath(); g.ellipse(x, EY - ry + lid, rx + 6, lid, 0, Math.PI, 0); g.fill(); } } }
function closed(g, up = true) { g.strokeStyle = K; g.lineWidth = 16; for (const x of [EL, ER]) { g.beginPath(); up ? g.arc(x, EY + 18, 38, Math.PI * 1.15, Math.PI * 1.85) : g.arc(x, EY - 22, 38, Math.PI * .15, Math.PI * .85); g.stroke(); } }
function mouth(g, x, y, w, h, o = {}) {
  g.fillStyle = K; g.beginPath();
  if (o.trap) { g.moveTo(x - w * .38, y - h / 2); g.lineTo(x + w * .38, y - h / 2); g.lineTo(x + w / 2, y + h / 2); g.lineTo(x - w / 2, y + h / 2); g.closePath(); }
  else if (o.frown) { g.moveTo(x - w / 2, y + h * .4); g.quadraticCurveTo(x, y - h * .9, x + w / 2, y + h * .4); g.quadraticCurveTo(x, y - h * .1, x - w / 2, y + h * .4); }
  else { g.moveTo(x - w / 2, y - h * .25); g.quadraticCurveTo(x, y - h * .45, x + w / 2, y - h * .25); g.quadraticCurveTo(x + w / 2, y + h * .9, x, y + h * .7); g.quadraticCurveTo(x - w / 2, y + h * .9, x - w / 2, y - h * .25); }
  g.fill(); g.save(); g.clip();
  if (o.teeth !== false) { g.fillStyle = '#fff'; g.fillRect(x - w, y - h / 2 - 10, w * 2, h * .3); }
  if (o.tongue !== false) { g.fillStyle = '#e8455a'; g.beginPath(); g.ellipse(x, y + h * .55, w * .3, h * .3, 0, 0, 7); g.fill(); }
  g.restore();
}
const line = (g, pts, w = 16) => { g.strokeStyle = K; g.lineWidth = w; g.beginPath(); pts.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.stroke(); };
const arc = (g, x, y, r, a0, a1, w = 16) => { g.strokeStyle = K; g.lineWidth = w; g.beginPath(); g.arc(x, y, r, a0, a1); g.stroke(); };
export const FACE_DRAW = {
  smile: g => { dots(g); brow(g, 185, 178, 178, 185, 14); arc(g, 256, 330, 62, Math.PI * .15, Math.PI * .85); },
  neutral: g => { dots(g); brow(g, 182, 182, 182, 182, 14); line(g, [[210, 360], [302, 360]]); },
  grin: g => { closed(g, true); brow(g, 175, 160, 160, 175, 14); mouth(g, 256, 360, 170, 120); },
  joy: g => { bigEyes(g, 22, 62, 70); brow(g, 160, 140, 140, 160); mouth(g, 256, 365, 180, 130); },
  wish: g => { closed(g, false); brow(g, 190, 175, 175, 190, 14); arc(g, 256, 330, 55, Math.PI * .1, Math.PI * .9); },
  squeeze: g => { for (const [x, s] of [[EL, 1], [ER, -1]]) line(g, [[x - 40 * s, EY - 25], [x + 30 * s, EY], [x - 40 * s, EY + 25]]); brow(g, 200, 222, 222, 200, 18); mouth(g, 256, 365, 150, 90, { tongue: false }); },
  blow: g => { dots(g); brow(g, 180, 172, 172, 180, 14); g.fillStyle = K; g.beginPath(); g.ellipse(256, 350, 24, 30, 0, 0, 7); g.fill(); },
  shock: g => { bigEyes(g, 13, 72, 86, 0, -6); brow(g, 150, 128, 128, 150, 18); mouth(g, 256, 385, 150, 140, { trap: true }); },
  scared: g => { bigEyes(g, 12, 66, 78, 0, 6); brow(g, 168, 140, 140, 168, 16); line(g, [[196, 380], [226, 360], [256, 380], [286, 360], [316, 380]], 14); g.fillStyle = '#7fd3ff'; g.beginPath(); g.ellipse(404, 200, 16, 26, 0, 0, 7); g.fill(); },
  sad: g => { closed(g, false); brow(g, 168, 190, 190, 168, 16); arc(g, 256, 400, 52, Math.PI * 1.15, Math.PI * 1.85); },
  cry: g => { closed(g, false); brow(g, 165, 190, 190, 165, 16); mouth(g, 256, 380, 150, 90, { frown: true, teeth: false }); g.fillStyle = '#5fc8ff'; for (const x of [EL, ER]) { g.fillRect(x - 12, EY + 10, 24, 150); } },
  angry: g => { dots(g, 8); brow(g, 170, 210, 210, 170, 22); mouth(g, 256, 380, 140, 70, { trap: true, tongue: false }); },
  smirk: g => { dots(g); brow(g, 178, 180, 165, 180, 14); line(g, [[200, 360], [280, 358], [318, 330]]); },
  evil: g => { for (const [x, s] of [[EL, 1], [ER, -1]]) { g.fillStyle = K; g.beginPath(); g.moveTo(x - 50 * s, EY - 30); g.lineTo(x + 45 * s, EY + 5); g.lineTo(x - 30 * s, EY + 30); g.fill(); } mouth(g, 256, 360, 230, 100, { tongue: false }); },
  sleep: g => { line(g, [[EL - 40, EY], [EL + 40, EY]]); line(g, [[ER - 40, EY], [ER + 40, EY]]); g.fillStyle = K; g.beginPath(); g.ellipse(256, 360, 18, 22, 0, 0, 7); g.fill(); g.font = 'bold 70px sans-serif'; g.fillText('z', 400, 150); },
  wink: g => { const x = ER; arc(g, x, EY + 18, 38, Math.PI * 1.15, Math.PI * 1.85); g.fillStyle = K; g.beginPath(); g.ellipse(EL, EY, 26, 40, 0, 0, 7); g.fill(); brow(g, 180, 172, 160, 175, 14); mouth(g, 256, 350, 140, 90); },
  love: g => { for (const x of [EL, ER]) { g.fillStyle = '#ff3d6e'; g.beginPath(); g.moveTo(x, EY + 40); g.bezierCurveTo(x - 70, EY - 10, x - 30, EY - 60, x, EY - 25); g.bezierCurveTo(x + 30, EY - 60, x + 70, EY - 10, x, EY + 40); g.fill(); } mouth(g, 256, 360, 160, 110); },
  dizzy: g => { for (const x of [EL, ER]) { g.strokeStyle = K; g.lineWidth = 10; g.beginPath(); for (let a = 0; a < 14; a += .2) g.lineTo(x + Math.cos(a) * a * 4, EY + Math.sin(a) * a * 4); g.stroke(); } line(g, [[200, 370], [230, 355], [260, 370], [290, 355], [320, 370]], 12); },
  determined: g => { dots(g, 6); brow(g, 175, 200, 200, 175, 22); line(g, [[205, 368], [307, 362]], 18); },
  worried: g => { bigEyes(g, 16, 58, 66, 0, 4); brow(g, 178, 150, 150, 178, 16); arc(g, 256, 410, 50, Math.PI * 1.2, Math.PI * 1.8, 14); },
  blank: g => { },
};
export const FACES = {};
export function face(name) { if (!FACES[name]) FACES[name] = new THREE.MeshStandardMaterial({ map: canvasTex(512, 512, g => { g.lineCap = g.lineJoin = 'round'; (FACE_DRAW[name] || FACE_DRAW.smile)(g); }), transparent: true, roughness: .6, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }); return FACES[name]; }

// ---------- outfits (front texture of the torso) ----------
const star = (g, x, y, r1, r2, c) => { g.fillStyle = c; g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? r2 : r1; g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); } g.fill(); };
export const OUTFIT = {
  plain: () => { },
  hoodie: (g, o) => { g.fillStyle = o.dark; g.beginPath(); g.moveTo(60, 0); g.lineTo(128, 70); g.lineTo(196, 0); g.fill(); g.fillRect(64, 170, 128, 70); g.strokeStyle = '#fff'; g.lineWidth = 6; g.beginPath(); g.moveTo(108, 60); g.lineTo(104, 130); g.moveTo(148, 60); g.lineTo(152, 130); g.stroke(); if (o.logo !== false) star(g, 128, 125, 30, 13, o.logoCol || '#ffd23f'); },
  stripe: (g, o) => { g.fillStyle = o.dark; for (let y = 20; y < 256; y += 52) g.fillRect(0, y, 256, 24); },
  puffer: (g, o) => { g.strokeStyle = o.dark; g.lineWidth = 7; for (let y = 30; y < 256; y += 42) { g.beginPath(); g.moveTo(0, y); g.lineTo(256, y); g.stroke(); } g.fillStyle = o.dark; g.fillRect(124, 0, 8, 256); },
  tee: (g, o) => { g.fillStyle = o.dark; g.beginPath(); g.arc(128, 0, 46, 0, Math.PI); g.fill(); },
  overall: (g, o) => { g.fillStyle = o.dark; g.fillRect(40, 110, 176, 146); g.fillRect(52, 0, 26, 120); g.fillRect(178, 0, 26, 120); g.fillStyle = '#ffd23f'; g.beginPath(); g.arc(65, 118, 9, 0, 7); g.arc(191, 118, 9, 0, 7); g.fill(); },
  suit: (g, o) => { g.fillStyle = '#fff'; g.beginPath(); g.moveTo(80, 0); g.lineTo(128, 120); g.lineTo(176, 0); g.fill(); g.fillStyle = o.tie || '#d12a2a'; g.beginPath(); g.moveTo(118, 10); g.lineTo(138, 10); g.lineTo(144, 120); g.lineTo(128, 140); g.lineTo(112, 120); g.fill(); g.strokeStyle = o.dark; g.lineWidth = 8; g.beginPath(); g.moveTo(80, 0); g.lineTo(128, 150); g.lineTo(176, 0); g.stroke(); },
  dress: (g, o) => { g.fillStyle = o.dark; g.fillRect(0, 140, 256, 116); g.fillStyle = '#fff'; for (let x = 20; x < 256; x += 44) { g.beginPath(); g.arc(x, 200, 9, 0, 7); g.fill(); } },
  police: (g, o) => { g.fillStyle = o.dark; g.fillRect(0, 200, 256, 20); star(g, 70, 80, 26, 12, '#ffd23f'); g.fillStyle = '#e8eef8'; g.fillRect(150, 60, 60, 26); },
  doctor: (g) => { g.fillStyle = '#ffffff'; g.fillRect(0, 0, 256, 256); g.fillStyle = '#60a5fa'; g.beginPath(); g.moveTo(90, 0); g.lineTo(128, 70); g.lineTo(166, 0); g.fill(); g.fillStyle = '#e11d48'; g.fillRect(170, 70, 34, 10); g.fillRect(182, 58, 10, 34); },
  king: (g, o) => { g.fillStyle = o.dark; g.fillRect(100, 0, 56, 256); g.fillStyle = '#ffd23f'; for (let y = 20; y < 256; y += 40) { g.beginPath(); g.arc(128, y, 9, 0, 7); g.fill(); } g.fillStyle = '#fff'; g.fillRect(0, 0, 256, 24); },
  armor: (g) => { g.fillStyle = '#c8ccd4'; g.fillRect(0, 0, 256, 256); g.strokeStyle = '#7a808c'; g.lineWidth = 8; for (let y = 50; y < 256; y += 60) { g.beginPath(); g.moveTo(0, y); g.lineTo(256, y); g.stroke(); } star(g, 128, 110, 34, 15, '#d12a2a'); },
  pajamas: (g, o) => { g.fillStyle = o.dark; for (let i = 0; i < 18; i++) { star(g, (i * 53) % 256, (i * 97) % 256, 12, 5, o.dark); } },
  number: (g, o) => { g.fillStyle = o.dark; g.font = 'bold 150px sans-serif'; g.textAlign = 'center'; g.fillText(o.num || '10', 128, 190); },
};
function frontTex(o) { return canvasTex(256, 256, (g) => { g.fillStyle = o.shirt; g.fillRect(0, 0, 256, 256); (OUTFIT[o.kind] || OUTFIT.plain)(g, o); }); }

// ---------- hair ----------
export const HAIR = {
  none: () => { },
  buzz: (g, m) => g.add(at(rbox(1.42, .2, 1.36, .1, m), 0, 5.2, -.02)),
  swoop: (g, m) => {
    g.add(at(rbox(1.5, .85, .34, .14, m), 0, 4.95, -.58));
    for (const s of [-1, 1]) g.add(at(rbox(.22, .62, 1.25, .1, m), s * .72, 4.98, -.04));
    [[-.42, 5.13, .6, .5], [.05, 5.19, .64, .4], [.47, 5.1, .58, .3]].forEach(([x, y, z, r]) => { const f = rbox(.62, .34, .5, .14, m); at(f, x, y, z); f.rotation.set(.35, 0, r); g.add(f); });
  },
  pony: (g, m) => { g.add(at(rbox(1.5, 1.2, .34, .14, m), 0, 4.75, -.58)); g.add(at(rbox(.55, 1.2, .5, .22, m), 0, 4.4, -.92)); for (const s of [-1, 1]) g.add(at(rbox(.24, 1.0, 1.25, .1, m), s * .73, 4.8, -.04)); const b = rbox(1.46, .3, .4, .12, m); at(b, 0, 5.08, .55); b.rotation.x = .3; g.add(b); },
  long: (g, m) => { g.add(at(rbox(1.56, 2.0, .4, .16, m), 0, 4.35, -.56)); for (const s of [-1, 1]) g.add(at(rbox(.26, 1.9, 1.1, .12, m), s * .76, 4.4, -.1)); const b = rbox(1.48, .32, .36, .12, m); at(b, 0, 5.1, .56); b.rotation.x = .25; g.add(b); },
  bun: (g, m) => { g.add(at(rbox(1.5, .8, .34, .14, m), 0, 4.95, -.58)); g.add(at(ball(.42, m, 2), 0, 5.55, -.2)); for (const s of [-1, 1]) g.add(at(rbox(.22, .6, 1.2, .1, m), s * .72, 4.98, -.04)); },
  spiky: (g, m) => { for (let i = 0; i < 7; i++) { const c = new THREE.Mesh(new THREE.ConeGeometry(.28, .7, 5), m); c.castShadow = true; const a = i / 7 * Math.PI * 2; at(c, Math.cos(a) * .45, 5.5, Math.sin(a) * .42); c.rotation.set(Math.sin(a) * .5, 0, -Math.cos(a) * .5); g.add(c); } g.add(at(rbox(1.5, .7, .3, .12, m), 0, 5.0, -.6)); },
  curly: (g, m) => { for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2; at(g.add(ball(.32, m)).children.at(-1), Math.cos(a) * .66, 5.2 + Math.sin(i * 1.7) * .08, Math.sin(a) * .62 - .05); } },
  mohawk: (g, m) => { for (let i = 0; i < 5; i++) { const c = new THREE.Mesh(new THREE.ConeGeometry(.2, .8, 4), m); at(c, 0, 5.6, .5 - i * .28); c.rotation.x = -.3; g.add(c); } },
  bald: () => { },
};
const CAP = 'cap';
function hairMesh(style, col) { const m = mat(col, { roughness: .8 }), g = new THREE.Group(); if (!['none', 'bald', 'mohawk'].includes(style)) g.add(at(rbox(1.5, .46, 1.44, .2, m), 0, 5.2, 0)); (HAIR[style] || HAIR.swoop)(g, m); return g; }

// ---------- accessories (positions in avatar space; head pieces follow the head) ----------
export const ACC = {
  partyHat: (o = {}) => { const [c1, c2] = o.cols || ['#ff4d6d', '#ffd23f']; const t = canvasTex(128, 128, (g) => { g.fillStyle = c1; g.fillRect(0, 0, 128, 128); g.fillStyle = c2; for (let i = -4; i < 8; i++) { g.save(); g.translate(i * 22, 0); g.rotate(-.5); g.fillRect(0, 0, 9, 220); g.restore(); } }); const g = new THREE.Group(), c = new THREE.Mesh(new THREE.ConeGeometry(.42, 1.0, 24, 1, true), mat('#fff', { map: t, side: THREE.DoubleSide })); c.castShadow = true; c.position.y = .5; g.add(c, at(ball(.16, mat(c2), 2), 0, 1.02, 0)); g.position.set(.18, 5.38, 0); g.rotation.z = -.18; g.userData.head = true; return g; },
  crown: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#ffcc33', { metalness: .6, roughness: .3, emissive: '#5a3a00', emissiveIntensity: .3 }); g.add(at(cyl(.62, .62, .32, m, 24), 0, 0, 0)); for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2, s = new THREE.Mesh(new THREE.ConeGeometry(.14, .38, 4), m); at(s, Math.cos(a) * .55, .32, Math.sin(a) * .55); g.add(s); const j = ball(.07, mat(['#e11d48', '#2563eb', '#16a34a'][i % 3], { emissive: '#330', emissiveIntensity: .5 })); at(j, Math.cos(a) * .63, .02, Math.sin(a) * .63); g.add(j); } g.position.set(0, 5.55, 0); g.userData.head = true; return g; },
  cap: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#e11d48'); g.add(at(rbox(1.5, .42, 1.46, .2, m), 0, 0, 0), at(box(1.3, .08, .7, m), 0, -.16, .95)); g.position.set(0, 5.35, 0); g.userData.head = true; return g; },
  policeHat: (o = {}) => { const g = new THREE.Group(), m = mat('#1e2a4a'); g.add(at(cyl(.82, .72, .45, m), 0, .1, 0), at(box(1.3, .08, .6, mat('#111')), 0, -.1, .8), at(box(.3, .3, .05, mat('#ffd23f', { metalness: .5 })), 0, .12, .78)); g.position.set(0, 5.4, 0); g.userData.head = true; return g; },
  topHat: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#15151a'); g.add(at(cyl(.95, .95, .08, m), 0, 0, 0), at(cyl(.6, .62, 1.0, m), 0, .5, 0), at(cyl(.63, .63, .18, mat('#b91c1c')), 0, .14, 0)); g.position.set(0, 5.3, 0); g.userData.head = true; return g; },
  glasses: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#111'); for (const s of [-1, 1]) { const r = new THREE.Mesh(new THREE.TorusGeometry(.2, .04, 8, 20), m); at(r, s * .3, 4.92, .66); g.add(r); } g.add(at(box(.2, .04, .04, m), 0, 4.95, .66)); g.userData.head = true; return g; },
  shades: (o = {}) => { const g = new THREE.Group(), m = mat('#0a0a0f', { roughness: .15, metalness: .4 }); g.add(at(box(1.3, .3, .06, m), 0, 4.9, .67)); g.userData.head = true; return g; },
  beard: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#55504c', { roughness: .95 }); g.add(at(rbox(1.3, 1.2, .5, .22, m), 0, 4.15, .5)); for (const s of [-1, 1]) g.add(at(rbox(.3, .8, .9, .12, m), s * .62, 4.55, .2)); g.userData.head = true; return g; },
  mustache: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#2a1b14'); for (const s of [-1, 1]) { const p = rbox(.42, .14, .08, .05, m); at(p, s * .2, 4.48, .66); p.rotation.z = s * -.25; g.add(p); } g.userData.head = true; return g; },
  backpack: (o = {}) => { const g = new THREE.Group(), m = mat(o.col || '#d12a2a'); g.add(at(rbox(1.6, 1.8, .7, .15, m), 0, 3.0, -.85), at(cyl(.3, .3, 1.7, mat('#3a5a3a'), 12), 0, 4.0, -.95)); g.children[1].rotation.z = Math.PI / 2; return g; },
  cape: (o = {}) => { const g = new THREE.Group(), c = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 3.6, 1, 6), mat(o.col || '#b91c1c', { side: THREE.DoubleSide })); c.castShadow = true; at(c, 0, 2.3, -.56); c.rotation.x = .08; g.add(c); return g; },
  watch: (o = {}) => { const g = new THREE.Group(); g.add(at(box(1.02, .28, 1.02, mat('#222')), 0, -1.45, 0), at(box(.5, .22, .06, glow(o.col || '#3dff8a', 2)), 0, -1.45, .52)); g.userData.arm = 'L'; return g; },
  sword: (o = {}) => { const g = new THREE.Group(); g.add(at(box(.18, 2.6, .08, mat('#d8dde6', { metalness: .8, roughness: .2 })), 0, 1.5, 0), at(box(.8, .14, .2, mat('#8a5a2a')), 0, .2, 0), at(box(.16, .5, .16, mat('#5a3a1a')), 0, -.1, 0)); g.position.set(0, -1.9, .1); g.rotation.x = Math.PI / 2; g.userData.arm = 'R'; return g; },
  phone: (o = {}) => { const g = new THREE.Group(); g.add(at(box(.5, .9, .08, mat('#111')), 0, 0, 0), at(box(.42, .8, .02, glow('#7fd3ff', 1.2)), 0, 0, .05)); g.position.set(0, -1.9, .5); g.rotation.x = -.6; g.userData.arm = 'R'; return g; },
  wand: (o = {}) => { const g = new THREE.Group(); g.add(at(cyl(.05, .05, 1.4, mat('#3a2a1a'), 8), 0, .5, 0), at(ball(.14, glow(o.col || '#ffd36a', 4), 1), 0, 1.25, 0)); g.position.set(0, -1.9, .2); g.rotation.x = Math.PI / 2.4; g.userData.arm = 'R'; return g; },
};

// ---------- the avatar ----------
export const SKIN = ['#f3d6b4', '#e8b98c', '#c98b5a', '#8d5a3a', '#ffd9b8', '#f5cba0'];
export const SHIRT = ['#ff4d4d', '#ffd23f', '#4ade80', '#c084fc', '#fb923c', '#38bdf8', '#f472b6', '#ffffff', '#1f2937', '#2f7bff'];
export const PANTS = ['#3a3f58', '#1f2937', '#2563eb', '#6b4f3a', '#14532d'];
export const HAIRCOL = ['#2a1b14', '#5a3522', '#d9a441', '#111111', '#8b3a1a', '#e8e0d0'];
// o: {skin, shirt, dark, kind, pants, shoe, hair, hairCol, sleeves, acc:[['partyHat',{...}], 'glasses'], face, scale}
export function avatar(o = {}) {
  const shirt = o.shirt || '#2f7bff', dark = o.dark || new THREE.Color(shirt).multiplyScalar(.6).getStyle();
  const g = new THREE.Group(), skin = mat(o.skin || '#f3d6b4'), shm = mat(shirt), sl = mat(o.sleeves || shirt), pa = mat(o.pants || '#3a3f58'), shoe = mat(o.shoe || '#2a2a33');
  const front = mat('#fff', { map: frontTex({ ...o, shirt, dark }) });
  const hip = new THREE.Group(); g.add(hip);
  const torso = new THREE.Mesh(new RoundedBoxGeometry(2, 2, 1, 2, .06), [shm, shm, shm, shm, front, shm]); torso.castShadow = torso.receiveShadow = true; torso.position.y = 3; hip.add(torso);
  const limb = (x, y, top, bot, hb, arm) => { const p = new THREE.Group(); p.position.set(x, y, 0); const off = arm ? .15 : 0; const a = rbox(.98, 2 - hb, .98, .05, top); a.position.y = -(2 - hb) / 2 + off; const b = rbox(.96, hb, .96, .05, bot); b.position.y = -(2 - hb) - hb / 2 + off; p.add(a, b); return p; };
  const armL = limb(1.5, 3.85, sl, skin, .5, true), armR = limb(-1.5, 3.85, sl, skin, .5, true);
  const legL = limb(.5, 2, pa, shoe, .42), legR = limb(-.5, 2, pa, shoe, .42);
  hip.add(armL, armR); g.add(legL, legR);
  const head = new THREE.Group(); head.position.y = 4.02; hip.add(head);
  const hd = rbox(1.36, 1.26, 1.26, .2, skin); hd.position.y = .63; head.add(hd);
  const fc = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 1.3), face(o.face || 'smile')); fc.position.set(0, .63, .632); head.add(fc);
  const hr = hairMesh(o.hair || 'swoop', o.hairCol || '#5a3522'); hr.position.y = -4.02; head.add(hr);
  for (const a of o.acc || []) { const [n, ao] = Array.isArray(a) ? a : [a, {}]; const m = ACC[n](ao); if (m.userData.head) { m.position.y -= 4.02; head.add(m); } else if (m.userData.arm) (m.userData.arm === 'L' ? armL : armR).add(m); else hip.add(m); }
  g.userData = { hip, torso, armL, armR, legL, legR, head, face: fc, o };
  if (o.scale) g.scale.setScalar(o.scale);
  if (o.add !== false) scene.add(g);
  return g;
}
// pose: {e: face, aL/aR: [x, y, z] arm rotations (x<0 raises forward, z>0 moves the left arm out), lL/lR legs, hx/hy/hz head, lean, bob}
export function pose(a, p = {}) {
  const u = a.userData;
  u.armL.rotation.set(p.aL ? p.aL[0] : 0, p.aL ? p.aL[1] || 0 : 0, p.aL ? p.aL[2] ?? .04 : .04);
  u.armR.rotation.set(p.aR ? p.aR[0] : 0, p.aR ? p.aR[1] || 0 : 0, p.aR ? p.aR[2] ?? -.04 : -.04);
  u.legL.rotation.set(p.lL || 0, 0, p.lLz || 0); u.legR.rotation.set(p.lR || 0, 0, p.lRz || 0);
  u.head.rotation.set(p.hx || 0, p.hy || 0, p.hz || 0); u.hip.rotation.set(p.lean || 0, p.twist || 0, 0); u.hip.position.y = p.bob || 0;
  u.face.material = face(p.e || 'smile');
}
// named poses: POSES.wave(t) etc. merge with your own fields: pose(a, {...POSES.cheer(t), e: 'joy'})
export const POSES = {
  idle: t => ({ hx: Math.sin(t * 1.3) * .03, bob: Math.sin(t * 2) * .03 }),
  wave: t => ({ aR: [-.2, 0, -2.6 - Math.sin(t * 9) * .35] }),
  cheer: t => ({ aL: [-.2, 0, 2.6 + Math.sin(t * 10) * .2], aR: [-.2, 0, -2.6 - Math.sin(t * 10 + 1) * .2], bob: Math.abs(Math.sin(t * 10)) * .3, e: 'joy' }),
  point: () => ({ aR: [-1.55, 0, -.1] }),
  pointUp: () => ({ aR: [-.3, 0, -2.9], hx: -.4 }),
  wish: () => ({ aL: [-1.15, 0, -.35], aR: [-1.15, 0, .35], e: 'wish' }),
  shrug: () => ({ aL: [-.3, 0, .9], aR: [-.3, 0, -.9], hz: .15, e: 'neutral' }),
  scared: t => ({ aL: [-2.6, 0, -.3], aR: [-2.6, 0, .3], hx: -.2, lL: Math.sin(t * 30) * .04, e: 'scared' }),
  lookUp: () => ({ hx: -.5, e: 'shock' }),
  facepalm: () => ({ aR: [-2.2, 0, .5], hx: .25, e: 'sad' }),
  hug: () => ({ aL: [-1.4, 0, -.9], aR: [-1.4, 0, .9], e: 'grin' }),
  sit: () => ({ lL: -1.57, lR: -1.57, bob: -1.0 }),
  think: () => ({ aR: [-2.0, 0, .8], hz: -.12, e: 'neutral' }),
  angry: t => ({ aL: [0, 0, .4], aR: [0, 0, -.4], lean: .08, bob: Math.abs(Math.sin(t * 14)) * .1, e: 'angry' }),
  cry: t => ({ aL: [-2.3, 0, -.6], aR: [-2.3, 0, .6], hx: .2, bob: Math.sin(t * 16) * .04, e: 'cry' }),
};
// walk / run cycles: returns pose fields; move the avatar yourself (position) — speed ~4.5 units/s walk, 10 run
export const walk = (t, rate = 7, amp = .6) => ({ lL: Math.sin(t * rate) * amp, lR: -Math.sin(t * rate) * amp, aL: [-Math.sin(t * rate) * amp * .9, 0, .05], aR: [Math.sin(t * rate) * amp * .9, 0, -.05], bob: Math.abs(Math.cos(t * rate)) * .12 });
export const runCycle = (t, rate = 13, amp = 1.0) => ({ ...walk(t, rate, amp), lean: .18, bob: Math.abs(Math.cos(t * rate)) * .3 });

// ---------- presets ----------
export const CAST = {
  hero: { skin: '#f3d6b4', shirt: '#2f7bff', kind: 'hoodie', pants: '#3a3f58', shoe: '#ffffff', hair: 'swoop', hairCol: '#5a3522' },
  heroine: { skin: '#f5cba0', shirt: '#f472b6', kind: 'stripe', dark: '#be185d', pants: '#1f2937', shoe: '#ffffff', hair: 'pony', hairCol: '#2a1b14' },
  puffer: { skin: '#f3d6b4', shirt: '#e53935', kind: 'puffer', sleeves: '#1f2a44', pants: '#55606e', shoe: '#c08a3a', hair: 'swoop', hairCol: '#4a2a18', acc: ['backpack'] },
  mom: { skin: '#f0c49a', shirt: '#ff7f6b', kind: 'dress', dark: '#c2410c', pants: '#3fae5a', hair: 'bun', hairCol: '#221a2b' },
  dad: { skin: '#e8b98c', shirt: '#3b82f6', kind: 'tee', pants: '#374151', hair: 'buzz', hairCol: '#2a1b14', acc: ['mustache'] },
  grandpa: { skin: '#f3d6b4', shirt: '#c8a96a', kind: 'overall', dark: '#7a5a2a', pants: '#6b4f3a', hair: 'buzz', hairCol: '#d8d8d8', acc: [['beard', { col: '#cfcfcf' }], 'glasses'] },
  explorer: { skin: '#f3d6b4', shirt: '#b8955a', kind: 'overall', dark: '#6b4a1a', pants: '#5a4a30', hair: 'swoop', hairCol: '#111', acc: ['beard', 'backpack'] },
  bully: { skin: '#e8b98c', shirt: '#7f1d1d', kind: 'tee', pants: '#111827', hair: 'spiky', hairCol: '#111', face: 'smirk' },
  king: { skin: '#f3d6b4', shirt: '#7c3aed', kind: 'king', dark: '#4c1d95', pants: '#4c1d95', hair: 'buzz', hairCol: '#e8e0d0', acc: ['crown', ['beard', { col: '#e8e0d0' }], 'cape'] },
  police: { skin: '#c98b5a', shirt: '#1e3a8a', kind: 'police', dark: '#172554', pants: '#172554', hair: 'buzz', hairCol: '#111', acc: ['policeHat'] },
  doctor: { skin: '#f5cba0', shirt: '#ffffff', kind: 'doctor', pants: '#60a5fa', hair: 'long', hairCol: '#5a3522', acc: ['glasses'] },
  teacher: { skin: '#e8b98c', shirt: '#14532d', kind: 'suit', dark: '#052e16', tie: '#ffd23f', pants: '#1f2937', hair: 'bun', hairCol: '#5a3522', acc: ['glasses'] },
  knight: { skin: '#f3d6b4', shirt: '#c8ccd4', kind: 'armor', sleeves: '#9aa0aa', pants: '#6b7280', hair: 'buzz', hairCol: '#2a1b14', acc: ['sword', 'cape'] },
  mayor: { skin: '#f3d6b4', shirt: '#1f2937', kind: 'suit', dark: '#0b1220', pants: '#1f2937', hair: 'buzz', hairCol: '#2a1b14', acc: ['topHat', 'mustache'] },
  sleepy: { skin: '#f3d6b4', shirt: '#60a5fa', kind: 'pajamas', dark: '#fef08a', pants: '#60a5fa', hair: 'curly', hairCol: '#d9a441', face: 'sleep' },
};
export const cast = (name, extra = {}) => avatar({ ...CAST[name], ...extra, acc: [...(CAST[name].acc || []), ...(extra.acc || [])] });
export function randomPerson(o = {}) { const s = pick(SHIRT); return avatar({ skin: pick(SKIN), shirt: s, kind: pick(['stripe', 'puffer', 'tee', 'overall', 'hoodie', 'dress', 'plain']), logo: false, pants: pick(PANTS), hair: pick(['swoop', 'pony', 'spiky', 'curly', 'long', 'bun', 'buzz']), hairCol: pick(HAIRCOL), ...o }); }
// a crowd ring facing a point; returns the list (added to the scene, registered as camera-safe extras)
export function crowd(n, c, r0, r1, o = {}) {
  const list = [];
  for (let i = 0; i < n; i++) { const a = R(0, Math.PI * 2), r = R(r0, r1); const p = randomPerson(o.hats && rnd() < o.hats ? { acc: [['partyHat', { cols: [pick(SHIRT), pick(SHIRT)] }]] } : {}); p.position.set(c.x + Math.cos(a) * r, 0, c.z + Math.sin(a) * r); p.rotation.y = Math.atan2(c.x - p.position.x, c.z - p.position.z); p.userData.ph = R(0, 6); p.userData.mood = rnd(); list.push(p); }
  extras(list); return list;
}
// crowd moods: 'idle', 'party', 'up' (looking up, amazed), 'scared', 'cheer', 'run' (flee outward)
export function crowdPose(list, t, mode, c) {
  for (const p of list) {
    const u = p.userData, m = u.mood;
    if (mode === 'idle') pose(p, { ...POSES.idle(t + u.ph), e: m > .5 ? 'smile' : 'neutral' });
    if (mode === 'party') pose(p, { e: m > .5 ? 'grin' : 'smile', aR: [-.2, 0, -(m > .7 ? 2.6 + Math.sin(t * 8 + u.ph) * .3 : .1)], hx: Math.sin(t * 4 + u.ph) * .05 });
    if (mode === 'cheer') pose(p, { ...POSES.cheer(t + u.ph) });
    if (mode === 'up') pose(p, { e: m > .4 ? 'joy' : 'shock', hx: -.55, aL: [-.2, 0, m > .5 ? 2.7 : .2], aR: [-.2, 0, -(m > .3 ? 2.7 : .2)] });
    if (mode === 'scared') pose(p, { ...POSES.scared(t + u.ph), hx: -.5 });
    if (mode === 'run') { pose(p, { ...runCycle(t + u.ph), e: 'scared' }); }
  }
}
