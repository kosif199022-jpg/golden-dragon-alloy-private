// Kit gallery: one second per kit, to check everything renders. Open index.html?story=gallery.js
import { THREE, V, run, look, dof, gradeSet, setTOD, shadowAt, overlay, lerp, eio, handheld } from './core.js';
import { cast, avatar, pose, POSES, walk, crowd, crowdPose, CAST, FACE_DRAW } from './kits/characters.js';
import { town, party, room, classroom, forest, spookyStreet, castle, iceWorld, beach, city, clouds } from './kits/sets.js';
import { dragon, flock, beast, stranger, ghost, slime, pet } from './kits/creatures.js';
import { mysteryCube, portalDoor, chest, textPanel, clock, car, remote, trophy, goldify, throne } from './kits/props.js';
import { burst, twinkle, confetti, poof, weather, motes, lightning, portal, orb, dust, soundWord, hudPill, chapterCard } from './kits/fx.js';

const S = 4000;   // sets sit 4000 apart
const T = town(0, 0), P = party(0, 0), RM = room(S, 0), CL = classroom(S, S), FO = forest(-S, 0), SP = spookyStreet(0, S), CA = castle(0, -S), IC = iceWorld(S, -S), BE = beach(-S, S), CI = city(-S, -S, { night: true });
clouds();
// cast lineup in the plaza
const names = Object.keys(CAST), line = names.map((n, i) => { const a = cast(n); a.position.set((i - (names.length - 1) / 2) * 3.2, 0, 14); return a; });
// faces row
const faces = Object.keys(FACE_DRAW).filter(f => f !== 'blank'), heads = faces.map((f, i) => { const a = cast('hero'); const u = a.userData; [u.torso, u.armL, u.armR, u.legL, u.legR].forEach(p => p.visible = false); a.visible = false; return [a, f, i]; });
const kids = crowd(40, V(0, 0, 0), 11, 26, { hats: .4 });
const st = stranger(); st.position.set(0, 0, S - 120);
const king = cast('king'); king.position.set(0, 1.2 + 2.4, -S - 31.6); const knight = cast('knight'); knight.position.set(5, 0, -S - 24); const thr = throne(); thr.position.set(0, 1.2, -S - 32);
const bst = beast({ scale: 1.4 }); bst.position.set(S, 60, -S - 90);
const dog = pet(), cat = pet({ kind: 'cat' }), sl = slime(); dog.position.set(-S - 4, 0, S); cat.position.set(-S + 4, 0, S); sl.position.set(-S, 0, S + 4);
const cr = car(); cr.position.set(-S - 5, 0, -S);
const cube = mysteryCube(); cube.position.set(S * 2, 0, 0);
const door = portalDoor(); door.position.set(S * 2, 0, 120); const ch = chest(); ch.position.set(S * 2 + 8, 0, 124); const ck = clock(); ck.position.set(S * 2 - 9, 6, 120);
const sign = textPanel('في هذا العالم\nIn this world', { w: 7, h: 3.6, post: 5, size: 120 }); sign.position.set(S * 2 - 4, 0, 128);
const gold = goldify(cast('explorer')); gold.position.set(S * 2 + 3, 0, 110); const tro = trophy(); tro.position.set(S * 2 + 12, 0, 128);
const dr = dragon({ scale: 2 }); dr.position.set(0, 30, -20); const baby = dragon({ body: '#4ade80', belly: '#fef08a', wing: '#22c55e', horn: '#fde68a', cute: true, scale: .5 }); baby.position.set(2, 2.9, -.4);
const fl = flock({ center: V(0, 0, 0) }); const gh = ghost(); gh.position.set(6, 0, S - 60);
const fx = { b: burst(), tw: twinkle(), cf: confetti(), pf: poof(), sn: weather(), rn: weather({ kind: 'rain' }), mo: motes(), li: lightning(), du: dust() };
const por = portal({ r: 3.4 }); por.position.set(S * 2, 5.5, 120.5);
let cur = '';
overlay((ctx, t) => { ctx.font = '800 54px Pop'; ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 10; ctx.textAlign = 'left'; ctx.strokeText(cur, 40, 1860); ctx.fillText(cur, 40, 1860); });
const sh = (name, fn) => (t, u) => { cur = name; fn(t, u); };
const SH = [
  ['cast lineup', (t, u) => { setTOD('day'); kids.forEach(k => k.visible = false); line.forEach((a, i) => pose(a, i % 3 ? POSES.idle(t + i) : POSES.wave(t))); look(V(0, 6, 31), V(0, 3.5, 14), 70); dof(17, .001); }],
  ['faces', (t, u) => { setTOD('indoor'); heads.forEach(([a, f, i]) => { a.visible = true; a.position.set(S + (i % 6 - 2.5) * 1.9, 2 - Math.floor(i / 6) * 1.75, -4); pose(a, { e: f }); }); look(V(S, 4.5, 8), V(S, 4.1, -4), 50); dof(12, .0003); }],
  ['town + crowd', (t, u) => { setTOD('day'); crowdPose(kids, t, 'party'); look(V(-60, 40, 90), V(0, 4, 0), 46); dof(100, .0003); }],
  ['party + fx', (t, u) => { setTOD('day'); P.userData.tick(t); crowdPose(kids, t, 'cheer'); fx.cf.at(t); fx.tw.at(t, V(0, 4, -.5)); fx.pf.at(t, 3.1, V(2, 3.4, -.4)); look(V(4, 5, 9), V(0, 3, -.5), 40); dof(9.5, .003); }],
  ['room', (t, u) => { setTOD('indoor'); shadowAt(S, 0, 20); look(V(S - 8, 7, 9), V(S + 2, 3, -5), 60); dof(12, .001); }],
  ['classroom', (t, u) => { setTOD('indoor'); shadowAt(S, S, 25); look(V(S + 10, 9, S + 12), V(S - 2, 4, S - 8), 60); dof(18, .0008); }],
  ['forest + fireflies', (t, u) => { setTOD('golden'); shadowAt(-S, 0, 60); fx.mo.at(t, V(-S, 0, -20)); look(V(-S + 2, 4, 30), V(-S, 5, -40), 50); dof(40, .0006); }],
  ['spooky street + stranger', (t, u) => { setTOD('spooky'); shadowAt(0, S - 100, 80); st.userData.tick(t); gh.userData.tick(t); look(V(-3, 4, S - 90), V(0, 8, S - 130), 50); dof(32, .0008); }],
  ['castle + king', (t, u) => { setTOD('day'); shadowAt(0, -S - 30, 60); pose(king, { ...POSES.sit(), e: 'smirk', aL: [-.3, 0, .2], aR: [-.3, 0, -.2] }); pose(knight, { e: 'determined' }); look(V(10, 7, -S - 8), V(0, 5, -S - 30), 46); dof(24, .0012); }],
  ['ice world + beast', (t, u) => { setTOD('ice'); shadowAt(S, -S, 80); bst.userData.tick(t, V(S, 5, -S + 30)); look(V(S + 10, 3, -S + 10), V(S, 50, -S - 90), 55); dof(100, .0003); fx.sn.at(t, V(S, 0, -S + 20)); }],
  ['beach + pets + slime', (t, u) => { setTOD('golden'); shadowAt(-S, S, 30); dog.userData.tick(t, 1); cat.userData.tick(t); sl.userData.tick(t); look(V(-S + 2, 5, S + 24), V(-S, 2, S + 1), 34); dof(23, .0015); }],
  ['city at night + car + rain', (t, u) => { setTOD('night'); shadowAt(-S, -S, 60); cr.userData.tick(t, 10); fx.rn.at(t, V(-S, 0, -S)); look(V(-S + 8, 5, -S + 18), V(-S - 3, 6, -S - 60), 50); dof(20, .0008); }],
  ['mystery cube', (t, u) => { setTOD('day'); shadowAt(S * 2, 0, 80); cube.userData.open(.8); cube.userData.countdown.userData.set(3599 - t * 10); look(V(S * 2 + 30, 6, 110), V(S * 2, 30, 0), 56); dof(80, .0004); fx.du.at(t, 11.0, V(S * 2, 0, 31)); }],
  ['props: door, chest, clock, sign, statue', (t, u) => { setTOD('day'); shadowAt(S * 2, 120, 30); door.userData.open(.7); por.userData.tick(t); ch.userData.open(.8); ck.userData.set(11, 58, t * 60); look(V(S * 2 + 4, 8, 165), V(S * 2, 5, 120), 58); dof(40, .0006); }],
  ['dragons', (t, u) => { setTOD('night'); fl.userData.tick(t); dr.userData.tick(t); baby.userData.tick(t, 14, .5); look(V(0, 3, 30), V(0, 25, -40), 60); dof(40, .0005); fx.li.at(t, 14.3, V(40, 140, -200), V(30, 0, -120)); }],
];
const hide = () => { heads.forEach(([a]) => a.visible = false); kids.forEach(k => k.visible = true); };
run(SH.map(([n, f], i) => [i, i + 1, (t, u) => { hide(); sh(n, f)(t, u); }]), { end: SH.length, noWhip: SH.map((_, i) => i) });
