// The pond world, the rescue choreography (GSAP) and the camera.
import * as THREE from 'three';
import gsap from 'gsap';
import { clay, glow, gloss } from './clay.js';
import { sphere, rbox, mesh, skyDome, blob, contactShadow, rng, capsule } from './shapes.js';
import { createBuddy } from './buddy.js';
import { createMan } from './man.js';
import { createCat } from './cat.js';

export const DURATION = 20;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const WATER_Y = -0.08;
const K0 = V(0.55, WATER_Y, -0.35);           // kitten in the water
const POST = V(-2.9, 0, 3.8);
const W0 = V(-4.8, 0.03, 3.5), W1 = V(-2.65, 0.03, 3.05);
const B = V(-1.3, 0.03, 2.75);                // the bank where the buddy throws
const LAND = K0.clone().add(V(-0.18, 0, 0.32));
const SHORE = V(-0.95, WATER_Y, 2.05);
const OUT = V(-0.82, 0.03, 2.42);

function waterMaterial() {
  const m = new THREE.MeshStandardMaterial({ color: 0x77c6cf, roughness: 0.12, metalness: 0.05, transparent: true, opacity: 0.86 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uT = { value: 0 }; m.userData.sh = sh;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uT; varying vec3 vW;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vW = (modelMatrix * vec4(position,1.0)).xyz;`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform float uT; varying vec3 vW;')
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          vec2 p = vW.xz;
          float a = sin(p.x*7.0 + uT*1.7) * cos(p.y*6.0 - uT*1.3);
          float b = sin((p.x+p.y)*11.0 - uT*2.3);
          vec3 g = vec3(a*0.08 + b*0.05, 0.0, cos(p.x*5.0 - uT)*0.06 + b*0.04);
          normal = normalize(normal + (viewMatrix * vec4(g, 0.0)).xyz);
        }`);
  };
  return m;
}

function lifebuoy() {
  const g = new THREE.Group();
  for (let i = 0; i < 8; i++) {
    const seg = mesh(new THREE.TorusGeometry(0.2, 0.06, 16, 12, Math.PI / 4), clay(i % 2 ? 0xfff5ee : 0xf06a6a, { bump: 0.3 }), { rot: [0, 0, (i * Math.PI) / 4] });
    g.add(seg);
  }
  return g;
}

export function buildPond() {
  const scene = new THREE.Scene();
  scene.add(skyDome(60, 0x6fa6e6, 0xffc9a8, 0xf9d9c8));
  scene.fog = new THREE.Fog(0xf6d2bc, 14, 42);
  // distant soft hills and bushes so the horizon is never empty
  for (let i = 0; i < 22; i++) {
    const a = (i / 22) * Math.PI * 2, d = 27 + (i % 3) * 3;
    scene.add(mesh(sphere(4 + (i % 4) * 0.8, 32), clay([0x9fcf98, 0xb6d7a0, 0xc9b8e0, 0x8cc4a6][i % 4], { bump: 0.4, rim: 0.3 }), { pos: [Math.cos(a) * d, -2.2, Math.sin(a) * d], scl: [1.8, 0.62, 1.2], shadow: false }));
  }
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2 + 0.11, d = 9.5 + (i % 3) * 0.8;
    const b = blob([0x8fc98a, 0xa6d69a, 0x7fbf9a][i % 3], 0.55 + (i % 4) * 0.12, 5, 100 + i); b.position.set(Math.cos(a) * d, 0.25, Math.sin(a) * d); scene.add(b);
  }
  scene.add(new THREE.HemisphereLight(0xfff4ec, 0x8aa07a, 1.1));
  const sun = new THREE.DirectionalLight(0xffd2a0, 2.8);
  sun.position.set(-5, 6, 6); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02;
  Object.assign(sun.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 1, far: 30 });
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0xb8d0ff, 1.0); rim.position.set(5, 3, -6); scene.add(rim);

  // ground with the pond basin (lathe profile)
  const prof = [[0.001, -0.5], [2.2, -0.5], [2.6, -0.3], [2.85, -0.05], [3.0, 0.03], [3.3, 0.04], [45, 0.04]].map(([r, y]) => new THREE.Vector2(r, y));
  const groundM = clay(0xa9d68e, { bump: 0.8, freq: 5 }).clone(); groundM.onBeforeCompile = clay(0xa9d68e, { bump: 0.8, freq: 5 }).onBeforeCompile; groundM.side = THREE.DoubleSide;
  scene.add(mesh(new THREE.LatheGeometry(prof, 128), groundM, { scl: [1, 1, 0.85] }));
  scene.add(mesh(new THREE.CylinderGeometry(2.4, 2.4, 0.02, 64), clay(0xe8d2a8), { pos: [0, -0.49, 0], scl: [1, 1, 0.85] }));
  const water = mesh(new THREE.CircleGeometry(2.95, 96), waterMaterial(), { pos: [0, WATER_Y, 0], rot: [-Math.PI / 2, 0, 0], scl: [1, 0.85, 1], shadow: false });
  water.castShadow = false; scene.add(water);
  const r = rng(5);
  // rim stones, reeds, lily pads
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2 + r() * 0.1;
    if (a > 1.7 && a < 2.3) continue;                          // keep the throwing spot clear
    scene.add(mesh(sphere(0.16 + r() * 0.12, 24), clay([0xc8c0d8, 0xd8cfc0, 0xb8c4c8][i % 3], { bump: 0.7 }), { pos: [Math.cos(a) * 2.95, 0.03, Math.sin(a) * 2.95 * 0.85], scl: [1.3, 0.6, 1.1] }));
  }
  for (let i = 0; i < 14; i++) {
    const a = 3.6 + r() * 1.6; const d = 2.5 + r() * 0.3;
    const x = Math.cos(a) * d, z = Math.sin(a) * d * 0.85; const h = 0.6 + r() * 0.5;
    scene.add(mesh(capsule(0.018, h), clay(0x6fb070), { pos: [x, WATER_Y + h / 2, z], rot: [(r() - 0.5) * 0.2, 0, (r() - 0.5) * 0.2] }));
    if (i % 2) scene.add(mesh(capsule(0.035, 0.12), clay(0x9a6a4a), { pos: [x, WATER_Y + h, z] }));
  }
  const pads = [V(1.4, WATER_Y + 0.01, 0.6), V(-0.6, WATER_Y + 0.01, -1.2), V(1.7, WATER_Y + 0.01, -0.8), V(-1.6, WATER_Y + 0.01, 0.3)];
  pads.forEach((p, i) => {
    scene.add(mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.02, 40, 1, false, 0.3, Math.PI * 2 - 0.6), clay(0x7fc47a), { pos: p.toArray(), rot: [0, i * 1.3, 0] }));
    if (i === 0) {
      const f = new THREE.Group(); f.position.copy(p).add(V(0, 0.05, 0));
      for (let k = 0; k < 6; k++) f.add(mesh(sphere(0.06, 16), clay(0xffb6cc), { pos: [Math.cos(k) * 0.05, 0.02, Math.sin(k) * 0.05], scl: [0.6, 1, 0.6], rot: [0, -k, 0.5] }));
      f.add(mesh(sphere(0.03, 12), clay(0xffe07a))); scene.add(f);
    }
  });
  // park: trees, bushes, bench, lamp, flowers
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2 + 0.3; const d = 5 + r() * 3;
    const x = Math.cos(a) * d, z = Math.sin(a) * d * 0.9;
    const h = 1.0 + r() * 0.8;
    scene.add(mesh(new THREE.CylinderGeometry(0.09, 0.14, h, 12), clay(0xb38a6e), { pos: [x, h / 2, z] }));
    const c = blob([0x9fd69a, 0x8cc9a8, 0xf0b8c8, 0xb6e08f][i % 4], 0.6 + r() * 0.3, 7, i + 3); c.position.set(x, h + 0.35, z); scene.add(c);
  }
  for (let i = 0; i < 30; i++) {
    const a = r() * Math.PI * 2; const d = 3.4 + r() * 2.5;
    const x = Math.cos(a) * d, z = Math.sin(a) * d * 0.88;
    if (Math.hypot(x - B.x, z - B.z) < 1.2 || Math.hypot(x - W1.x, z - W1.z) < 1.0 || (z > 2.6 && x > -5.5 && x < -2)) continue;
    scene.add(mesh(capsule(0.012, 0.16), clay(0x6fb070), { pos: [x, 0.12, z] }));
    scene.add(mesh(sphere(0.045, 12), clay([0xffb6cc, 0xfff07a, 0xc6b0ff, 0xffffff][i % 4]), { pos: [x, 0.24, z] }));
  }
  scene.add(mesh(rbox(1.1, 0.08, 0.36, 0.03), clay(0xd99a6a), { pos: [2.6, 0.42, 3.0], rot: [0, -0.5, 0] }));
  scene.add(mesh(rbox(1.1, 0.36, 0.06, 0.03), clay(0xd99a6a), { pos: [2.72, 0.66, 2.83], rot: [0, -0.5, 0] }));
  for (const sx of [-0.45, 0.45]) scene.add(mesh(rbox(0.06, 0.42, 0.3, 0.02), clay(0x8a6a5a), { pos: [2.6 + sx * Math.cos(0.5), 0.21, 3.0 + sx * Math.sin(0.5)], rot: [0, -0.5, 0] }));
  // the lifebuoy post
  scene.add(mesh(new THREE.CylinderGeometry(0.05, 0.06, 1.3, 14), clay(0xb38a6e), { pos: [POST.x, 0.65, POST.z] }));
  scene.add(mesh(capsule(0.025, 0.12), clay(0x8a6a5a), { pos: [POST.x, 1.15, POST.z - 0.08], rot: [Math.PI / 2, 0, 0] }));
  scene.add(contactShadow(0.25, 0.25, 0.35).translateX(POST.x).translateY(0.045).translateZ(POST.z));

  // characters and props
  const buddy = createMan();
  scene.add(buddy.root);
  const cat = createCat();
  scene.add(cat.root);
  const ring = lifebuoy(); scene.add(ring);
  const ropeMat = clay(0xf2e4c4, { bump: 0.6, freq: 30 });
  let rope = null;
  const ripples = [];
  for (let i = 0; i < 4; i++) {
    const m = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.012, 8, 48), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, depthWrite: false }));
    m.rotation.x = Math.PI / 2; scene.add(m); ripples.push(m);
  }
  const splashN = 40;
  const splash = new THREE.InstancedMesh(sphere(0.014, 10), gloss(0xd8f6ff, 0.05), splashN); scene.add(splash);
  const hearts = [];
  for (let i = 0; i < 5; i++) {
    const h = new THREE.Group();
    h.add(mesh(sphere(0.05, 16), clay(0xff7a9a), { pos: [-0.032, 0, 0] }), mesh(sphere(0.05, 16), clay(0xff7a9a), { pos: [0.032, 0, 0] }));
    h.add(mesh(new THREE.ConeGeometry(0.068, 0.09, 20), clay(0xff7a9a), { pos: [0, -0.05, 0], rot: [Math.PI, 0, 0] }));
    scene.add(h); hearts.push(h);
  }

  // ---------------------------------------------------------------- choreography (GSAP, scrubbed by seek)
  const bs = buddy.state, cs = cat.state;
  const k = { walk: 0, run1: 0, run2: 0, face: Math.PI / 2, throwU: -1, pull: 0, pullOsc: 0, catSwim: 0, catHop: 0, pick: 0, hug: 0, heart: 0, cam: 0, ringBob: 1 };
  const tl = gsap.timeline({ paused: true });
  Object.assign(bs, { mouth: 'smile', look: [0, -0.2] });
  Object.assign(cs, { paddle: 1, eyes: 1.25, mouth: 'o', wet: 1 });
  tl.to(k, { walk: 1, duration: 1.7, ease: 'none' }, 1.9)
    .to(bs, { stride: 0.9, duration: 0.2 }, 1.9).to(bs, { stride: 0, duration: 0.2 }, 3.55)
    .to(bs, { look: [0.8, 0.1], duration: 0.2 }, 3.6)
    .to(k, { face: 2.6, duration: 0.3, ease: 'power2.out' }, 3.62)
    .to(bs, { squash: -0.1, duration: 0.15, ease: 'power2.in' }, 3.7)
    .set(bs, { mouth: 'oh', brow: 1, mouthOpen: 1 }, 3.85)
    .to(bs, { squash: 0.14, bounce: 0.12, duration: 0.15, ease: 'power2.out' }, 3.85)
    .to(bs, { squash: 0, bounce: 0, duration: 0.45, ease: 'elastic.out(1,0.4)' }, 4.0)
    .to(k, { face: -0.34, duration: 0.25 }, 4.3)                       // turn to the post
    .to(k, { run1: 1, duration: 0.5, ease: 'power1.inOut' }, 4.4)
    .to(k, { face: 1.79, duration: 0.25 }, 5.0)
    .to(k, { run2: 1, duration: 1.4, ease: 'power1.inOut' }, 5.15)
    .to(bs, { stride: 1.2, lean: 0.25, duration: 0.2 }, 5.15).to(bs, { stride: 0, lean: 0, duration: 0.2 }, 6.5)
    .set(bs, { mouth: 'grin', brow: -0.6 }, 5.2)
    .to(k, { throwU: 0, duration: 0.01 }, 6.7)                          // wind-up
    .to(bs, { lean: -0.28, squash: 0.08, duration: 0.6, ease: 'power2.out' }, 6.7)
    .to(bs, { lean: 0.32, squash: -0.08, duration: 0.18, ease: 'power3.in' }, 7.4)
    .to(k, { throwU: 1, duration: 0.85, ease: 'none' }, 7.58)
    .to(bs, { lean: 0, squash: 0, duration: 0.6, ease: 'elastic.out(1,0.5)' }, 7.6)
    .set(bs, { mouth: 'oh', brow: 1 }, 7.8)
    .to(k, { catSwim: 1, duration: 0.9, ease: 'power2.inOut' }, 8.5)
    .set(cs, { mouth: 'w', eyes: 1.05 }, 9.3)
    .set(bs, { mouth: 'grin', brow: -0.4 }, 9.3)
    .to(k, { pull: 1, duration: 2.8, ease: 'power1.inOut' }, 9.4)
    .to(k, { pullOsc: 1, duration: 0.2 }, 9.4).to(k, { pullOsc: 0, duration: 0.3 }, 12.0)
    .to(k, { catHop: 1, duration: 0.8, ease: 'none' }, 12.3)
    .set(cs, { paddle: 0, mouth: 'o', eyes: 1.15 }, 12.3)
    .to(cs, { squash: -0.15, duration: 0.1 }, 13.1).to(cs, { squash: 0, duration: 0.4, ease: 'elastic.out(1,0.4)' }, 13.2)
    .set(bs, { mouth: 'grin', brow: 0.6 }, 12.6)
    .to(cs, { shake: 1, blink: 0.9, duration: 0.1 }, 13.6).to(cs, { shake: 0, blink: 0, duration: 0.2 }, 14.6)
    .set(cs, { wet: 0, mouth: 'w' }, 14.6)
    .to(bs, { bounce: 0.04, duration: 0.15, yoyo: true, repeat: 3 }, 13.7)
    .to(k, { pick: 1, duration: 0.8, ease: 'power2.inOut' }, 15.1)
    .to(bs, { squash: -0.12, lean: 0.22, duration: 0.35 }, 15.1).to(bs, { squash: 0, lean: 0, duration: 0.5, ease: 'back.out(2)' }, 15.5)
    .to(k, { hug: 1, duration: 0.5 }, 15.9)
    .to(bs, { blink: 0.85, duration: 0.3 }, 16.1)
    .to(cs, { blink: 0.85, duration: 0.3 }, 16.3)
    .to(k, { heart: 1, duration: 3.7, ease: 'none' }, 16.2)
    .to({}, { duration: 0.01 }, DURATION - 0.01);

  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sv = new THREE.Vector3(), tmp = new THREE.Vector3();
  const lerpV = (a, b, u) => a.clone().lerp(b, u);
  function ringPos(t) {
    // returns world position + whether flat on water
    if (k.throwU < 0) {
      if (t < 4.85) return { p: POST.clone().add(V(0, 0.95, -0.12)), flat: false };
      return { p: null, flat: false };            // in the hands
    }
    if (k.throwU < 1 && t < 8.45) {
      const u = k.throwU; const a = handMid(); const p = lerpV(a, LAND, u); p.y += Math.sin(u * Math.PI) * 1.1;
      return { p, flat: u > 0.6, spin: u };
    }
    const base = lerpV(LAND, SHORE, k.pull);
    base.y = WATER_Y + 0.02 + 0.015 * Math.sin(t * 3) * k.ringBob;
    return { p: base, flat: true };
  }
  function handMid() { return buddy.arms[0].hand.getWorldPosition(new THREE.Vector3()).add(buddy.arms[1].hand.getWorldPosition(new THREE.Vector3())).multiplyScalar(0.5); }

  return {
    scene, buddy, cat, water, ring,
    update(t) {
      tl.seek(t, false);
      // ---------------- buddy position / facing
      let pos;
      if (t < 4.4) pos = lerpV(W0, W1, k.walk);
      else if (t < 5.15) pos = lerpV(W1, POST.clone().add(V(0.2, 0.03, -0.45)), Math.sin(k.run1 * Math.PI) * 0.8);
      else pos = lerpV(W1, B, k.run2);
      buddy.root.position.copy(pos);
      const toCat = Math.atan2(K0.x - B.x, K0.z - B.z);
      buddy.root.rotation.y = t < 6.6 ? k.face : toCat;
      bs.phase = t * (k.run2 > 0 && k.run2 < 1 ? 15 : 10);
      // arms
      const sw = Math.sin(bs.phase) * 0.6 * Math.min(1, bs.stride);
      bs.handL = bs.handR = null;
      bs.armL = [0.25, sw]; bs.armR = [0.25, -sw];
      if (t > 4.5 && t < 4.95) { bs.handL = [-0.1, 0.95, 0.15]; bs.handR = [0.1, 0.95, 0.15]; }          // reach up for the ring
      if (t >= 4.95 && t < 6.7) { bs.handL = [-0.2, 0.42, 0.28]; bs.handR = [0.2, 0.42, 0.28]; }          // carry it
      if (t >= 6.7 && t < 7.58) { const u = Math.min(1, (t - 6.7) / 0.6); bs.handL = [-0.17, 0.5 + 0.55 * u, 0.2 - 0.25 * u]; bs.handR = [0.17, 0.5 + 0.55 * u, 0.2 - 0.25 * u]; }
      if (t >= 7.58 && t < 8.0) { bs.handL = [-0.15, 0.62, 0.42]; bs.handR = [0.15, 0.62, 0.42]; }
      if (t >= 8.0 && t < 9.4) { bs.handL = [-0.2, 0.62, 0.3]; bs.handR = [0.2, 0.62, 0.3]; }            // hands to the face, worried
      if (t >= 9.4 && t < 12.3) {                                                                        // hand over hand
        const ph = t * 6;
        bs.handL = [-0.08, 0.45 + 0.06 * Math.sin(ph), 0.3 + 0.12 * Math.sin(ph)];
        bs.handR = [0.08, 0.45 - 0.06 * Math.sin(ph), 0.3 - 0.12 * Math.sin(ph)];
        bs.lean = -0.18 - 0.08 * Math.sin(ph) * k.pullOsc; bs.squash = 0.04 * Math.sin(ph * 2) * k.pullOsc;
      }
      if (t >= 15.1) { const u = k.pick; bs.handL = [-0.14, lerp(0.15, 0.42, u), 0.32]; bs.handR = [0.14, lerp(0.15, 0.42, u), 0.32]; }
      buddy.state.tilt = t > 16 ? 0.1 * Math.sin(t * 2.2) : 0;
      buddy.update();

      // ---------------- ring
      const rp = ringPos(t);
      if (rp.p) { ring.position.copy(rp.p); ring.rotation.set(rp.flat ? Math.PI / 2 : (rp.spin ?? 0) * 6, 0, 0); }
      else { ring.position.copy(handMid()).add(tmp.set(0, 0.02, 0)); ring.rotation.set(Math.PI / 2 - 0.3, buddy.root.rotation.y, 0); if (t >= 6.7 && t < 7.6) ring.rotation.set(0.4, buddy.root.rotation.y, 0); }

      // ---------------- rope (from ring to the buddy's hands) once thrown
      if (rope) { scene.remove(rope); rope.geometry.dispose(); rope = null; }
      if (t > 7.6 && t < 12.6) {
        const a = handMid(), b = ring.position.clone().add(V(0, 0.06, 0));
        const mid = a.clone().lerp(b, 0.5); mid.y -= t < 9.4 ? 0.35 : 0.08;
        rope = new THREE.Mesh(new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(a, mid, b), 30, 0.012, 6), ropeMat);
        rope.castShadow = true; scene.add(rope);
      }

      // ---------------- kitten
      let cp, cy = 0;
      if (t < 8.5) { cp = K0.clone().add(V(0.05 * Math.sin(t * 2.1), 0, 0.04 * Math.cos(t * 1.7))); cy = -0.16 + 0.025 * Math.sin(t * 6); }
      else if (t < 9.4) { cp = lerpV(K0, LAND.clone().add(V(0, 0, -0.12)), k.catSwim); cy = lerp(-0.16, 0.0, Math.max(0, (k.catSwim - 0.6) / 0.4)); }
      else if (t < 12.3) { cp = ring.position.clone().add(V(0, 0, -0.06)); cy = 0.0; }
      else if (t < 15.1) {
        const u = k.catHop; cp = lerpV(SHORE.clone().add(V(0, 0, -0.06)), OUT, u); cy = Math.sin(u * Math.PI) * 0.35 + lerp(0.0, 0.0, u);
        if (u >= 1) cp = OUT.clone();
      } else {
        const hands = handMid();
        cp = lerpV(OUT, hands.clone().add(V(0, -0.2, 0)), k.pick); cy = 0;
      }
      cat.root.position.copy(cp); cat.root.position.y += cy;
      cat.root.rotation.y = t < 12.3 ? Math.atan2(B.x - cp.x, B.z - cp.z) + 0.4 * Math.sin(t * 1.3) * (t < 8.5 ? 1 : 0) : (t < 15.1 ? Math.atan2(-cp.x, -cp.z) : buddy.root.rotation.y);
      cs.look = t < 8.5 ? [0.6 * Math.sin(t * 1.5), 0.3] : [0, 0.3];
      cs.headTilt = t < 8.5 ? 0.15 * Math.sin(t * 3.1) : (t > 15.9 ? 0.25 : 0);
      cs.tailWag = t > 15.9 ? 0.6 : 1;
      cat.root.children[0].visible = t >= 12.3;          // contact shadow only on land
      cat.update(t);

      // ---------------- water effects
      water.material.userData.sh && (water.material.userData.sh.uniforms.uT.value = t);
      const rc = t < 9.4 ? cat.root.position : (t < 12.4 ? ring.position : null);
      ripples.forEach((m, i) => {
        if (!rc) { m.visible = false; return; }
        const ph = (t * 0.9 + i / ripples.length) % 1;
        m.visible = true; m.position.set(rc.x, WATER_Y + 0.005, rc.z); m.scale.setScalar(0.6 + ph * 3.2);
        m.material.opacity = 0.55 * (1 - ph);
      });
      // splashes: paddling (0-8.5), ring landing (8.42), shake spray (13.6-14.6)
      for (let i = 0; i < splashN; i++) {
        let p = null, s = 0;
        const ph = (t * 1.8 + i / splashN) % 1;
        const ang = i * 2.399;
        if (t < 8.5) {
          p = cat.root.position.clone().add(V(Math.cos(ang) * (0.12 + ph * 0.18), WATER_Y - cat.root.position.y + Math.sin(ph * Math.PI) * 0.22, Math.sin(ang) * (0.12 + ph * 0.18) + 0.06));
          s = (1 - ph) * (i % 3 === 0 ? 0.9 : 0);
        }
        const u = (t - 8.42) / 0.7;
        if (u > 0 && u < 1) { p = LAND.clone().add(V(Math.cos(ang) * u * 0.6, Math.sin(u * Math.PI) * (0.3 + (i % 5) * 0.06), Math.sin(ang) * u * 0.6)); s = 0.8 * (1 - u); }
        const v = (t - 13.6) / 1.0;
        if (v > 0 && v < 1) { const vv = (v * 3 + i / splashN) % 1; p = cat.root.position.clone().add(V(Math.cos(ang) * vv * 0.55, 0.22 + Math.sin(vv * Math.PI) * 0.2 - vv * 0.25, Math.sin(ang) * vv * 0.55)); s = 0.9 * (1 - vv); }
        m4.compose(p ?? sv.set(0, -5, 0), q, tmp.setScalar(Math.max(0.0001, s))); splash.setMatrixAt(i, m4);
      }
      splash.instanceMatrix.needsUpdate = true;
      // hearts
      hearts.forEach((h, i) => {
        const ph = (k.heart * 2.2 + i / hearts.length) % 1;
        const on = k.heart > 0.02 && k.heart * 2.2 > i / hearts.length;
        h.visible = on;
        if (!on) return;
        const c = cat.root.position;
        h.position.set(c.x + 0.15 * Math.sin(i * 2 + t), c.y + 0.5 + ph * 0.8, c.z + 0.1 * Math.cos(i * 3));
        h.scale.setScalar(Math.sin(ph * Math.PI) * 0.9);
        h.rotation.y = Math.sin(t * 2 + i) * 0.4;
        h.lookAt(h.position.clone().add(V(0, 0, 1)));
      });
    },
    k,
  };
}

function lerp(a, b, u) { return a + (b - a) * u; }

// ---------------------------------------------------------------- camera: shot plan -> framed poses -> smoothed track
// Each shot names its subjects and the side the camera looks from; the distance is fitted so the subjects fill the frame.
const SHOTS = [
  // t0, t1, subjects, from (direction from subjects to camera, xz), elevation (deg), fill (radius in metres), extra
  [0.0, 1.9, ['cat'], [0.55, 1.0], 10, 0.32],
  [1.9, 3.55, ['buddy'], 'pond', 12, 0.65],
  [3.55, 4.4, ['buddyHead'], 'pond', 6, 0.36],
  [4.4, 5.2, ['buddy', 'ring'], 'pondL', 14, 0.7],
  [5.2, 6.65, ['buddy'], 'pondR', 12, 0.75],
  [6.65, 8.35, ['buddy', 'ring'], 'side', 16, 0.9],
  [8.35, 9.4, ['cat', 'ring'], [0.4, 1.0], 18, 0.42],
  [9.4, 12.3, ['buddy', 'cat'], 'pond', 20, 1.0],
  [12.3, 13.4, ['cat', 'buddy'], 'pond', 12, 0.7],
  [13.4, 15.1, ['cat'], 'pond', 10, 0.36],
  [15.1, 17.6, ['buddyHead', 'cat'], 'pond', 10, 0.5],
  [17.6, 20.0, ['buddy'], 'pondWide', 30, 2.6],
];
const HALF_H = Math.atan(Math.tan(THREE.MathUtils.degToRad(36 / 2)) * (1080 / 1920));
let TRACK = null;
export function buildTrack(world) {
  const FPS = 30, N = Math.round(DURATION * FPS) + 1;
  const raw = [];
  for (let n = 0; n < N; n++) {
    const t = n / FPS;
    world.update(t);
    const shot = SHOTS.find((s) => t >= s[0] && t <= s[1]) ?? SHOTS[SHOTS.length - 1];
    const bp = world.buddy.root.position.clone().add(V(0, 0.55, 0));
    const pts = shot[2].map((nm) => nm === 'cat' ? world.cat.root.position.clone().add(V(0, 0.2, 0)) : nm === 'ring' ? world.ring.position.clone() : nm === 'buddyHead' ? bp.clone().add(V(0, 0.28, 0)) : bp);
    const c = pts.reduce((a, b) => a.add(b), V(0, 0, 0)).divideScalar(pts.length);
    const R = Math.max(shot[5], ...pts.map((p) => p.distanceTo(c) + shot[5] * 0.6));
    let dir;
    const toPond = V(-c.x, 0, -c.z).normalize();
    const rotY = (v, a) => V(v.x * Math.cos(a) + v.z * Math.sin(a), 0, -v.x * Math.sin(a) + v.z * Math.cos(a));
    if (Array.isArray(shot[3])) dir = V(shot[3][0], 0, shot[3][1]).normalize();
    else if (shot[3] === 'pond') dir = rotY(toPond, 0.35);
    else if (shot[3] === 'pondL') dir = rotY(toPond, 0.9);
    else if (shot[3] === 'pondR') dir = rotY(toPond, -0.5);
    else if (shot[3] === 'side') dir = rotY(toPond, 1.2);
    else dir = rotY(toPond, -0.2 + (t - shot[0]) * 0.12);
    const el = THREE.MathUtils.degToRad(shot[4] + (shot[3] === 'pondWide' ? (t - shot[0]) * 6 : 0));
    let dist = R / Math.sin(HALF_H);
    if (shot[3] === 'pondWide') dist *= 0.35 + 0.65 * Math.min(1, (t - shot[0]) / 2.4);
    const pos = c.clone().addScaledVector(dir, dist * Math.cos(el)); pos.y += dist * Math.sin(el);
    pos.y = Math.max(pos.y, 0.12);
    raw.push({ pos, target: c });
  }
  // gaussian smoothing (sigma 0.3 s) -> continuous camera moves between shots
  const sig = 0.3 * FPS, K = Math.ceil(sig * 3);
  TRACK = raw.map((_, n) => {
    const p = V(0, 0, 0), g = V(0, 0, 0); let ws = 0;
    for (let j = -K; j <= K; j++) { const m = Math.min(N - 1, Math.max(0, n + j)); const w = Math.exp(-(j * j) / (2 * sig * sig)); p.addScaledVector(raw[m].pos, w); g.addScaledVector(raw[m].target, w); ws += w; }
    return { pos: p.divideScalar(ws), target: g.divideScalar(ws) };
  });
}
export function cameraAt(t) {
  const f = Math.min(TRACK.length - 1.001, Math.max(0, t * 30)); const i = Math.floor(f), u = f - i;
  return { pos: TRACK[i].pos.clone().lerp(TRACK[i + 1].pos, u), target: TRACK[i].target.clone().lerp(TRACK[i + 1].target, u) };
}
