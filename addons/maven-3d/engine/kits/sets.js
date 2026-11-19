// Sets: each builder returns a THREE.Group placed at an origin (x, z) so several sets coexist far apart.
// Show one with set.visible = true and call shadowAt(x, z) when you film it. Units: an avatar is 5.3 tall.
import { THREE, canvasTex, mat, glow, box, rbox, cyl, ball, at, R, pick, rnd, seed, scene, cloudMat, V, lerpV, followCam } from '../core.js';

// ---------- textures ----------
const noiseTex = (base, hues, rep, dots = 2500) => canvasTex(256, 256, (g, w, h) => { g.fillStyle = base; g.fillRect(0, 0, w, h); for (let i = 0; i < dots; i++) { g.fillStyle = pick(hues); g.fillRect(R(0, w), R(0, h), 2, R(2, 5)); } }, rep);
export const TEX = {
  grass: () => noiseTex('#5fbf3a', ['#4caf35', '#6fcf48', '#57b83c', '#7ad655'], 60),
  sand: () => noiseTex('#f2d59a', ['#e8c987', '#fae3b0', '#e0bf7a'], 40),
  snow: () => noiseTex('#eef4ff', ['#dfe8ff', '#ffffff', '#d4e0fa'], 40, 1200),
  dirt: () => noiseTex('#8a6a45', ['#7a5a38', '#9a7a52', '#6b4d30'], 30),
  road: () => noiseTex('#4b4d55', ['#55575f', '#44464d', '#5c5e66'], 20, 900),
  tiles: (a = '#f2d3a6', b = '#eebf8e', l = '#c99a6a', rep = 9) => canvasTex(512, 512, (g, w) => { const n = 8, s = w / n; for (let i = 0; i < n; i++)for (let j = 0; j < n; j++) { g.fillStyle = (i + j) % 2 ? a : b; g.fillRect(i * s, j * s, s, s); g.strokeStyle = l; g.lineWidth = 5; g.strokeRect(i * s, j * s, s, s); } }, rep),
  planks: (c = '#c98f55', rep = 6) => canvasTex(256, 256, (g, w, h) => { for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? c : new THREE.Color(c).multiplyScalar(.9).getStyle(); g.fillRect(0, i * 32, w, 32); g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(0, i * 32, w, 3); g.fillRect((i * 97) % w, i * 32, 3, 32); } }, rep),
  bricks: (c = '#b5533c', rep = 4) => canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#d8cbb8'; g.fillRect(0, 0, w, h); for (let r = 0; r < 8; r++) for (let k = -1; k < 5; k++) { g.fillStyle = new THREE.Color(c).offsetHSL(0, 0, R(-.05, .05)).getStyle(); g.fillRect(k * 64 + (r % 2) * 32 + 3, r * 32 + 3, 58, 26); } }, rep),
  stone: (c = '#8a8f99', rep = 4) => canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#5a5e66'; g.fillRect(0, 0, w, h); for (let r = 0; r < 6; r++) for (let k = -1; k < 4; k++) { g.fillStyle = new THREE.Color(c).offsetHSL(0, 0, R(-.08, .08)).getStyle(); g.fillRect(k * 86 + (r % 2) * 43 + 4, r * 43 + 4, 78, 35); } }, rep),
  wallpaper: (a = '#bfe3ff', b = '#a8d4f5', rep = 3) => canvasTex(256, 256, (g, w, h) => { for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? a : b; g.fillRect(i * 32, 0, 32, h); } }, rep),
  windows: (wall) => canvasTex(256, 256, (g, W2, H2) => { g.fillStyle = wall; g.fillRect(0, 0, W2, H2); for (let i = 0; i < 2; i++)for (let j = 0; j < 2; j++) { const x0 = 40 + i * 120, y0 = 40 + j * 110; g.fillStyle = '#fff'; g.fillRect(x0 - 8, y0 - 8, 72, 78); g.fillStyle = '#5fb8f0'; g.fillRect(x0, y0, 56, 62); g.fillStyle = 'rgba(255,255,255,.55)'; g.fillRect(x0 + 6, y0 + 6, 14, 50); g.fillStyle = '#fff'; g.fillRect(x0 + 25, y0, 6, 62); } }),
  tower: (wall, lit = .3) => canvasTex(256, 512, (g, W2, H2) => { g.fillStyle = wall; g.fillRect(0, 0, W2, H2); for (let y = 16; y < H2; y += 36) for (let x = 14; x < W2; x += 40) { g.fillStyle = Math.random() < lit ? '#ffe9a0' : '#3a5a80'; g.fillRect(x, y, 26, 22); } }),
  cloud: () => canvasTex(256, 160, (g) => { for (let i = 0; i < 9; i++) { const x = 50 + i * 19 + R(-8, 8), y = 100 - Math.sin(i / 8 * Math.PI) * 45 + R(-6, 6), r = R(30, 48); const gr = g.createRadialGradient(x, y - r * .3, 2, x, y, r); gr.addColorStop(0, '#fff'); gr.addColorStop(.7, '#f3f7ff'); gr.addColorStop(1, 'rgba(225,235,255,0)'); g.fillStyle = gr; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); } }),
};
const flat = (w, d, m, y = 0) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(w, d), m); p.rotation.x = -Math.PI / 2; p.position.y = y; p.receiveShadow = true; return p; };
const disk = (r, m, y = .02, seg = 64) => { const p = new THREE.Mesh(new THREE.CircleGeometry(r, seg), m); p.rotation.x = -Math.PI / 2; p.position.y = y; p.receiveShadow = true; return p; };

// ---------- shared pieces ----------
export const HOUSE_COL = ['#ffd1dc', '#fff0a8', '#bfe9ff', '#c9f2c0', '#ffd9a8', '#e6d0ff', '#ffffff', '#ffb8a8'];
export const ROOF_COL = ['#e0473c', '#3b6fd8', '#8a4b2a', '#2f9e6b', '#c2410c', '#6b4bc9'];
export function house(o = {}) {
  const g = new THREE.Group(), sc = o.scale || 1, w = (o.w || R(12, 16)) * sc, h = (o.h || R(9, 13)) * sc, d = (o.d || R(11, 14)) * sc;
  const body = box(w, h, d, mat('#fff', { map: TEX.windows(o.wall || pick(HOUSE_COL)) })); body.position.y = h / 2; g.add(body);
  const shp = new THREE.Shape([new THREE.Vector2(-w / 2 - .8, 0), new THREE.Vector2(w / 2 + .8, 0), new THREE.Vector2(0, h * .45)]);
  const roof = new THREE.Mesh(new THREE.ExtrudeGeometry(shp, { depth: d + 1.6, bevelEnabled: false }), mat(o.roof || pick(ROOF_COL), { roughness: .7 }));
  roof.position.set(0, h, -d / 2 - .8); roof.castShadow = roof.receiveShadow = true; g.add(roof);
  g.add(at(box(2.6 * sc, 4.4 * sc, .3, mat(o.door || '#7a4a2c')), 0, 2.2 * sc, d / 2 + .1));
  if (o.night) for (const x of [-w / 4, w / 4]) g.add(at(box(2.2, 2.2, .2, glow('#ffd88a', 1.4)), x, h * .62, d / 2 + .12));
  g.userData.size = [w, h, d]; return g;
}
export function tree(o = {}) {
  const g = new THREE.Group(), s = o.scale || 1; g.add(at(box(.8 * s, 4 * s, .8 * s, mat(o.trunk || '#7a4b2a')), 0, 2 * s, 0));
  const cm = mat(o.col || pick(['#3fbf3a', '#56d14a', '#2fa84a']), { roughness: .85 });
  for (let i = 0; i < 6; i++) g.add(at(ball(R(1.6, 2.3) * s, cm), R(-1.4, 1.4) * s, (4.6 + R(-.6, 1.6)) * s, R(-1.4, 1.4) * s));
  return g;
}
export function pine(o = {}) { const g = new THREE.Group(), s = o.scale || 1, m = mat(o.col || '#2f7a4a', { roughness: .85 }); g.add(at(box(.7 * s, 3 * s, .7 * s, mat('#5a3a22')), 0, 1.5 * s, 0)); for (let i = 0; i < 3; i++) { const c = new THREE.Mesh(new THREE.ConeGeometry((3 - i * .7) * s, 3.4 * s, 7), m); c.castShadow = true; c.position.y = (3.4 + i * 2) * s; g.add(c); if (o.snow) { const sn = new THREE.Mesh(new THREE.ConeGeometry((1.4 - i * .3) * s, 1.4 * s, 7), mat('#f4f8ff')); sn.position.y = (4.4 + i * 2) * s; g.add(sn); } } return g; }
export function lamp(o = {}) { const g = new THREE.Group(); g.add(at(cyl(.15, .2, 8, mat('#2a2d36'), 8), 0, 4, 0), at(box(1.4, .2, .2, mat('#2a2d36')), .6, 8, 0), at(ball(.45, o.on ? glow('#ffe6a0', 3) : mat('#fffbe8'), 1), 1.2, 7.7, 0)); if (o.on) { const l = new THREE.PointLight(0xffd890, 30, 22, 1.6); l.position.set(1.2, 7.3, 0); g.add(l); } return g; }
export function fence(len, o = {}) { const g = new THREE.Group(), m = mat(o.col || '#ffffff'); for (let x = 0; x <= len; x += 1.6) g.add(at(box(.35, 2.2, .35, m), x - len / 2, 1.1, 0)); g.add(at(box(len, .3, .2, m), 0, 1.6, 0), at(box(len, .3, .2, m), 0, .8, 0)); return g; }
export function clouds(n = 36, o = {}) { const g = new THREE.Group(); cloudMat.map = cloudMat.map || TEX.cloud(); for (let i = 0; i < n; i++) { const s = new THREE.Sprite(cloudMat); const a = R(0, Math.PI * 2), r = R(250, 800); s.position.set(Math.cos(a) * r, R(110, 260), Math.sin(a) * r); const k = R(90, 180) * (o.scale || 1); s.scale.set(k, k * .62, 1); g.add(s); } scene.add(g); if (o.follow !== false) followCam(g); return g; }
export function hills(o = {}) { const g = new THREE.Group(); for (let i = 0; i < 9; i++) { const a = i / 9 * Math.PI * 2, h = new THREE.Mesh(new THREE.SphereGeometry(R(160, 260), 32, 16), mat(pick(o.cols || ['#58c43f', '#4cb53a', '#6ccf48']), { roughness: 1 })); h.scale.y = o.flat || .35; at(h, Math.cos(a) * 620, -20, Math.sin(a) * 620); g.add(h); } return g; }
export function bunting(rad = 30, y = 12, n = 5) {
  const g = new THREE.Group(), FLAG = ['#ff4d6d', '#ffd23f', '#3fa9f5', '#4ade80', '#c084fc', '#fb923c'];
  const fg = new THREE.BufferGeometry().setFromPoints([V(-.45, 0, 0), V(.45, 0, 0), V(0, -1, 0)]); fg.computeVertexNormals();
  for (let k = 0; k < n; k++) { const a = k / n * Math.PI, A = V(Math.cos(a) * rad, y, Math.sin(a) * rad), B = V(-A.x, y, -A.z);
    for (const P of [A, B]) g.add(at(box(.4, y, .4, mat('#f5f5f5')), P.x, y / 2, P.z));
    const m = 46; for (let i = 0; i < m; i++) { const k2 = (i + .5) / m, p = lerpV(A, B, k2); p.y -= Math.sin(k2 * Math.PI) * 3.2; const f = new THREE.Mesh(fg, mat(FLAG[i % 6], { side: THREE.DoubleSide })); f.position.copy(p); f.lookAt(p.x + (B.z - A.z), p.y, p.z - (B.x - A.x)); f.castShadow = true; g.add(f); } }
  return g;
}

// ---------- 1. town: round plaza, ring road, two rings of houses, trees, hills ----------
export function town(x = 0, z = 0, o = {}) {
  seed(o.seed || 11); const g = new THREE.Group();
  g.add(flat(2600, 2600, mat('#fff', { map: TEX.grass(), roughness: .95 })));
  g.add(disk(33, mat('#fff', { map: TEX.tiles(), roughness: .8 }), .03), (() => { const r = new THREE.Mesh(new THREE.RingGeometry(33, 40, 96), mat('#fff', { map: TEX.road(), roughness: .9 })); r.rotation.x = -Math.PI / 2; r.position.y = .02; r.receiveShadow = true; return r; })());
  for (let i = 0; i < 48; i++) { const a = i / 48 * Math.PI * 2; const d = box(2.2, .05, .4, mat('#f5f0d8')); at(d, Math.cos(a) * 36.5, .05, Math.sin(a) * 36.5); d.rotation.y = -a; g.add(d); }
  const houses = [];
  for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2 + .11, h = house({ night: o.night }); at(h, Math.cos(a) * 52, 0, Math.sin(a) * 52); h.rotation.y = -a - Math.PI / 2; g.add(h); houses.push(h); }
  for (let i = 0; i < 26; i++) { const a = i / 26 * Math.PI * 2 + .3, r = R(88, 100), h = house({ scale: R(.9, 1.15), night: o.night }); at(h, Math.cos(a) * r, 0, Math.sin(a) * r); h.rotation.y = -a - Math.PI / 2; g.add(h); }
  for (let i = 0; i < 40; i++) { const a = i / 40 * Math.PI * 2 + R(0, .1), r = R(41, 45); g.add(at(tree({ scale: R(.8, 1.1) }), Math.cos(a) * r, 0, Math.sin(a) * r)); }
  for (let i = 0; i < 70; i++) { const a = R(0, Math.PI * 2), r = R(110, 300); g.add(at(tree({ scale: R(1.2, 2), col: pick(['#3fbf3a', '#56d14a', '#2fa84a', '#7fd14a']) }), Math.cos(a) * r, 0, Math.sin(a) * r)); }
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2 + .2; g.add(at(lamp({ on: o.night }), Math.cos(a) * 31, 0, Math.sin(a) * 31)); }
  g.add(hills()); g.position.set(x, 0, z); scene.add(g); g.userData = { houses, center: V(x, 0, z) }; return g;
}

// ---------- 2. party: table, cake with number candles, presents, balloons (place it in the plaza) ----------
export function party(x = 0, z = 0, o = {}) {
  seed(o.seed || 3); const g = new THREE.Group(), FLAG = ['#ff4d6d', '#ffd23f', '#3fa9f5', '#4ade80', '#c084fc', '#fb923c'];
  g.add(at(box(10, .3, 3.4, mat('#ffffff')), 0, 2.25, -.6), at(box(9.9, 2.0, 3.3, mat(o.skirt || '#ff9cc2')), 0, 1.1, -.6));
  const cake = new THREE.Group(); cake.position.set(0, 2.4, -.5); g.add(cake);
  cake.add(at(cyl(1.15, 1.15, .75, mat('#ff8fb8'), 40), 0, .375, 0), at(cyl(.8, .8, .6, mat('#fff4e8'), 40), 0, 1.05, 0));
  for (const [r, y, c] of [[1.12, .74, '#fff4e8'], [.78, 1.34, '#ff5d9e']]) { const d = new THREE.Mesh(new THREE.TorusGeometry(r, .1, 8, 48), mat(c)); d.rotation.x = Math.PI / 2; d.position.y = y; cake.add(d); }
  for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; cake.add(at(ball(.09, mat(FLAG[i % 6], { emissive: FLAG[i % 6], emissiveIntensity: .2 }), 1), Math.cos(a), .78, Math.sin(a))); }
  const digits = String(o.age ?? 10).split(''), flames = [];
  digits.forEach((dch, i) => { const x0 = (i - (digits.length - 1) / 2) * .6, m = mat(FLAG[i % 6], { roughness: .4 });
    if (dch === '0') { const z0 = new THREE.Mesh(new THREE.TorusGeometry(.24, .085, 12, 32), m); z0.scale.set(1, 1.45, 1); z0.position.set(x0, 1.73, 0); cake.add(z0); }
    else cake.add(at(box(.2, .8, .16, m), x0, 1.75, 0));
    const f = new THREE.Sprite(new THREE.SpriteMaterial({ map: FLAME, color: 0xffb040, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true })); f.position.set(x0, 2.32, 0); f.scale.set(.32, .5, 1); cake.add(f); flames.push(f); });
  const light = new THREE.PointLight(0xffa040, 6, 6, 1.6); light.position.set(0, 2.5, .2); cake.add(light);
  for (const [px, c] of [[-3.4, '#4ade80'], [-2.2, '#c084fc'], [3.5, '#3fa9f5'], [2.4, '#fb923c']]) { g.add(at(box(.9, .8, .9, mat(c)), px, 2.8, -1.1), at(box(.95, .82, .2, mat('#fff')), px, 2.8, -1.1)); }
  const balloons = []; for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2, r = R(6, 9), b = ball(.85, mat(FLAG[i % 6], { roughness: .25 }), 3); b.scale.y = 1.18; g.add(b); balloons.push([b, V(Math.cos(a) * r, R(8, 10.5), Math.sin(a) * r - .6), R(0, 6)]); }
  g.position.set(x, 0, z); scene.add(g);
  g.userData = { cake, flames, light, balloons, top: V(x, 2.4, z - .5),
    tick(t, lit = 1) { flames.forEach((f, i) => { f.visible = lit > 0; f.scale.set(.32 * lit, (.5 + Math.sin(t * 30 + i) * .05) * lit, 1); }); light.intensity = 6 * lit; balloons.forEach(([b, p, ph]) => b.position.set(p.x + Math.sin(t + ph) * .3, p.y + Math.sin(t * 1.4 + ph) * .35, p.z)); } };
  return g;
}
const FLAME = canvasTex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(.25, 'rgba(255,240,180,.8)'); r.addColorStop(1, 'rgba(255,200,80,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });

// ---------- 3. room: an interior box (bedroom by default) with a window, bed, desk, lamp ----------
export function room(x = 0, z = 0, o = {}) {
  seed(o.seed || 5); const g = new THREE.Group(), W2 = o.w || 26, D = o.d || 22, Hh = o.h || 14;
  const wallM = mat('#fff', { map: o.wallTex || TEX.wallpaper(o.wallA, o.wallB), side: THREE.BackSide });
  const shell = new THREE.Mesh(new THREE.BoxGeometry(W2, Hh, D), [wallM, wallM, mat(o.ceiling || '#f6f1ea', { side: THREE.BackSide }), mat('#fff', { map: TEX.planks(o.floor || '#c98f55'), side: THREE.BackSide }), wallM, wallM]);
  shell.position.y = Hh / 2; shell.receiveShadow = true; g.add(shell);
  // window on the back wall with sky behind
  const win = new THREE.Group(); win.position.set(-4, 7.5, -D / 2 + .1); g.add(win);
  win.add(at(box(7.4, 6.4, .3, mat('#ffffff')), 0, 0, 0)); const glass = box(6.6, 5.6, .32, mat(o.skyCol || '#8fd0ff', { emissive: o.skyCol || '#8fd0ff', emissiveIntensity: .8 })); win.add(glass); win.add(at(box(.25, 5.6, .4, mat('#fff')), 0, 0, 0), at(box(6.6, .25, .4, mat('#fff')), 0, 0, 0));
  g.userData.windowGlass = glass;
  if (o.kind !== 'empty') {
    // bed
    const bed = new THREE.Group(); bed.position.set(7, 0, -5); g.add(bed);
    bed.add(at(box(6.4, 1.6, 9.4, mat('#8a5a3a')), 0, .8, 0), at(box(6.2, 1.0, 9.2, mat(o.blanket || '#4f7cff')), 0, 2.0, .1), at(rbox(4.6, .9, 2.2, .3, mat('#ffffff')), 0, 2.8, -3.2), at(box(6.4, 4.4, .6, mat('#8a5a3a')), 0, 2.2, -4.7));
    // desk + lamp + shelf + rug + poster
    g.add(at(box(6, .4, 3, mat('#b07a4a')), -6, 3.4, -8.5), at(box(.4, 3.4, .4, mat('#8a5a3a')), -8.6, 1.7, -7.4), at(box(.4, 3.4, .4, mat('#8a5a3a')), -3.4, 1.7, -7.4));
    g.add(at(cyl(.3, .5, 1.6, mat('#ffd23f'), 12), -4.2, 4.4, -9), at(ball(.5, glow('#fff1b8', 2), 1), -4.2, 5.4, -9));
    g.add(at(box(8, .3, 1.6, mat('#b07a4a')), -6, 10, -10.3)); for (let i = 0; i < 6; i++) g.add(at(box(.6, R(1, 1.8), 1.0, mat(pick(['#e11d48', '#2563eb', '#16a34a', '#f59e0b', '#7c3aed']))), -9 + i * 1.1, 10.8, -10.3));
    const rug = new THREE.Mesh(new THREE.CircleGeometry(4, 40), mat(o.rug || '#ff9cc2')); rug.rotation.x = -Math.PI / 2; rug.position.set(-1, .03, 2); rug.receiveShadow = true; g.add(rug);
    g.add(at(box(4, 5, .1, mat(pick(['#7c3aed', '#0ea5e9', '#f97316']))), 6, 8.5, -D / 2 + .1));
    const door = box(4.4, 8.6, .4, mat('#8a5a3a')); door.position.set(W2 / 2 - .2, 4.3, 4); door.rotation.y = Math.PI / 2; g.add(door); g.userData.door = door;
  }
  const lt = new THREE.PointLight(o.lightCol || 0xfff1d8, o.light ?? 120, 60, 1.4); lt.position.set(0, Hh - 1.5, 0); lt.castShadow = true; lt.shadow.mapSize.set(1024, 1024); g.add(lt); g.userData.light = lt;
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 4. classroom ----------
export function classroom(x = 0, z = 0, o = {}) {
  const g = room(x, z, { kind: 'empty', wallTex: TEX.wallpaper('#f5e8c8', '#efdfba'), floor: '#a8835a', w: 32, d: 28, ...o });
  const board = box(14, 6, .3, mat('#1f4d3a')); board.position.set(0, 7.5, -13.8); g.add(board); g.add(at(box(14.6, .4, .6, mat('#8a5a3a')), 0, 4.4, -13.6));
  g.userData.board = board;
  g.add(at(box(5, 3.2, 2.6, mat('#8a5a3a')), 8, 1.6, -9));
  g.userData.desks = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) { const d = new THREE.Group(); d.position.set(-8 + c * 8, 0, -2 + r * 6); d.add(at(box(4, .3, 2.4, mat('#d9b07a')), 0, 2.6, 0), at(box(.3, 2.6, .3, mat('#555')), -1.7, 1.3, -1), at(box(.3, 2.6, .3, mat('#555')), 1.7, 1.3, -1), at(box(2.4, .3, 2.2, mat('#3b82f6')), 0, 1.6, 2.2)); g.add(d); g.userData.desks.push(d); }
  g.add(at(cyl(1.3, 1.3, .2, mat('#fff')), 10, 10, -13.8)); g.children.at(-1).rotation.x = Math.PI / 2;
  return g;
}

// ---------- 5. forest: dense pines and round trees, dirt path, fireflies optional ----------
export function forest(x = 0, z = 0, o = {}) {
  seed(o.seed || 9); const g = new THREE.Group();
  g.add(flat(1600, 1600, mat('#fff', { map: o.snow ? TEX.snow() : TEX.grass(), roughness: .95 })));
  const path = flat(8, 400, mat('#fff', { map: TEX.dirt() }), .03); g.add(path);
  for (let i = 0; i < 260; i++) { const px = R(-160, 160), pz = R(-300, 120); if (Math.abs(px) < 7) continue; g.add(at(rnd() < .7 ? pine({ scale: R(1.2, 2.4), snow: o.snow, col: o.dark ? '#1f4a34' : undefined }) : tree({ scale: R(1, 1.8), col: o.dark ? '#2a5a2a' : undefined }), px, 0, pz)); }
  for (let i = 0; i < 40; i++) g.add(at(ball(R(.6, 1.4), mat('#8a8f99'), 0), R(-40, 40), .3, R(-200, 60)));
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 6. spooky street: dark houses with lit windows, church with a clock tower, fog-friendly ----------
export function spookyStreet(x = 0, z = 0, o = {}) {
  seed(o.seed || 13); const g = new THREE.Group();
  g.add(flat(1200, 1200, mat('#3a4a3a', { roughness: 1 })), flat(14, 400, mat('#fff', { map: TEX.stone('#6a6e76', 30) }), .03));
  for (let i = 0; i < 10; i++) for (const s of [-1, 1]) { const h = house({ wall: pick(['#7a7f8a', '#8a7a70', '#6a6060', '#5a6a70']), roof: pick(['#2a2a33', '#3a2a2a', '#1f2a2a']), night: true }); at(h, s * 17, 0, -i * 22 + 30); h.rotation.y = -s * Math.PI / 2; g.add(h); g.add(at(lamp({ on: true }), s * 8.5, 0, -i * 22 + 40)); }
  // church + clock tower at the end of the street
  const ch = new THREE.Group(); ch.position.set(0, 0, -210); g.add(ch);
  ch.add(at(box(30, 18, 22, mat('#fff', { map: TEX.bricks('#7a4a3c', 3) })), 0, 9, 0), at(box(8, 44, 8, mat('#fff', { map: TEX.bricks('#7a4a3c', 2) })), 0, 22, 12));
  const spire = new THREE.Mesh(new THREE.ConeGeometry(6, 14, 4), mat('#2a2a33')); spire.position.set(0, 51, 12); spire.rotation.y = Math.PI / 4; ch.add(spire);
  const clk = new THREE.Mesh(new THREE.CircleGeometry(3, 40), mat('#fffbe8', { emissive: '#fff1b8', emissiveIntensity: .6 })); clk.position.set(0, 36, 16.1); ch.add(clk);
  for (const [l, w] of [[2.2, .3], [1.6, .4]]) { const hnd = box(w, l, .1, mat('#111')); hnd.geometry.translate(0, l / 2, 0); hnd.position.set(0, 36, 16.2); ch.add(hnd); }
  g.userData.church = ch;
  for (let i = 0; i < 30; i++) g.add(at(pine({ scale: R(1.5, 2.5), col: '#1f3a2a' }), R(-120, 120) + (rnd() < .5 ? 0 : 0), 0, R(-300, -230)));
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 7. castle courtyard: walls, towers, gate, throne platform ----------
export function castle(x = 0, z = 0, o = {}) {
  seed(o.seed || 17); const g = new THREE.Group(), st = mat('#fff', { map: TEX.stone('#a8a49a', 6) });
  g.add(flat(1400, 1400, mat('#fff', { map: TEX.grass(), roughness: .95 })), disk(46, mat('#fff', { map: TEX.stone('#c8c0b0', 10) }), .03));
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; const tw = cyl(6, 6.5, 34, st, 16); at(tw, Math.cos(a) * 48, 17, Math.sin(a) * 48); g.add(tw); const cone = new THREE.Mesh(new THREE.ConeGeometry(7.4, 12, 16), mat(o.roof || '#3b4fa8')); cone.castShadow = true; at(cone, Math.cos(a) * 48, 40, Math.sin(a) * 48); g.add(cone);
    const b = Math.PI * 2 / 8, mid = a + b / 2, wl = box(32, 22, 4, st); at(wl, Math.cos(mid) * 45, 11, Math.sin(mid) * 45); wl.rotation.y = -mid + Math.PI / 2; g.add(wl);
    for (let k = -3; k <= 3; k++) { const m = box(2.4, 2.4, 4.2, st); at(m, Math.cos(mid) * 45 + Math.cos(mid + Math.PI / 2) * k * 4.4, 23, Math.sin(mid) * 45 + Math.sin(mid + Math.PI / 2) * k * 4.4); m.rotation.y = -mid + Math.PI / 2; g.add(m); } }
  // throne dais
  g.add(at(box(14, 1.2, 10, mat('#7a1f2a')), 0, .6, -30));   // dais: put props.throne() at (x, 1.2, z - 32)
  for (const s of [-1, 1]) { const ban = box(3.6, 10, .2, mat(s > 0 ? '#b91c1c' : '#1d4ed8')); at(ban, s * 9, 14, -41); g.add(ban); }
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 8. ice world: snow field, crystal spikes, glowing creatures go here ----------
export function iceWorld(x = 0, z = 0, o = {}) {
  seed(o.seed || 19); const g = new THREE.Group();
  g.add(flat(2000, 2000, mat('#fff', { map: TEX.snow(), roughness: .6 })));
  const ice = mat('#9fd8ff', { roughness: .1, metalness: .1, transparent: true, opacity: .85, emissive: '#3a7ad8', emissiveIntensity: .35 });
  for (let i = 0; i < 160; i++) { const a = R(0, Math.PI * 2), r = R(14, 300), h = R(4, 26); const c = new THREE.Mesh(new THREE.ConeGeometry(R(1, 3.5), h, 5), ice); c.castShadow = true; at(c, Math.cos(a) * r, h / 2 - 1, Math.sin(a) * r); c.rotation.set(R(-.2, .2), R(0, 3), R(-.2, .2)); g.add(c); }
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2, m = new THREE.Mesh(new THREE.ConeGeometry(R(60, 120), R(90, 180), 6), mat('#e8efff', { roughness: .8 })); at(m, Math.cos(a) * 520, 40, Math.sin(a) * 520); g.add(m); }
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 9. beach: sand, sea plane, palm trees ----------
export function beach(x = 0, z = 0, o = {}) {
  seed(o.seed || 23); const g = new THREE.Group();
  g.add(flat(1400, 1400, mat('#fff', { map: TEX.sand(), roughness: 1 })));
  const sea = flat(2400, 1400, mat('#1fa3d8', { roughness: .15, metalness: .2, emissive: '#0a4a7a', emissiveIntensity: .2 }), .3); sea.position.z = -760; g.add(sea); g.userData.sea = sea;
  for (let i = 0; i < 26; i++) { const p = new THREE.Group(), h = R(10, 16); const tr = cyl(.45, .65, h, mat('#a0703a'), 8); tr.position.y = h / 2; tr.rotation.z = R(-.15, .15); p.add(tr); for (let k = 0; k < 6; k++) { const lf = box(.5, .15, 7, mat('#2fa84a')); lf.geometry.translate(0, 0, 3.5); lf.position.y = h; lf.rotation.set(.45, k / 6 * Math.PI * 2, 0); p.add(lf); } at(p, R(-120, 120), 0, R(-50, 60)); g.add(p); }
  g.position.set(x, 0, z); scene.add(g); return g;
}

// ---------- 10. city: road grid with towers ----------
export function city(x = 0, z = 0, o = {}) {
  seed(o.seed || 29); const g = new THREE.Group();
  g.add(flat(1600, 1600, mat('#fff', { map: TEX.road(), roughness: .9 })));
  for (const s of [-1, 1]) g.add(at(box(6, .4, 600, mat('#c8c8c8')), s * 11, .2, -150));
  for (let i = 0; i < 70; i++) { const px = (rnd() < .5 ? -1 : 1) * R(18, 160), pz = R(-420, 60), h = R(20, 90), w = R(10, 22); const b = box(w, h, w, mat('#fff', { map: TEX.tower(pick(['#9ab', '#c9d6e3', '#7a8aa0', '#e3d6c9', '#5a6a80']), o.night ? .45 : .1) })); b.position.set(px, h / 2, pz); g.add(b); }
  for (let i = 0; i < 30; i++) g.add(at(box(.3, .05, 4, mat('#ffffff')), 0, .05, -i * 14 + 40));
  g.position.set(x, 0, z); scene.add(g); return g;
}

export const SETS = { town, party, room, classroom, forest, spookyStreet, castle, iceWorld, beach, city };
