// Procedural geometry helpers for the clay world.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { clay } from './clay.js';

export const sphere = (r, seg = 40) => new THREE.SphereGeometry(r, seg, Math.round(seg * 0.75));
export const rbox = (w, h, d, r = 0.06, seg = 4) => new RoundedBoxGeometry(w, h, d, seg, r);

export function mesh(geo, mat, { pos = [0, 0, 0], rot = [0, 0, 0], scl = [1, 1, 1], shadow = true } = {}) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...pos); m.rotation.set(...rot); m.scale.set(...scl);
  m.castShadow = shadow; m.receiveShadow = true;
  return m;
}

// A bean / pebble made with a lathe profile: r(y) for y in [0, h].
export function bean(h = 0.8, rBot = 0.34, rMid = 0.37, rTop = 0.3, seg = 48) {
  const pts = [];
  const N = 40;
  for (let i = 0; i <= N; i++) {
    const u = i / N;
    const y = u * h;
    // base profile with a rounded bottom and dome top
    let r = THREE.MathUtils.lerp(rBot, rMid, Math.sin(Math.min(1, u / 0.35) * Math.PI / 2));
    if (u > 0.35) r = THREE.MathUtils.lerp(rMid, rTop, (u - 0.35) / 0.4);
    if (u > 0.72) r = rTop * Math.sqrt(Math.max(0, 1 - Math.pow((u - 0.72) / 0.28, 2)));
    if (u < 0.08) r *= Math.sqrt(Math.max(0.0, u / 0.08)) * 0.9 + 0.1;
    pts.push(new THREE.Vector2(Math.max(0.0001, r), y));
  }
  const g = new THREE.LatheGeometry(pts, seg);
  g.computeVertexNormals();
  return g;
}

// radius of the bean at height y (for placing faces on the surface)
export function beanR(y, h = 0.8, rBot = 0.34, rMid = 0.37, rTop = 0.3) {
  const u = y / h;
  let r = THREE.MathUtils.lerp(rBot, rMid, Math.sin(Math.min(1, u / 0.35) * Math.PI / 2));
  if (u > 0.35) r = THREE.MathUtils.lerp(rMid, rTop, (u - 0.35) / 0.4);
  if (u > 0.72) r = rTop * Math.sqrt(Math.max(0, 1 - Math.pow((u - 0.72) / 0.28, 2)));
  return r;
}

export function capsule(r, len) { return new THREE.CapsuleGeometry(r, len, 8, 20); }

// soft contact shadow (fake AO) — a radial gradient disc
let aoTex = null;
export function contactShadow(rx, rz = rx, opacity = 0.45) {
  if (!aoTex) {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 4, 64, 64, 64);
    gr.addColorStop(0, 'rgba(40,20,30,1)'); gr.addColorStop(0.5, 'rgba(40,20,30,0.45)'); gr.addColorStop(1, 'rgba(40,20,30,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
    aoTex = new THREE.CanvasTexture(c);
  }
  const m = new THREE.Mesh(new THREE.PlaneGeometry(rx * 2, rz * 2), new THREE.MeshBasicMaterial({ map: aoTex, transparent: true, opacity, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.renderOrder = 1;
  return m;
}

// gradient sky dome
export function skyDome(r, top, bottom, mid) {
  const g = new THREE.SphereGeometry(r, 32, 20);
  const cols = []; const p = g.attributes.position;
  const ct = new THREE.Color(top), cb = new THREE.Color(bottom), cm = new THREE.Color(mid ?? bottom);
  for (let i = 0; i < p.count; i++) {
    const u = (p.getY(i) / r + 1) / 2;
    const c = u > 0.5 ? cm.clone().lerp(ct, (u - 0.5) * 2) : cb.clone().lerp(cm, u * 2);
    cols.push(c.r, c.g, c.b);
  }
  g.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
  return new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false }));
}

// a blobby cluster (tree crowns, bushes, clouds)
export function blob(color, r = 0.5, n = 6, seed = 1, opts = {}) {
  const grp = new THREE.Group();
  let s = seed;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < n; i++) {
    const rr = r * (0.55 + rnd() * 0.45);
    const a = rnd() * Math.PI * 2, e = (rnd() - 0.3) * 0.9;
    const d = i === 0 ? 0 : r * 0.55;
    grp.add(mesh(sphere(rr, 28), clay(color, opts), { pos: [Math.cos(a) * d * Math.cos(e), Math.sin(e) * d * 0.7, Math.sin(a) * d * Math.cos(e)] }));
  }
  return grp;
}

export function rng(seed) { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; }
