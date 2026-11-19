// Example (English): "In this world, every kid gets one wish on their tenth birthday... Thousands of dragons."
// Shots are keyed to words with C(wi('word')) so they follow the voice whatever its pace.
import { V, lerp, lerpV, clamp, eio, eo, run, look, dof, gradeSet, setTOD, flash, handheld, C, wi, onReset, CAM } from './core.js';
import { cast, pose, POSES, crowd, crowdPose } from './kits/characters.js';
import { town, party, clouds } from './kits/sets.js';
import { dragon, flock } from './kits/creatures.js';
import { burst, twinkle, confetti, poof, orb } from './kits/fx.js';

// ---- world ----
const T = town(0, 0); clouds();
const P = party(0, 0, { age: 10 });
const leo = cast('hero', { acc: [['partyHat', { cols: ['#ff4d6d', '#ffd23f'] }]] });
const kids = [[-3.9, -3.1, .1], [3.9, -3.1, -.1], [-6.6, -1.6, .7], [6.6, -1.6, -.7], [-7.6, 3.4, 2.4], [7.6, 3.4, -2.4]].map(([x, z, r], i) => {
  const k = cast(i % 2 ? 'heroine' : 'puffer', { acc: [['partyHat', { cols: [['#4ade80', '#c084fc', '#38bdf8'][i % 3], '#ffd23f'] }]], shirt: ['#ff4d4d', '#ffd23f', '#4ade80', '#c084fc', '#fb923c', '#38bdf8'][i] });
  k.position.set(x, 0, z); k.rotation.y = r; k.scale.setScalar(.95); return k; });
const folk = crowd(46, V(0, 0, 0), 11, 27, { hats: .4 });
const baby = dragon({ body: '#4ade80', belly: '#fef08a', wing: '#22c55e', horn: '#fde68a', cute: true, scale: .42 }); baby.position.set(2.0, 2.85, -.4);
const big = dragon({ scale: 4.5 });
const swarm = flock({ center: V(0, 0, 0), t0: 7 });
const fx = { sparks: burst({ radius: 40 }), tw: twinkle(), conf: confetti(), poof: poof(), orb: orb() };
onReset(t => { baby.visible = big.visible = swarm.visible = false; leo.visible = P.visible = true; kids.forEach(k => k.visible = true); folk.forEach(c => c.visible = true); P.userData.tick(t, 1); });
const DAY = () => { setTOD('day'); gradeSet(1.28, 1.08, [1.02, 1, .97], .26); };
const leoParty = () => { leo.position.set(0, 0, -3); leo.rotation.y = 0; };
const kidsParty = t => kids.forEach((k, i) => pose(k, { e: i % 2 ? 'joy' : 'grin', aL: [-.3 - .3 * Math.abs(Math.sin(t * 6 + i)), 0, .3], aR: [-.3, 0, -.6 - .5 * Math.abs(Math.sin(t * 6 + i))] }));

// ---- shots: [start, end, (t, u) => {}] ----
const S = [
  [0, C(wi('gets')), (t, u) => { DAY(); kidsParty(t); crowdPose(folk, t, 'party'); leoParty(); pose(leo, { e: 'grin', ...POSES.wave(t) });
    CAM.fly(u, V(-120, 78, 190), V(-30, 22, 46), V(0, 0, -20), V(0, 5, -2), 44); dof(lerp(200, 50, u), .0004); }],
  [C(wi('gets')), C(wi('tenth')), (t, u) => { DAY(); kidsParty(t); crowdPose(folk, t, 'party'); leoParty(); pose(leo, { ...POSES.wish(), hx: .05, lean: .05 });
    const k = eo(u); look(lerpV(V(4.2, 5.5, 4.6), V(3.1, 5.15, 2.4), k).add(handheld(t)), V(0, 4.6, -3), 36); dof(lerp(9.2, 6.9, k), .0055); fx.tw.at(t, V(0, 4.6, -3), 1.9); }],
  [C(wi('tenth')), C(wi('but')), (t, u) => { DAY(); kidsParty(t); crowdPose(folk, t, 'party'); leoParty(); pose(leo, { e: 'grin' });
    const k = eio(u); look(lerpV(V(-3.3, 3.7, 4.4), V(-2.3, 3.9, 2.9), k).add(handheld(t, .5)), V(-.35, 4.1, -1.2), 38, -.05); dof(lerp(5.3, 3.7, k), .006); fx.conf.at(t); }],
  [C(wi('but')), C(wi('the', 1)), (t, u) => { DAY(); kidsParty(t); crowdPose(folk, t, 'party'); leoParty();
    const blow = u < .38; pose(leo, { e: blow ? 'blow' : 'joy', lean: blow ? .25 : 0, hx: blow ? .2 : -.35, aL: blow ? [0] : [-.4, 0, 2.2], aR: blow ? [0] : [-.4, 0, -2.2] });
    P.userData.tick(t, blow ? 1 - u / .38 : 0);
    const k = eio(clamp((u - .3) / .7)), oy = 4.2 + 18 * k * k; if (u > .34) { fx.orb.at(V(0, oy, -.5), 1.6 + 3 * k); fx.tw.at(t, V(0, oy, -.5), 1.2); }
    look(V(6.2 + k * 3, 3.6 + k * 2, 5.5 + k * 6).add(handheld(t)), V(0, lerp(4, oy, k * .55), -1), lerp(42, 50, k)); dof(lerp(8, 12, k), .003); }],
  [C(wi('the', 1)), C(wi('leo')), (t, u) => { DAY(); P.userData.tick(t, 0); crowdPose(folk, t, 'up'); kidsParty(t); leoParty(); pose(leo, { e: 'joy', hx: -.5, aL: [-.2, 0, 2.6], aR: [-.2, 0, -2.6] });
    const t0 = C(wi('the', 1)), tb = t0 + .12, a = .9 + u * .35; if (t < tb) fx.orb.at(V(0, lerp(22, 30, (t - t0) / .12), 0), 4, 0);
    fx.sparks.at(t, tb, V(0, 30, 0)); look(V(Math.cos(a) * 58, 34 - u * 6, Math.sin(a) * 58).add(handheld(t, 2)), V(0, 14 - u * 4, 0), 52); dof(60, .0004); if (t > tb) flash(clamp(.35 - (t - tb) * 1.4)); }],
  [C(wi('leo')), C(wi('dragon')), (t, u) => { DAY(); P.userData.tick(t, 0); crowdPose(folk, t, 'party'); kidsParty(t); leoParty(); pose(leo, { e: 'squeeze', aL: [-1.4, 0, -.45], aR: [-1.4, 0, .45], hx: -.05 });
    const a = -.95 + u * .4; look(V(Math.sin(a) * 8.2, 3.7, -3 + Math.cos(a) * 8.2).add(handheld(t)), V(0, 4.6, -3), 36, .12); dof(8.3, .005); fx.tw.at(t, V(0, 4.8, -3), 1.6); }],
  [C(wi('dragon')), C(wi('the', 2)), (t, u) => { DAY(); P.userData.tick(t, 0); crowdPose(folk, t, 'party'); kidsParty(t); leoParty(); pose(leo, { e: 'joy', aL: [-.3, 0, 2.4], aR: [-.3, 0, -2.4], hx: -.1 });
    const k = t - C(wi('dragon')); baby.visible = k > .06; baby.scale.setScalar(k < .06 ? 0 : k < .16 ? lerp(.1, .5, (k - .06) / .1) : lerp(.5, .42, clamp((k - .16) / .12)));
    baby.userData.tick(t, 14, .5); baby.rotation.y = .45; fx.poof.at(t, C(wi('dragon')) + .04, V(2, 3.4, -.9));
    look(lerpV(V(4.2, 4.1, 5.2), V(3.6, 3.9, 4.1), eo(u)).add(handheld(t, .6)), V(1.6, 3.6, -.6), 34); dof(5, .007); }],
  [C(wi('the', 2)), C(wi('the', 3)), (t, u) => { setTOD('golden'); gradeSet(1.2, 1.06, [1.04, .99, .94], .3); P.visible = false; kids.forEach(k => k.visible = false); folk.forEach(c => c.visible = false); leo.visible = false;
    look(lerpV(V(30, 9, 40), V(24, 11, 30), eio(u)), V(-20, 18, -120), 46); dof(80, .0003); }],
  [C(wi('the', 3)), C(wi('dark')), (t, u) => { const k = eio(clamp(u * 1.3)); setTOD('golden', 'night', k); gradeSet(lerp(1.2, .95, k), lerp(1.06, 1.15, k), [lerp(1.04, .9, k), lerp(.99, .9, k), lerp(.94, 1.08, k)], .3 + .15 * k);
    P.visible = false; kids.forEach(k => k.visible = false); folk.forEach(c => c.visible = false); leo.visible = false;
    look(V(-18, 2.2, 14).add(handheld(t, 1.5)), V(-30, 26 + u * 10, -34), 50, -.08); dof(60, .0003);
    big.visible = true; big.position.set(lerp(-110, 30, u), 58, lerp(-80, -60, u)); big.rotation.set(0, Math.PI / 2 - .2, -.1); big.userData.tick(t, 4, .8);
    if (u > .7) { swarm.visible = true; swarm.userData.tick(t); } }],
  [C(wi('dark')), C(wi('thousands')), (t, u) => { setTOD('night'); gradeSet(.95, 1.15, [.9, .9, 1.08], .45); P.visible = false; kids.forEach(k => k.visible = false); folk.forEach(c => c.visible = false);
    leo.position.set(0, 0, 10); leo.rotation.y = 0; pose(leo, { e: 'shock', hx: -.28 });
    const k = eo(u); look(V(.3, 3.7, 10 + lerp(6, 4.4, k)).add(handheld(t, 1.3)), V(0, 4.75, 10), lerp(36, 28, k)); dof(lerp(5, 3.5, k), .007); swarm.visible = true; swarm.userData.tick(t); }],
  [C(wi('thousands')), 99, (t, u) => { setTOD('night'); gradeSet(1.0, 1.15, [.92, .9, 1.08], .42); P.visible = false; kids.forEach(k => k.visible = false);
    folk.forEach(c => c.visible = c.position.z < 4); crowdPose(folk, t, 'scared');
    leo.position.set(0, 0, 10); leo.rotation.y = Math.PI; pose(leo, { e: 'shock', hx: -.5, aL: [0, 0, .5], aR: [0, 0, -.5] });
    const u2 = clamp((t - C(wi('thousands'))) / 2.2), k = eio(u2);
    look(V(1.4, lerp(1.8, 1.3, k), 10 + lerp(10.5, 13, k)).add(handheld(t, 1.4)), V(0, lerp(9, 46, k), lerp(-4, -60, k)), lerp(58, 68, k)); dof(lerp(11, 60, k), lerp(.003, .0005, k));
    const bk = clamp((t - (C(wi('thousands')) + .35)) / 1.2); big.visible = bk > 0 && bk < 1; big.position.set(lerp(-80, 80, bk), lerp(42, 52, bk), lerp(-30, -55, bk)); big.rotation.set(-.15, Math.PI / 2 + .15, .15); big.userData.tick(t, 4.5, .85);
    swarm.visible = true; swarm.userData.tick(t); flash(Math.max(clamp(.6 - (t - C(wi('thousands'))) * 5), clamp(.4 - Math.abs(t - C(wi('thousands')) - 1.3) * 6))); }],
];
run(S);
