// A rigged clay character: bean body, expressive eyes, cheeks, mouths, stubby arms and feet.
import * as THREE from 'three';
import { clay, gloss } from './clay.js';
import { bean, beanR, sphere, capsule, mesh, contactShadow } from './shapes.js';

const H = 0.8;

export function createBuddy({ color = 0xf2b8a0, cheek = 0xf07f8f, feet = 0xc98f7a, scale = 1 } = {}) {
  const root = new THREE.Group();
  root.scale.setScalar(scale);
  const shadow = contactShadow(0.42, 0.42, 0.5); shadow.position.y = 0.003; root.add(shadow);

  // feet (not squashed)
  const footGeo = sphere(0.11, 24);
  const fl = mesh(footGeo, clay(feet), { pos: [-0.14, 0.05, 0.05], scl: [1, 0.55, 1.35] });
  const fr = mesh(footGeo, clay(feet), { pos: [0.14, 0.05, 0.05], scl: [1, 0.55, 1.35] });
  root.add(fl, fr);

  // body pivot at the feet: squash & stretch + lean
  const pivot = new THREE.Group(); pivot.position.y = 0.05; root.add(pivot);
  const body = mesh(bean(H), clay(color, { bump: 0.45 })); pivot.add(body);

  // face sits on the surface
  const face = new THREE.Group(); pivot.add(face);
  const eyeY = 0.53, eyeX = 0.115;
  const eyes = [];
  for (const sx of [-1, 1]) {
    const z = Math.sqrt(Math.max(0, beanR(eyeY) ** 2 - eyeX ** 2)) - 0.02;
    const eg = new THREE.Group(); eg.position.set(sx * eyeX, eyeY, z);
    eg.lookAt(sx * eyeX * 2.2, eyeY, z + 1);
    const white = mesh(sphere(0.072, 28), gloss(0xfdfbf6, 0.25), { scl: [1, 1.12, 0.6], shadow: false });
    const pupil = mesh(sphere(0.046, 24), gloss(0x241a24, 0.12), { pos: [0, 0, 0.032], scl: [1, 1.05, 0.55], shadow: false });
    const spark = mesh(sphere(0.014, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }), { pos: [0.016, 0.02, 0.058], shadow: false });
    const lid = mesh(new THREE.SphereGeometry(0.079, 28, 14, 0, Math.PI * 2, 0, Math.PI * 0.5), clay(color), { scl: [1.04, 1.13, 0.68], shadow: false });
    const brow = mesh(capsule(0.012, 0.06), clay(0x7a4a4a), { pos: [0, 0.105, 0.02], rot: [0, 0, Math.PI / 2], shadow: false });
    eg.add(white, pupil, spark, lid, brow);
    face.add(eg);
    eyes.push({ g: eg, pupil, lid, brow, sx });
  }
  // cheeks
  for (const sx of [-1, 1]) {
    const y = 0.43, x = 0.2;
    const z = Math.sqrt(Math.max(0, beanR(y) ** 2 - x ** 2)) - 0.012;
    const ck = mesh(sphere(0.055, 20), clay(cheek, { rough: 0.9, rim: 0.05 }), { pos: [sx * x, y, z], scl: [1, 0.62, 0.3], shadow: false });
    ck.lookAt(sx * x * 2, y, z + 1);
    face.add(ck);
  }
  // mouths
  const mouthY = 0.42;
  const mz = beanR(mouthY) - 0.004;
  const mouthMat = clay(0x5a2a32, { rough: 0.6, rim: 0.0 });
  const smileCurve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(-0.06, 0.012, 0), new THREE.Vector3(0, -0.04, 0.012), new THREE.Vector3(0.06, 0.012, 0));
  const smile = mesh(new THREE.TubeGeometry(smileCurve, 20, 0.011, 8), mouthMat, { pos: [0, mouthY, mz], shadow: false });
  const oh = mesh(sphere(0.04, 20), mouthMat, { pos: [0, mouthY - 0.01, mz - 0.01], scl: [0.8, 1.1, 0.45], shadow: false });
  const grinGeo = new THREE.SphereGeometry(0.06, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
  const grin = mesh(grinGeo, mouthMat, { pos: [0, mouthY + 0.008, mz - 0.012], scl: [1, 0.85, 0.5], shadow: false });
  const tongue = mesh(sphere(0.026, 16), clay(0xf08a96), { pos: [0, mouthY - 0.028, mz + 0.006], scl: [1, 0.5, 0.5], shadow: false });
  face.add(smile, oh, grin, tongue);

  // arms: pivots at the shoulders
  const arms = [];
  for (const sx of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(sx * 0.31, 0.4, 0.02); pivot.add(sh);
    const arm = mesh(capsule(0.05, 0.13), clay(color), { pos: [0, -0.1, 0] });
    const hand = mesh(sphere(0.062, 20), clay(color), { pos: [0, -0.2, 0] });
    sh.add(arm, hand);
    arms.push({ sh, sx, hand });
  }

  const api = {
    root, pivot, face, eyes, arms,
    state: { squash: 0, lean: 0, turn: 0, tilt: 0, blink: 0, look: [0, 0], mouth: 'smile', mouthOpen: 0, brow: 0, armL: [0.2, 0], armR: [0.2, 0], handL: null, handR: null, bounce: 0, stride: 0, phase: 0 },
    update() {
      const s = api.state;
      const sq = s.squash;
      pivot.scale.set(1 - sq * 0.5, 1 + sq, 1 - sq * 0.5);
      pivot.position.y = 0.05 + s.bounce;
      for (const [k, f] of [fl, fr].entries()) {
        const ph = s.phase + k * Math.PI;
        f.position.z = 0.05 + Math.sin(ph) * 0.12 * s.stride;
        f.position.y = 0.05 + Math.max(0, Math.cos(ph)) * 0.07 * s.stride;
      }
      pivot.rotation.set(s.lean, s.turn, s.tilt);
      for (const e of eyes) {
        e.pupil.position.x = s.look[0] * 0.022 * (e.sx > 0 ? 1 : 1);
        e.pupil.position.y = s.look[1] * 0.022;
        // lid rotates down to close
        e.lid.rotation.x = THREE.MathUtils.lerp(-1.65, 1.45, s.blink);
        e.brow.position.y = 0.105 + s.brow * 0.025;
        e.brow.rotation.z = Math.PI / 2 + e.sx * s.brow * -0.35;
      }
      smile.visible = s.mouth === 'smile';
      oh.visible = s.mouth === 'oh';
      grin.visible = tongue.visible = s.mouth === 'grin';
      oh.scale.set(0.8 + s.mouthOpen * 0.3, 1.1 + s.mouthOpen * 0.6, 0.45);
      for (const [i, a] of arms.entries()) {
        const tgt = i === 0 ? s.handL : s.handR;
        if (tgt) {
          const d = new THREE.Vector3(tgt[0], tgt[1], tgt[2]).sub(a.sh.position);
          const len = d.length(); d.normalize();
          a.sh.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d);
          a.sh.scale.set(1, Math.min(1.35, len / 0.22), 1);
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
