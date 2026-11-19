// A clay kitten: round body, big head, ears, whiskers, stripy back, paddling paws, wagging tail.
import * as THREE from 'three';
import { clay, gloss } from './clay.js';
import { sphere, mesh, capsule, contactShadow } from './shapes.js';

export function createCat({ color = 0xf4a85e, stripe = 0xd9823e, belly = 0xfff0de } = {}) {
  const root = new THREE.Group();
  const shadow = contactShadow(0.2, 0.2, 0.45); shadow.position.y = 0.004; root.add(shadow);
  const pivot = new THREE.Group(); root.add(pivot);
  const fur = clay(color, { bump: 0.6, freq: 16 });
  const furWet = clay(new THREE.Color(color).multiplyScalar(0.72).getHex(), { bump: 0.9, freq: 18, rough: 0.45 });

  const body = mesh(sphere(0.13, 40), fur, { pos: [0, 0.12, -0.03], scl: [1, 0.92, 1.25] });
  const bel = mesh(sphere(0.1, 28), clay(belly), { pos: [0, 0.1, 0.06], scl: [0.9, 0.85, 0.7] });
  pivot.add(body, bel);
  for (let i = 0; i < 3; i++) pivot.add(mesh(sphere(0.05, 16), clay(stripe), { pos: [0, 0.235, -0.11 + i * 0.07], scl: [1.6, 0.25, 0.45], shadow: false }));

  const head = new THREE.Group(); head.position.set(0, 0.3, 0.07); pivot.add(head);
  const skull = mesh(sphere(0.125, 44), fur, { scl: [1.08, 0.96, 1] }); head.add(skull);
  head.add(mesh(sphere(0.06, 20), clay(belly), { pos: [0, -0.04, 0.085], scl: [1.3, 0.8, 0.6], shadow: false }));
  for (const sx of [-1, 1]) {
    const ear = mesh(new THREE.ConeGeometry(0.055, 0.1, 20), fur, { pos: [sx * 0.075, 0.115, -0.01], rot: [-0.15, 0, -sx * 0.35] });
    ear.add(mesh(new THREE.ConeGeometry(0.032, 0.06, 16), clay(0xf6a4b0), { pos: [0, -0.008, 0.017], shadow: false }));
    head.add(ear);
    head.add(mesh(sphere(0.022, 12), clay(stripe), { pos: [sx * 0.04, 0.1, 0.06], scl: [0.6, 0.3, 0.3], shadow: false }));
  }
  const eyes = [];
  for (const sx of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(sx * 0.052, 0.012, 0.105); head.add(g);
    const white = mesh(sphere(0.036, 22), gloss(0xfdfbf6, 0.2), { scl: [1, 1.12, 0.55], shadow: false });
    const pupil = mesh(sphere(0.026, 18), gloss(0x1c1620, 0.1), { pos: [0, -0.002, 0.012], scl: [1, 1.12, 0.6], shadow: false });
    const spark = mesh(sphere(0.008, 10), new THREE.MeshBasicMaterial({ color: 0xffffff }), { pos: [0.009, 0.012, 0.026], shadow: false });
    const lid = mesh(new THREE.SphereGeometry(0.039, 22, 12, 0, Math.PI * 2, 0, Math.PI / 2), fur, { scl: [1.04, 1.15, 0.65], shadow: false });
    g.add(white, pupil, spark, lid);
    eyes.push({ g, pupil, lid, white });
  }
  head.add(mesh(sphere(0.016, 12), clay(0xf28a9a), { pos: [0, -0.025, 0.13], scl: [1.2, 0.8, 0.7], shadow: false }));
  for (const sx of [-1, 1]) for (let k = 0; k < 3; k++)                                    // cheek fluff
    head.add(mesh(new THREE.ConeGeometry(0.022, 0.05, 10), fur, { pos: [sx * (0.118 + k * 0.004), -0.03 - k * 0.022, 0.03], rot: [0, 0, sx * (1.7 + k * 0.25)], shadow: false }));
  for (let k = 0; k < 4; k++)                                                                // chest fluff
    pivot.add(mesh(new THREE.ConeGeometry(0.03, 0.06, 10), clay(belly), { pos: [(k - 1.5) * 0.035, 0.2 - Math.abs(k - 1.5) * 0.01, 0.11], rot: [2.6, 0, (k - 1.5) * 0.3], shadow: false }));
  const mouthMat = clay(0x5a2a32, { rim: 0 });
  const mouthO = mesh(sphere(0.018, 14), mouthMat, { pos: [0, -0.06, 0.122], scl: [1, 1.2, 0.4], shadow: false });
  const smileCurve = new THREE.CatmullRomCurve3([new THREE.Vector3(-0.03, -0.045, 0.12), new THREE.Vector3(-0.012, -0.058, 0.128), new THREE.Vector3(0, -0.048, 0.13), new THREE.Vector3(0.012, -0.058, 0.128), new THREE.Vector3(0.03, -0.045, 0.12)]);
  const mouthW = mesh(new THREE.TubeGeometry(smileCurve, 20, 0.005, 6), mouthMat, { shadow: false });
  head.add(mouthO, mouthW);
  for (const sx of [-1, 1]) for (let k = 0; k < 3; k++) {
    const w = mesh(new THREE.CylinderGeometry(0.0025, 0.0025, 0.11, 5), clay(0xfffaf2, { rim: 0 }), { pos: [sx * 0.09, -0.035 + (k - 1) * 0.014, 0.1], rot: [0, 0, Math.PI / 2 + sx * (k - 1) * 0.15], shadow: false });
    head.add(w);
  }
  const paws = [];
  for (const [x, z] of [[-0.07, 0.1], [0.07, 0.1], [-0.07, -0.12], [0.07, -0.12]]) {
    const p = mesh(sphere(0.042, 18), clay(belly), { pos: [x, 0.03, z], scl: [1, 0.7, 1.1] }); pivot.add(p); paws.push({ p, x, z });
  }
  const tail = [];
  for (let i = 0; i < 8; i++) { const s = mesh(sphere(0.034 - i * 0.002, 14), i % 3 === 2 ? clay(stripe) : fur); pivot.add(s); tail.push(s); }

  const furMeshes = [body, skull, ...tail.filter((_, i) => i % 3 !== 2)];
  const api = {
    root, pivot, head, eyes, paws,
    state: { paddle: 0, blink: 0, eyes: 1, mouth: 'o', shake: 0, wet: 1, look: [0, 0], headTilt: 0, squash: 0, bounce: 0, tailWag: 1, sit: 0 },
    update(t) {
      const s = api.state;
      pivot.scale.set(1 - s.squash * 0.5, 1 + s.squash, 1 - s.squash * 0.5);
      pivot.position.y = s.bounce;
      const sh = s.shake * Math.sin(t * 48);
      pivot.rotation.y = sh * 0.6;
      head.rotation.set(-0.1 + s.sit * 0.05, sh * 0.5, s.headTilt + sh * 0.3);
      for (const e of eyes) {
        e.lid.rotation.x = THREE.MathUtils.lerp(-1.6, 1.45, s.blink);
        e.white.scale.set(s.eyes, 1.12 * s.eyes, 0.55);
        e.pupil.position.set(s.look[0] * 0.01, s.look[1] * 0.01, 0.012);
      }
      mouthO.visible = s.mouth === 'o';
      mouthW.visible = s.mouth === 'w';
      // paddling: front paws circle at the surface
      paws.forEach((q, i) => {
        const front = i < 2;
        const ph = t * 13 + i * Math.PI;
        if (front && s.paddle > 0) {
          q.p.position.set(q.x * 1.2, 0.17 + 0.05 * Math.sin(ph) * s.paddle, q.z + 0.08 + 0.06 * Math.cos(ph) * s.paddle);
        } else q.p.position.set(q.x, 0.03, q.z);
      });
      // tail
      for (let i = 0; i < tail.length; i++) {
        const u = i / (tail.length - 1);
        const wag = Math.sin(t * 5 - u * 2.5) * 0.08 * s.tailWag * u;
        tail[i].position.set(wag, 0.08 + u * 0.18 + Math.sin(u * 2.2) * 0.05, -0.18 - u * 0.08 + u * u * 0.06);
      }
      for (const m of furMeshes) m.material = s.wet > 0.5 ? furWet : fur;
    },
  };
  api.update(0);
  return api;
}
