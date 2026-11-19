// Kitten Rescue — renderer, depth of field and controls.
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { BokehPass } from 'three/examples/jsm/postprocessing/BokehPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { buildPond, cameraAt, buildTrack, DURATION } from './pond.js';

const W = 1080, H = 1920;
const RENDER = new URLSearchParams(location.search).has('render');
if (RENDER) document.body.classList.add('render');
document.title = 'Kitten Rescue';

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.96;
document.getElementById('stage').appendChild(renderer.domElement);

const world = buildPond();
buildTrack(world);
const camera = new THREE.PerspectiveCamera(36, W / H, 0.02, 120);
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
composer.addPass(new RenderPass(world.scene, camera));
const bokeh = new BokehPass(world.scene, camera, { focus: 2, aperture: 0.002, maxblur: 0.006 });
composer.addPass(bokeh); composer.addPass(new OutputPass());

function renderAt(t) {
  t = Math.min(Math.max(t, 0), DURATION - 1e-4);
  world.update(t);
  const p = cameraAt(t);
  camera.position.copy(p.pos); camera.lookAt(p.target); camera.updateMatrixWorld(true);
  const focus = p.pos.distanceTo(p.target);
  bokeh.uniforms.focus.value = focus;
  bokeh.uniforms.nearClip.value = camera.near; bokeh.uniforms.farClip.value = camera.far;
  bokeh.uniforms.aperture.value = 0.004 / Math.max(0.5, focus);
  composer.render();
}

let playing = !RENDER, t0 = performance.now(), tNow = 0;
const scrub = document.getElementById('scrub'), timeEl = document.getElementById('time'), playBtn = document.getElementById('play');
scrub.max = DURATION;
playBtn.onclick = () => { playing = !playing; playBtn.textContent = playing ? 'Pause' : 'Play'; t0 = performance.now() - tNow * 1000; };
document.getElementById('restart').onclick = () => { tNow = 0; t0 = performance.now(); playing = true; playBtn.textContent = 'Pause'; };
scrub.oninput = () => { tNow = +scrub.value; t0 = performance.now() - tNow * 1000; if (!playing) renderAt(tNow); };
window.addEventListener('keydown', (e) => { if (e.code === 'Space') playBtn.onclick(); });
function loop() {
  if (playing) { tNow = ((performance.now() - t0) / 1000) % DURATION; renderAt(tNow); scrub.value = tNow; timeEl.textContent = tNow.toFixed(2) + ' s'; }
  requestAnimationFrame(loop);
}
// character sheet: ?sheet=ANGLE shows the man and the kitten on a plain backdrop
const SHEET = new URLSearchParams(location.search).get('sheet');
if (SHEET !== null) {
  const ang = +SHEET;
  world.update(0.0);
  const b = world.buddy, c = world.cat;
  b.root.position.set(-0.08, 0.03, 3.6); b.root.rotation.y = ang;
  Object.assign(b.state, { lean: 0, squash: 0, bounce: 0, stride: 0, mouth: 'grin', brow: 0.3, look: [0, 0], blink: 0, handL: null, handR: null, armL: [0.35, 0.1], armR: [0.35, 0.1], tilt: 0.06 });
  b.update();
  c.root.position.set(0.2, 0.03, 3.95); c.root.rotation.y = ang - 0.3;
  Object.assign(c.state, { paddle: 0, wet: 0, mouth: 'w', eyes: 1.1, blink: 0, shake: 0, squash: 0, bounce: 0, look: [0, 0.2], headTilt: 0.2 });
  c.update(1.0); c.root.children[0].visible = true;
  camera.position.set(0.05, 0.72, 6.45); camera.lookAt(0.05, 0.52, 3.7); camera.updateMatrixWorld(true);
  bokeh.uniforms.focus.value = 2.75; bokeh.uniforms.aperture.value = 0.0012;
  bokeh.uniforms.nearClip.value = camera.near; bokeh.uniforms.farClip.value = camera.far;
  composer.render();
  window.__kosif = { duration: DURATION, seek: () => composer.render(), ready: true };
} else
window.__kosif = { duration: DURATION, seek: (t) => { tNow = t; renderAt(t); }, ready: true };
if (SHEET === null) renderAt(0);
if (!RENDER && SHEET === null) loop();
