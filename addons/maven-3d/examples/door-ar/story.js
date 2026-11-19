// Example (Arabic): «في هذا العالم، كلُّ بابٍ في المدرسة يفتحُ على عالمٍ مختلف...»
// Arabic captions are right-to-left in Lalezar; shots are keyed to Arabic words with wi() (diacritics ignored).
import { TOD, V, lerp, lerpV, clamp, eio, eo, run, look, dof, gradeSet, setTOD, shadowAt, flash, handheld, C, wi, onReset, CAM, overlay } from './core.js';
import { cast, avatar, CAST, pose, POSES, walk, crowd, crowdPose } from './kits/characters.js';
import { town, room, castle, clouds, TEX } from './kits/sets.js';
import { portalDoor, throne } from './kits/props.js';
import { portal, twinkle, motes, soundWord } from './kits/fx.js';

const HX = 4000, CX = 0, CZ = -4000;           // corridor at (4000, 0), castle at (0, -4000)
town(0, 0); castle(CX, CZ); clouds();
const hall = room(HX, 0, { kind: 'empty', w: 16, d: 70, h: 14, wallTex: TEX.wallpaper('#f5e8c8', '#efdfba'), floor: '#b88a5a', skyCol: '#ffe2b0', light: 45 });
TOD.hall = { ...TOD.indoor, hi: .9, si: 1.2, exp: .95 };
TOD.castle = { ...TOD.day, sd: [.55, .75, -.25] };
// a corridor of glowing doors, each to a different world
const COLS = ['#ff7ad9', '#7afcff', '#ffd36a', '#8aff7a', '#b07aff', '#ff9a6a'];
const doors = [], swirls = [];
for (let i = 0; i < 6; i++) { const s = i % 2 ? 1 : -1, z = 20 - Math.floor(i / 2) * 14 - (s > 0 ? 7 : 0); const d = portalDoor({ col: COLS[i] }); d.position.set(HX + s * 7.7, 0, z); d.rotation.y = -s * Math.PI / 2; doors.push(d);
  const p = portal({ r: 2.9, c1: COLS[i], c2: COLS[(i + 2) % 6] }); p.position.set(HX + s * 7.3, 4.6, z); p.rotation.y = -s * Math.PI / 2; p.scale.y = 1.5; swirls.push(p); }
const SAMI_DOOR = 2;                            // left side, z = 6
const sami = cast('hero', { shirt: '#16a34a', kind: 'hoodie', logoCol: '#ffffff', hair: 'swoop', hairCol: '#2a1b14', acc: [['backpack', { col: '#f59e0b' }]] });
// the king without his beard, so the grin shows
const king = avatar({ ...CAST.king, acc: ['crown', 'cape', ['mustache', { col: '#e8e0d0' }]] }); const thr = throne(); thr.position.set(CX, 1.2, CZ - 32); king.position.set(CX, 3.6, CZ - 31.6);
const guards = [-6, 6].map(x => { const g = cast('knight'); g.position.set(CX + x, 1.2, CZ - 28); return g; });
const court = crowd(24, V(CX, 0, CZ - 6), 14, 26);
const fx = { tw: twinkle({ col: 0xfff2b0 }), motes: motes({ n: 160, col: 0xffe6a0, radius: 7, height: 12 }) };
onReset(t => { doors.forEach((d, i) => d.userData.open(i === SAMI_DOOR ? 0 : .12)); swirls.forEach((p, i) => { p.userData.tick(t + i); p.visible = i !== SAMI_DOOR; }); sami.visible = true; });
const HALL = () => { setTOD('hall'); shadowAt(HX, 0, 40); gradeSet(1.25, 1.08, [1.03, 1, .96], .3); };
const CASTLE = () => { setTOD('castle'); shadowAt(CX, CZ - 20, 60); gradeSet(1.25, 1.1, [1.03, 1, .95], .3); };
const sit = () => pose(king, { ...POSES.sit(), e: 'smirk', aL: [-.3, 0, .25], aR: [-.3, 0, -.25] });
const dz = 20 - 14 - 0;                          // z of Sami's door (i = 2 -> left, z = 6)

const S = [
  // «في هذا العالم،» aerial over the town toward the school
  [0, C(wi('كل')), (t, u) => { setTOD('day'); gradeSet(1.28, 1.08, [1.02, 1, .97], .26); sami.visible = false; CAM.fly(u, V(140, 90, 170), V(50, 30, 60), V(0, 0, -10), V(0, 6, 0), 46); dof(200, .0003); }],
  // «كلُّ بابٍ في المدرسة يفتحُ» dolly down the corridor of glowing doors
  [C(wi('كل')), C(wi('على')), (t, u) => { HALL(); sami.visible = false; look(lerpV(V(HX + .8, 5.5, 33), V(HX - .4, 5, 14), eio(u)).add(handheld(t)), V(HX, 4.6, -20), 56); dof(18, .002); }],
  // «على عالمٍ مختلف.» push into one door's swirl
  [C(wi('على')), C(wi('في', 3)), (t, u) => { HALL(); sami.visible = false; const d = doors[3]; d.userData.open(eo(clamp(u * 1.6)));
    const k = eio(u); look(lerpV(V(HX - 3, 4.8, d.position.z), V(HX + 1.2, 4.6, d.position.z), k).add(handheld(t, .6)), V(HX + 7.7, 4.6, d.position.z), lerp(54, 44, k)); dof(lerp(10.5, 6.5, k), .004); fx.tw.at(t, V(HX + 6.5, 3, d.position.z), 2, 6); }],
  // «في الصباح،» morning: Sami walks down the corridor toward us
  [C(wi('في', 3)), C(wi('فتح')), (t, u) => { HALL(); const z = lerp(-14, -6, u); sami.position.set(HX, 0, z); sami.rotation.y = 0; pose(sami, { ...walk(t), e: 'smile' });
    look(V(HX + 1.2, 3.2, z + 9).add(handheld(t)), V(HX, 4.2, z), 40); dof(9, .004); fx.motes.at(t, V(HX, 0, z)); }],
  // «فتح سامي بابَ الصف،» over the shoulder: he pulls the door, light spills out
  [C(wi('فتح')), C(wi('فوجد')), (t, u) => { HALL(); const d = doors[SAMI_DOOR], k = eo(clamp((u - .25) / .75)); d.userData.open(k); swirls[SAMI_DOOR].visible = k > .05;
    sami.position.set(HX - 5.3, 0, dz); sami.rotation.y = -Math.PI / 2; pose(sami, { e: k > .2 ? 'shock' : 'determined', aR: [-1.45, 0, -.1], lean: k > .2 ? -.08 : 0 });
    look(V(HX + 1.6, 6.2, dz + 4.4).add(handheld(t, .7)), V(HX - 7.4, 4.5, dz), 50); dof(8, .004); flash(k * .1, [1, .8, 1]); }],
  // «فوجد نفسه في قلعةٍ» crane down into the castle courtyard, Sami small in the middle
  [C(wi('فوجد')), C(wi('قديمة')), (t, u) => { CASTLE(); sami.position.set(CX, 0, CZ + 8); sami.rotation.y = Math.PI; pose(sami, { e: 'shock', hx: -.3, hy: Math.sin(t * 3) * .4 });
    crowdPose(court, t, 'idle'); sit(); guards.forEach(g => pose(g, { e: 'determined' }));
    const k = eio(u); look(lerpV(V(CX + 22, 52, CZ + 66), V(CX + 12, 9, CZ + 26), k), lerpV(V(CX, 8, CZ - 6), V(CX, 4, CZ + 6), k), 50); dof(lerp(60, 22, k), .001); }],
  // «قديمة.» punch-in on Sami's shocked face
  [C(wi('قديمة')), C(wi('نظر')), (t, u) => { CASTLE(); sami.position.set(CX, 0, CZ + 8); sami.rotation.y = Math.PI; pose(sami, { e: 'shock', hx: -.1 }); sit(); crowdPose(court, t, 'idle');
    CAM.punch(u, V(CX, 4.75, CZ + 8), -5, -3.6, .3); dof(lerp(5, 3.6, eo(u)), .007); }],
  // «نظر إليه الملك وقال:» low angle on the king, his head turns to Sami
  [C(wi('نظر')), C(wi('أخيرا')), (t, u) => { CASTLE(); sami.position.set(CX, 0, CZ + 8); sami.rotation.y = Math.PI; pose(sami, { e: 'worried' }); guards.forEach(g => pose(g, { e: 'determined' })); crowdPose(court, t, 'idle');
    pose(king, { ...POSES.sit(), e: 'neutral', aL: [-.3, 0, .25], aR: [-.3, 0, -.25], hy: lerp(.7, 0, eo(clamp(u * 1.6))) });
    look(V(CX + 4.5, 4.4, CZ - 20).add(handheld(t)), V(CX, 6.8, CZ - 31.6), 40); dof(12.4, .003); }],
  // «أخيرًا وصلت.» push in on the king's grin
  [C(wi('أخيرا')), 99, (t, u) => { CASTLE(); sami.visible = false; crowdPose(court, t, 'idle'); pose(king, { ...POSES.sit(), e: 'evil', aL: [-.3, 0, .25], aR: [-.3, 0, -.25], hx: .08 });
    const k = eo(clamp((t - C(wi('أخيرا'))) / 1.4)); look(V(CX + .5, 7.0, CZ - 31.6 + lerp(9.5, 6.6, k)).add(handheld(t, .8)), V(CX, 7.25, CZ - 31.6), lerp(34, 28, k)); dof(lerp(9.5, 6.6, k), .006);
    flash(clamp(.4 - (t - C(wi('وصلت'))) * 3) * (t > C(wi('وصلت')) ? 1 : 0), [1, .85, .6]); }],
];
run(S);
