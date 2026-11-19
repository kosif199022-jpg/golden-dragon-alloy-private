// Maven 3D story. Edit the WORLD and the SHOTS; everything else is in core.js and kits/.
// Rules of the style (references/style.md): a cut every ~1.1 s on the spoken noun, the camera never still,
// a reaction face punch-in on every emotional beat, one-word captions (automatic), DOF + bloom always on.
import { TOD, V, lerp, lerpV, clamp, eio, eo, run, look, dof, gradeSet, setTOD, shadowAt, flash, handheld, C, ws, wi, WD, onReset, CAM, overlay, faceOf } from './core.js';
import { cast, avatar, CAST, pose, POSES, walk, runCycle, crowd, crowdPose } from './kits/characters.js';
import { town, party, room, classroom, forest, spookyStreet, castle, iceWorld, beach, city, clouds, house, tree, TEX } from './kits/sets.js';
import { dragon, flock, beast, stranger, ghost, slime, pet } from './kits/creatures.js';
import { mysteryCube, portalDoor, chest, textPanel, clock, car, remote, trophy, goldify, throne, countdown } from './kits/props.js';
import { burst, twinkle, confetti, poof, weather, motes, lightning, portal, orb, dust, soundWord, hudPill, chapterCard } from './kits/fx.js';

// ---------- WORLD (build once) ----------
// Sets live far apart so several can coexist: town at (0,0), others at multiples of 4000.
town(0, 0); clouds();
const hero = cast('hero');                       // presets: hero heroine puffer mom dad grandpa explorer bully king police doctor teacher knight mayor sleepy
const folk = crowd(30, V(0, 0, 0), 11, 26);      // extras ring around the plaza (camera-safe)
const fx = { tw: twinkle(), sparks: burst() };

// reset per frame: anything a shot may hide or change must be restored here (seek(t) must be pure)
onReset(t => { hero.visible = true; });

// ---------- SHOTS ----------
// The template cuts at 1/3 and 2/3 of the words so it runs with any script; replace A and B with C(wi('your noun')).
const A = C(Math.round(WD.length / 3)), B = C(Math.round(WD.length * 2 / 3));
// [start, end, (t, u) => {...}]  t = seconds, u = 0..1 progress in the shot.
// C(wi('word')) = 40 ms before that word is spoken; wi('the', 2) = the 2nd "the". Works for Arabic words too.
const S = [
  // 1. HOOK: the rule over the most striking picture (fly-over / low angle on something huge)
  [0, A, (t, u) => {
    setTOD('day'); gradeSet(1.28, 1.08, [1.02, 1, .97], .26); crowdPose(folk, t, 'idle');
    CAM.fly(u, V(-120, 78, 190), V(-30, 22, 46), V(0, 0, -20), V(0, 5, -2), 44); dof(200, .0004);
  }],
  // 2. the hero, medium shot, walking
  [A, B, (t, u) => {
    setTOD('day'); crowdPose(folk, t, 'idle');
    hero.position.set(0, 0, lerp(-4, 2, u)); hero.rotation.y = 0; pose(hero, { ...walk(t), e: 'smile' });
    look(V(1.5, 3.4, hero.position.z + 9).add(handheld(t)), faceOf(hero, 4.2), 40); dof(9, .004);
  }],
  // 3. reaction punch-in
  [B, 99, (t, u) => {
    setTOD('day'); hero.position.set(0, 0, 2); pose(hero, { e: 'shock', hx: -.2 });
    CAM.punch(u, faceOf(hero)); dof(lerp(5, 3.4, eo(u)), .007);
  }],
];
run(S);   // options: run(S, { tail: 1.0, whip: .085, whipAmount: .22, noWhip: [shotIndex] })
