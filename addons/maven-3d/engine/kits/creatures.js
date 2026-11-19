// Creatures: dragons (scary or cute), an instanced flock (dragons/bats/birds), a many-eyed sky beast,
// a tall thin stranger, a ghost, slimes, and blocky pets. Each returns a Group with userData.tick(t).
import { THREE, RoundedBoxGeometry, canvasTex, mat, glow, box, rbox, cyl, ball, at, R, rnd, seed, scene, V } from '../core.js';

function wingGeo(side, shape) {
  const P = (shape || [[0, .4], [4.4, .2], [3.9, -1.0], [3.0, -2.6], [1.8, -1.7], [1.0, -2.8], [0, -1.6]]).map(([x, z]) => V(x * side, 0, z));
  const pos = []; for (let i = 1; i < P.length - 1; i++) pos.push(P[0], P[i], P[i + 1]);
  const g = new THREE.BufferGeometry().setFromPoints(pos); g.computeVertexNormals(); return g;
}
function cuteEyes(head, x, y, z, r = .34) { for (const s of [-1, 1]) { head.add(at(ball(r, mat('#fff', { roughness: .2 }), 2), s * x, y, z), at(ball(r * .5, mat('#111', { roughness: .1 }), 2), s * x, y - .02, z + r * .8), at(ball(r * .18, glow('#fff', 1), 1), s * (x - .04), y + .1, z + r * 1.2)); } }

// ---------- dragon ----------
export function dragon(o = {}) {
  const c = { body: '#2a1d44', belly: '#4b3a72', wing: '#1c1430', horn: '#d6c9a8', eye: '#ffcf3f', ...o };
  const g = new THREE.Group(), bm = mat(c.body, { roughness: .5 }), wm = mat(c.wing, { side: THREE.DoubleSide, roughness: .6 });
  g.add(rbox(2.2, 1.6, 3.8, .45, bm), at(rbox(1.6, .3, 3.0, .12, mat(c.belly)), 0, -.75, .2));
  const neck = rbox(1.1, 1.1, 1.8, .3, bm); neck.position.set(0, .9, 2.1); neck.rotation.x = -.6; g.add(neck);
  const head = new THREE.Group(); head.position.set(0, 1.7, 3.1); g.add(head);
  head.add(rbox(1.6, 1.3, 1.7, .35, bm), at(rbox(1.15, .75, 1.1, .25, bm), 0, -.2, 1.05));
  if (c.cute) { cuteEyes(head, .42, .22, .78); for (const s of [-1, 1]) head.add(at(ball(.14, mat('#ff8fb8'), 1), s * .62, -.15, .7)); }
  else for (const s of [-1, 1]) { const e = box(.5, .2, .12, glow(c.eye, 4)); at(e, s * .45, .28, .86); e.rotation.z = s * .25; head.add(e); }
  for (const s of [-1, 1]) { const h = new THREE.Mesh(new THREE.ConeGeometry(.2, .9, 6), mat(c.horn)); at(h, s * .45, .85, -.4); h.rotation.x = -1.0; head.add(h); }
  for (let i = 0; i < 4; i++) { const sp = new THREE.Mesh(new THREE.ConeGeometry(.22, .6, 5), mat(c.horn)); at(sp, 0, .95, 1.1 - i * .9); sp.rotation.x = -.4; g.add(sp); }
  const wings = []; for (const s of [-1, 1]) { const p = new THREE.Group(); p.position.set(s * .9, .6, .6); const m = new THREE.Mesh(wingGeo(s), wm); m.castShadow = true; p.add(m, at(box(4.4, .22, .22, bm), s * 2.2, .05, .3)); g.add(p); wings.push([p, s]); }
  const tail = []; let par = g; for (let i = 0; i < 5; i++) { const n = new THREE.Group(); n.position.set(0, i ? 0 : -.1, i ? -1.05 : -1.9); const k = 1 - i * .16; n.add(rbox(1.0 * k, .8 * k, 1.2, .2 * k, bm)); par.add(n); tail.push(n); par = n; }
  for (const [x, z] of [[-.7, 1.1], [.7, 1.1], [-.7, -1.1], [.7, -1.1]]) g.add(at(rbox(.5, .9, .6, .12, bm), x, -1.0, z));
  g.userData = { head, wings, tail, tick(t, rate = 5, amp = .75) { for (const [p, s] of wings) p.rotation.z = s * (Math.sin(t * rate) * amp + .15); tail.forEach((n, i) => n.rotation.y = Math.sin(t * 3 - i * .7) * .18); head.rotation.x = Math.sin(t * 2) * .05; } };
  if (c.scale) g.scale.setScalar(c.scale);
  scene.add(g); return g;
}

// ---------- flock: hundreds of instanced flyers on a dome around a centre ----------
// kind: 'dragon' | 'bat' | 'bird'; they start spread on a shell and drift with velocity v (units/s) from time t0
export function flock(o = {}) {
  const N = o.n || 900, kind = o.kind || 'dragon', ctr = o.center || V(0, 0, 0); seed(o.seed || 99);
  const L = [];
  for (let i = 0; i < N; i++) { const az = R(0, Math.PI * 2), el = R(o.elMin ?? .12, o.elMax ?? 1.25), r = R(o.rMin || 140, o.rMax || 520); L.push({ p: V(ctr.x + Math.cos(az) * Math.cos(el) * r, (o.y0 ?? 25) + Math.sin(el) * r * .8, ctr.z + Math.sin(az) * Math.cos(el) * r), v: V(R(10, 22), R(-1, 1), R(-6, 6)).multiplyScalar(o.speed ?? 1), ph: R(0, 6), rate: R(4, 6.5) * (kind === 'bird' ? 1.6 : kind === 'bat' ? 2.4 : 1), s: R(2.2, 3.6) * (o.size || (kind === 'dragon' ? 1 : kind === 'bat' ? .5 : .4)) }); }
  const col = o.col || (kind === 'dragon' ? '#3d2c63' : kind === 'bat' ? '#1a1420' : '#2a2a30');
  const fB = mat(col, { roughness: .5 }), fW = mat(new THREE.Color(col).multiplyScalar(.8).getStyle(), { side: THREE.DoubleSide, roughness: .6 }), fE = glow(o.eye || '#ffc43a', 6);
  const g = new THREE.Group(); scene.add(g);
  const IM = (geo, m) => { const im = new THREE.InstancedMesh(geo, m, N); im.frustumCulled = false; g.add(im); return im; };
  const body = IM(new RoundedBoxGeometry(2.2, 1.5, 3.8, 2, .4), fB), head = IM(new RoundedBoxGeometry(1.4, 1.1, 2.2, 2, .3), fB), tl = IM(new THREE.BoxGeometry(.8, .6, 3.4), fB);
  const wl = IM(wingGeo(1), fW), wr = IM(wingGeo(-1), fW), eye = kind === 'bird' ? null : IM(new THREE.BoxGeometry(1.1, .22, .1), fE);
  const local = (x, y, z, rx = 0, ry = 0, rz = 0) => new THREE.Matrix4().compose(V(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz)), V(1, 1, 1));
  const LH = local(0, .9, 2.6, -.15), LT = local(0, -.1, -3.4, .1), LE = local(0, 1.05, 3.72), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), s = new THREE.Vector3(), O = new THREE.Matrix4();
  const t0 = o.t0 ?? 7;
  g.userData.tick = (t) => {
    for (let i = 0; i < N; i++) { const f = L[i], p = f.p.clone().addScaledVector(f.v, t - t0), yaw = Math.atan2(f.v.x, f.v.z);
      O.compose(p, q.setFromEuler(e.set(Math.sin(t * 2 + f.ph) * .08, yaw, Math.sin(t * 1.3 + f.ph) * .15)), s.setScalar(f.s));
      body.setMatrixAt(i, O); head.setMatrixAt(i, m.multiplyMatrices(O, LH)); tl.setMatrixAt(i, m.multiplyMatrices(O, LT)); if (eye) eye.setMatrixAt(i, m.multiplyMatrices(O, LE));
      const fl = Math.sin(t * f.rate + f.ph) * .8 + .15; wl.setMatrixAt(i, m.multiplyMatrices(O, local(.9, .5, .5, 0, 0, fl))); wr.setMatrixAt(i, m.multiplyMatrices(O, local(-.9, .5, .5, 0, 0, -fl))); }
    for (const im of [body, head, tl, wl, wr, eye]) if (im) im.instanceMatrix.needsUpdate = true;
  };
  return g;
}

// ---------- the sky beast: a black mass covered in glowing eyes, with tentacles ----------
export function beast(o = {}) {
  seed(o.seed || 31); const g = new THREE.Group(), bm = mat(o.col || '#0c0a12', { roughness: .4 }), eyes = [];
  g.add(ball(10, bm, 2)); for (let i = 0; i < 9; i++) g.add(at(ball(R(4, 7), bm, 2), R(-10, 10), R(-5, 6), R(-8, 8)));
  for (let i = 0; i < (o.eyes || 46); i++) { const d = V(R(-1, 1), R(-.6, 1), R(.1, 1)).normalize(), e = new THREE.Group(); e.position.copy(d.multiplyScalar(10.4)); e.lookAt(e.position.clone().multiplyScalar(2)); const r = R(.5, 1.3); e.add(at(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), glow(o.eye || '#ffcc33', 3)), 0, 0, 0), at(new THREE.Mesh(new THREE.SphereGeometry(r * .45, 10, 8), mat('#000')), 0, 0, r * .7)); g.add(e); eyes.push(e); }
  const tents = []; for (let i = 0; i < (o.tentacles || 8); i++) { const a = i / 8 * Math.PI * 2, root = new THREE.Group(); root.position.set(Math.cos(a) * 8, -6, Math.sin(a) * 8); g.add(root); let par = root; const segs = []; for (let k = 0; k < 8; k++) { const n = new THREE.Group(); n.position.y = k ? -3 : 0; n.add(at(cyl(1.4 - k * .14, 1.5 - k * .14, 3.2, bm, 10), 0, -1.6, 0)); par.add(n); segs.push(n); par = n; } tents.push([root, segs, a]); }
  g.userData = { eyes, tick(t, look) { tents.forEach(([r, segs, a], i) => segs.forEach((n, k) => { n.rotation.x = Math.sin(t * 1.6 + i + k * .5) * .25; n.rotation.z = Math.cos(t * 1.3 + i * 2 + k * .4) * .25; })); if (look) eyes.forEach(e => e.lookAt(look)); } };
  if (o.scale) g.scale.setScalar(o.scale); scene.add(g); return g;
}

// ---------- tall thin stranger (horror): long limbs, wide grin, glowing chest dial ----------
export function stranger(o = {}) {
  const g = new THREE.Group(), sk = mat(o.skin || '#e8e4dc'), cl = mat(o.col || '#2a3a2a');
  const H = o.height || 11; g.add(at(box(1.6, H * .38, .9, cl), 0, H * .62, 0));
  for (const s of [-1, 1]) { g.add(at(box(.5, H * .55, .5, cl), s * .45, H * .27, 0)); const arm = new THREE.Group(); arm.position.set(s * 1.05, H * .8, 0); arm.add(at(box(.4, H * .55, .4, sk), 0, -H * .27, 0)); g.add(arm); g.userData['arm' + (s > 0 ? 'L' : 'R')] = arm; }
  const head = new THREE.Group(); head.position.y = H * .82; g.add(head);
  head.add(at(rbox(1.5, 1.7, 1.3, .3, sk), 0, .85, 0));
  const fc = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.7), new THREE.MeshStandardMaterial({ map: canvasTex(256, 290, (c) => { c.fillStyle = '#000'; for (const x of [80, 176]) { c.beginPath(); c.ellipse(x, 110, 22, 30, 0, 0, 7); c.fill(); } c.beginPath(); c.moveTo(30, 175); c.quadraticCurveTo(128, 260, 226, 175); c.quadraticCurveTo(128, 215, 30, 175); c.fill(); c.fillStyle = '#fff'; for (let x = 45; x < 215; x += 18) c.fillRect(x, 182 + Math.sin((x - 45) / 170 * Math.PI) * 18, 10, 14); }), transparent: true }));
  fc.position.set(0, .85, .66); head.add(fc);
  const dial = new THREE.Mesh(new THREE.CircleGeometry(.6, 32), glow(o.dial || '#ffe08a', 2)); dial.position.set(0, H * .66, .46); g.add(dial);
  g.userData.head = head; g.userData.tick = (t) => { head.rotation.z = Math.sin(t * .9) * .12; dial.material.emissiveIntensity = 1.5 + Math.sin(t * 12) * .8; };
  scene.add(g); return g;
}

// ---------- ghost ----------
export function ghost(o = {}) {
  const g = new THREE.Group(), m = mat('#f4f6ff', { transparent: true, opacity: o.opacity ?? .82, emissive: '#bfd0ff', emissiveIntensity: .4 });
  g.add(at(ball(1.6, m, 3), 0, 3.6, 0), at(cyl(1.6, 1.9, 3.2, m, 24), 0, 1.9, 0)); for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; g.add(at(ball(.45, m, 1), Math.cos(a) * 1.7, .3, Math.sin(a) * 1.7)); }
  for (const s of [-1, 1]) g.add(at(new THREE.Mesh(new THREE.SphereGeometry(.28, 12, 8), mat('#111')), s * .55, 3.9, 1.45));
  g.add(at(new THREE.Mesh(new THREE.SphereGeometry(.32, 12, 8), mat('#111')), 0, 3.1, 1.5));
  g.userData.tick = (t) => { g.children[0].position.y = 3.6 + Math.sin(t * 2) * .2; };
  scene.add(g); return g;
}

// ---------- slime ----------
export function slime(o = {}) {
  const g = new THREE.Group(), m = mat(o.col || '#5ee86a', { transparent: true, opacity: .88, roughness: .15, emissive: o.col || '#5ee86a', emissiveIntensity: .15 });
  const b = new THREE.Mesh(new THREE.SphereGeometry(1.6, 32, 20, 0, Math.PI * 2, 0, Math.PI * .55), m); b.castShadow = true; g.add(b);
  const head = new THREE.Group(); g.add(head); cuteEyes(head, .55, .8, 1.15, .3);
  g.userData.tick = (t) => { const k = 1 + Math.sin(t * 6) * .07; b.scale.set(k, 2 - k, k); };
  scene.add(g); return g;
}

// ---------- blocky pets ----------
export function pet(o = {}) {
  const kind = o.kind || 'dog', c = o.col || (kind === 'cat' ? '#f59e0b' : '#c08a52'), m = mat(c), g = new THREE.Group();
  g.add(at(rbox(1.4, 1.2, 2.6, .25, m), 0, 1.6, 0));
  const head = new THREE.Group(); head.position.set(0, 2.5, 1.5); g.add(head); head.add(rbox(1.4, 1.2, 1.2, .3, m)); cuteEyes(head, .32, .15, .58, .22);
  if (kind === 'dog') { head.add(at(rbox(.7, .5, .6, .15, m), 0, -.3, .7), at(ball(.14, mat('#111'), 1), 0, -.15, 1.0)); for (const s of [-1, 1]) { const e = rbox(.3, .9, .5, .1, mat(new THREE.Color(c).multiplyScalar(.7).getStyle())); at(e, s * .8, .1, 0); e.rotation.z = s * .3; head.add(e); } }
  else for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.ConeGeometry(.3, .6, 4), m); at(e, s * .45, .8, 0); head.add(e); }
  const legs = []; for (const [x, z] of [[-.45, .9], [.45, .9], [-.45, -.9], [.45, -.9]]) { const l = new THREE.Group(); l.position.set(x, 1.1, z); l.add(at(box(.4, 1.1, .4, m), 0, -.55, 0)); g.add(l); legs.push(l); }
  const tail = new THREE.Group(); tail.position.set(0, 2.0, -1.3); tail.add(at(box(.25, .25, 1.2, m), 0, 0, -.6)); g.add(tail);
  g.userData = { head, tick(t, moving = 0) { tail.rotation.y = Math.sin(t * 14) * .5; tail.rotation.x = -.6; legs.forEach((l, i) => l.rotation.x = moving * Math.sin(t * 12 + (i % 2) * Math.PI) * .6); } };
  scene.add(g); return g;
}

export const CREATURES = { dragon, flock, beast, stranger, ghost, slime, pet };
