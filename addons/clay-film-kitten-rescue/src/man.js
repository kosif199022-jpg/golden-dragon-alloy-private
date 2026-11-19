// A clay man (chibi proportions) with the same rig API as buddy.js, so the choreography works unchanged.
// v2: sculpted hair clumps, recessed eyes with thick brows, collar + pocket + cuffs, mitten hands with thumbs,
// hip piece instead of a floating belt, shoes with soles, smile with teeth and tongue.
import * as THREE from 'three';
import { clay, gloss } from './clay.js';
import { sphere, capsule, mesh, contactShadow, rbox } from './shapes.js';

export function createMan({ skin = 0xf0bf9a, hair = 0x4a3328, shirt = 0x6fb7c9, pants = 0x3d4f78, shoes = 0x8a5a3c } = {}) {
  const root = new THREE.Group();
  const shadow = contactShadow(0.36, 0.3, 0.55); shadow.position.y = 0.003; root.add(shadow);
  const skinM = clay(skin, { bump: 0.35 });
  const shirtM = clay(shirt, { bump: 0.9, freq: 16 });
  const shirtD = clay(new THREE.Color(shirt).multiplyScalar(0.82).getHex(), { bump: 0.9, freq: 16 });
  const pantsM = clay(pants, { bump: 0.9, freq: 16 });
  const hairM = clay(hair, { bump: 1.3, freq: 22 });

  // legs (outside the squash pivot)
  const legs = [];
  for (const sx of [-1, 1]) {
    const hip = new THREE.Group(); hip.position.set(sx * 0.075, 0.33, 0); root.add(hip);
    hip.add(mesh(capsule(0.064, 0.19), pantsM, { pos: [0, -0.13, 0] }));
    hip.add(mesh(new THREE.TorusGeometry(0.06, 0.016, 10, 24), pantsM, { pos: [0, -0.255, 0], rot: [Math.PI / 2, 0, 0] }));           // cuff
    hip.add(mesh(sphere(0.07, 24), clay(shoes, { bump: 0.4 }), { pos: [0, -0.288, 0.035], scl: [1, 0.62, 1.55] }));                     // shoe
    hip.add(mesh(rbox(0.12, 0.022, 0.2, 0.01, 3), clay(0xd9c4ae), { pos: [0, -0.312, 0.035] }));                                       // sole
    legs.push(hip);
  }

  // upper body pivot at the hips
  const pivot = new THREE.Group(); pivot.position.y = 0.33; root.add(pivot);
  pivot.add(mesh(sphere(0.15, 32), pantsM, { pos: [0, 0.03, 0], scl: [0.98, 0.42, 0.8] }));                                              // hip piece
  pivot.add(mesh(capsule(0.135, 0.15), shirtM, { pos: [0, 0.165, 0], scl: [1.12, 1, 0.88] }));                                           // torso
  pivot.add(mesh(new THREE.TorusGeometry(0.135, 0.018, 10, 40), clay(0x5a3a2a), { pos: [0, 0.035, 0], rot: [Math.PI / 2, 0, 0], scl: [1.12, 0.88, 1] }));  // belt
  pivot.add(mesh(rbox(0.05, 0.035, 0.02, 0.006, 2), clay(0xe8c46a), { pos: [0, 0.035, 0.122] }));                                        // buckle
  for (const y of [0.22, 0.15, 0.085]) pivot.add(mesh(sphere(0.014, 10), clay(0xfff4e0), { pos: [0, y, 0.123], shadow: false }));
  pivot.add(mesh(rbox(0.06, 0.06, 0.015, 0.01, 2), shirtD, { pos: [-0.065, 0.2, 0.118], rot: [0, -0.15, 0] }));                          // pocket
  for (const sx of [-1, 1]) pivot.add(mesh(rbox(0.075, 0.05, 0.016, 0.012, 2), shirtM, { pos: [sx * 0.042, 0.31, 0.085], rot: [0.5, sx * 0.4, sx * 0.55] }));  // collar
  pivot.add(mesh(capsule(0.048, 0.03), skinM, { pos: [0, 0.335, 0] }));

  // head
  const head = new THREE.Group(); head.position.set(0, 0.5, 0.01); pivot.add(head);
  head.add(mesh(sphere(0.165, 56), skinM, { scl: [1, 1.04, 0.96] }));
  head.add(mesh(sphere(0.11, 32), skinM, { pos: [0, -0.07, 0.035], scl: [1.2, 0.8, 1] }));                                                 // cheeks / jaw
  for (const sx of [-1, 1]) {
    head.add(mesh(sphere(0.042, 18), skinM, { pos: [sx * 0.162, -0.005, -0.01], scl: [0.5, 1, 0.8] }));
    head.add(mesh(sphere(0.02, 12), clay(0xe0a080), { pos: [sx * 0.172, -0.005, 0.0], scl: [0.4, 0.8, 0.6], shadow: false }));
  }
  // sculpted hair: cap + clumps + quiff + sideburns
  head.add(mesh(new THREE.SphereGeometry(0.173, 48, 24, 0, Math.PI * 2, 0, Math.PI * 0.5), hairM, { pos: [0, 0.015, -0.015], rot: [-0.34, 0, 0], scl: [1.02, 1.03, 1.02] }));
  const clumps = [[0.06, 0.16, 0.08, 0.07], [-0.03, 0.17, 0.095, 0.06], [-0.1, 0.13, 0.07, 0.055], [0.12, 0.12, 0.05, 0.05], [0.0, 0.19, 0.0, 0.07], [-0.12, 0.08, -0.06, 0.06], [0.12, 0.08, -0.06, 0.06], [0.0, 0.12, -0.12, 0.08]];
  clumps.forEach(([x, y, z, r], i) => head.add(mesh(sphere(r, 20), hairM, { pos: [x, y, z], scl: [1.3, 0.65, 1.0], rot: [0.3, i * 0.7, 0.2] })));
  for (const sx of [-1, 1]) head.add(mesh(capsule(0.022, 0.05), hairM, { pos: [sx * 0.152, 0.03, 0.03], rot: [0, 0, sx * 0.1] }));
  // eyes: recessed, with lids and thick brows
  const eyes = [];
  for (const sx of [-1, 1]) {
    const eg = new THREE.Group(); eg.position.set(sx * 0.06, 0.018, 0.132); eg.lookAt(sx * 0.15, 0.018, 1); head.add(eg);
    const white = mesh(sphere(0.041, 24), gloss(0xfdfbf6, 0.25), { scl: [1, 1.12, 0.45], shadow: false });
    const pupil = mesh(sphere(0.027, 18), gloss(0x2a1d18, 0.12), { pos: [0, -0.002, 0.014], scl: [1, 1.05, 0.5], shadow: false });
    const iris = mesh(sphere(0.031, 18), gloss(0x6a4630, 0.2), { pos: [0, -0.002, 0.011], scl: [1, 1.05, 0.45], shadow: false });
    const spark = mesh(sphere(0.008, 10), new THREE.MeshBasicMaterial({ color: 0xffffff }), { pos: [0.01, 0.012, 0.028], shadow: false });
    const lid = mesh(new THREE.SphereGeometry(0.044, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.5), skinM, { scl: [1.04, 1.12, 0.55], shadow: false });
    const brow = mesh(capsule(0.014, 0.05), hairM, { pos: [0, 0.064, 0.012], rot: [0, 0, Math.PI / 2], shadow: false });
    eg.add(white, iris, pupil, spark, lid, brow);
    eyes.push({ g: eg, pupil: iris, lid, brow, sx, dot: pupil });
  }
  head.add(mesh(sphere(0.032, 18), skinM, { pos: [0, -0.028, 0.165], scl: [0.95, 0.85, 0.8], shadow: false }));                          // nose
  for (const sx of [-1, 1]) head.add(mesh(sphere(0.034, 14), clay(0xf29a8f, { rough: 0.9, rim: 0.05 }), { pos: [sx * 0.1, -0.05, 0.138], scl: [1, 0.6, 0.3], shadow: false }));
  // mouths
  const mouthMat = clay(0x6a2c30, { rough: 0.6, rim: 0 });
  const mz = 0.157, my = -0.088;
  const smile = mesh(new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(new THREE.Vector3(-0.045, 0.01, -0.004), new THREE.Vector3(0, -0.028, 0.008), new THREE.Vector3(0.045, 0.01, -0.004)), 16, 0.008, 8), mouthMat, { pos: [0, my, mz], shadow: false });
  const oh = mesh(sphere(0.026, 16), mouthMat, { pos: [0, my - 0.006, mz - 0.006], scl: [0.8, 1.1, 0.45], shadow: false });
  const grin = mesh(new THREE.SphereGeometry(0.044, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), mouthMat, { pos: [0, my + 0.01, mz - 0.012], scl: [1, 0.8, 0.5], shadow: false });
  const teeth = mesh(rbox(0.058, 0.013, 0.01, 0.005, 2), clay(0xfffaf2), { pos: [0, my + 0.004, mz + 0.006], shadow: false });
  const tongue = mesh(sphere(0.02, 14), clay(0xf08a96), { pos: [0, my - 0.02, mz + 0.002], scl: [1.2, 0.5, 0.5], shadow: false });
  head.add(smile, oh, grin, teeth, tongue);

  // arms: shoulder pivot; sleeve + cuff + forearm + mitten hand with a thumb
  const arms = [];
  for (const sx of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(sx * 0.165, 0.27, 0); pivot.add(sh);
    sh.add(mesh(capsule(0.048, 0.1), shirtM, { pos: [0, -0.045, 0] }));
    sh.add(mesh(new THREE.TorusGeometry(0.046, 0.013, 8, 22), shirtD, { pos: [0, -0.11, 0], rot: [Math.PI / 2, 0, 0] }));
    sh.add(mesh(capsule(0.037, 0.1), skinM, { pos: [0, -0.165, 0] }));
    const hand = new THREE.Group(); hand.position.set(0, -0.24, 0); sh.add(hand);
    hand.add(mesh(sphere(0.048, 20), skinM, { scl: [0.95, 1.05, 0.72] }));
    hand.add(mesh(capsule(0.016, 0.03), skinM, { pos: [-sx * 0.04, 0.012, 0.02], rot: [0.2, 0, sx * 0.8] }));
    for (let f = 0; f < 3; f++) hand.add(mesh(capsule(0.012, 0.012), skinM, { pos: [(f - 1) * 0.022, -0.045, 0.006], shadow: false }));
    arms.push({ sh, sx, hand });
  }

  const api = {
    root, pivot, head, eyes, arms, legs,
    state: { squash: 0, lean: 0, turn: 0, tilt: 0, blink: 0, look: [0, 0], mouth: 'smile', mouthOpen: 0, brow: 0, armL: [0.2, 0], armR: [0.2, 0], handL: null, handR: null, bounce: 0, stride: 0, phase: 0 },
    update() {
      const s = api.state;
      pivot.scale.set(1 - s.squash * 0.4, 1 + s.squash, 1 - s.squash * 0.4);
      pivot.position.y = 0.33 + s.bounce;
      pivot.rotation.set(s.lean, s.turn, s.tilt);
      head.rotation.set(-s.lean * 0.3, 0, s.tilt * 0.5);
      legs.forEach((l, k) => { l.rotation.x = Math.sin(s.phase + k * Math.PI) * 0.55 * s.stride; l.position.y = 0.33 + s.bounce * 0.5; });
      for (const e of eyes) {
        e.pupil.position.x = s.look[0] * 0.013; e.pupil.position.y = s.look[1] * 0.013 - 0.002;
        e.dot.position.x = s.look[0] * 0.013; e.dot.position.y = s.look[1] * 0.013 - 0.002;
        e.lid.rotation.x = THREE.MathUtils.lerp(-1.65, 1.45, Math.max(s.blink, 0.12));
        e.brow.position.y = 0.064 + s.brow * 0.015;
        e.brow.rotation.z = Math.PI / 2 + e.sx * s.brow * -0.35;
      }
      smile.visible = s.mouth === 'smile';
      oh.visible = s.mouth === 'oh';
      grin.visible = teeth.visible = tongue.visible = s.mouth === 'grin';
      oh.scale.set(0.8 + s.mouthOpen * 0.3, 1.1 + s.mouthOpen * 0.6, 0.45);
      for (const [i, a] of arms.entries()) {
        const tgt = i === 0 ? s.handL : s.handR;
        if (tgt) {
          const d = new THREE.Vector3(tgt[0], tgt[1] - 0.33 + 0.05 + 0.08, tgt[2]).sub(a.sh.position);
          const len = d.length(); d.normalize();
          a.sh.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d);
          a.sh.scale.set(1, THREE.MathUtils.clamp(len / 0.25, 0.6, 1.5), 1);
        } else {
          a.sh.scale.set(1, 1, 1);
          if (i === 0) a.sh.rotation.set(-s.armL[1], 0, -s.armL[0]); else a.sh.rotation.set(-s.armR[1], 0, s.armR[0]);
        }
      }
    },
  };
  api.update();
  return api;
}
