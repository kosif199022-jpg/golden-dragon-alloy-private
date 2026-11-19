// Props: mystery cube with glyph walls and doors, golden portal door, 7-segment countdown, chest, signboard and note
// (any language, Arabic included), wall clock, car, remote, trophy, gold statue (goldify), throne chair.
import { THREE, canvasTex, mat, glow, box, rbox, cyl, ball, at, R, seed, scene, V, LANG } from '../core.js';

const GOLD = () => mat('#e8b84a', { metalness: .75, roughness: .28, emissive: '#5a3a00', emissiveIntensity: .25 });
// glyph panel texture (gold symbols on dark tiles)
export const glyphTex = (rep = 1) => canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#1a1c2a'; g.fillRect(0, 0, w, h); g.strokeStyle = '#d9a640'; g.fillStyle = '#d9a640'; g.lineWidth = 7; g.lineCap = 'round';
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { const x = 64 + i * 128, y = 64 + j * 128, k = (i * 7 + j * 3) % 6; g.save(); g.translate(x, y);
    g.strokeRect(-58, -58, 116, 116);
    if (k === 0) { g.beginPath(); g.arc(0, 0, 36, 0, 7); g.stroke(); g.beginPath(); g.arc(0, 0, 14, 0, 7); g.fill(); }
    if (k === 1) { g.beginPath(); for (let a = 0; a < 5; a++) { const b = -Math.PI / 2 + a * 4 * Math.PI / 5; g.lineTo(Math.cos(b) * 38, Math.sin(b) * 38); } g.closePath(); g.stroke(); }
    if (k === 2) { g.beginPath(); for (let a = 0; a < 12; a += .3) g.lineTo(Math.cos(a) * a * 3.2, Math.sin(a) * a * 3.2); g.stroke(); }
    if (k === 3) { for (let r = 0; r < 3; r++) { g.beginPath(); g.moveTo(-34, -24 + r * 24); g.lineTo(34, -24 + r * 24); g.stroke(); } }
    if (k === 4) { g.beginPath(); g.moveTo(0, -38); g.lineTo(34, 30); g.lineTo(-34, 30); g.closePath(); g.stroke(); g.beginPath(); g.arc(0, 8, 10, 0, 7); g.fill(); }
    if (k === 5) { for (let a = 0; a < 8; a++) { g.beginPath(); g.moveTo(0, 0); g.lineTo(Math.cos(a * Math.PI / 4) * 38, Math.sin(a * Math.PI / 4) * 38); g.stroke(); } }
    g.restore(); } }, rep);

// ---------- 7-segment countdown (texture you redraw per frame) ----------
export function countdown(o = {}) {
  const c = document.createElement('canvas'); c.width = 512; c.height = 200; const ctx = c.getContext('2d'), tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(o.w || 6, (o.w || 6) * 200 / 512), new THREE.MeshStandardMaterial({ map: tex, emissiveMap: tex, emissive: '#ffffff', emissiveIntensity: 1.2 }));
  const SEG = { 0: 'abcdef', 1: 'bc', 2: 'abged', 3: 'abgcd', 4: 'fgbc', 5: 'afgcd', 6: 'afgedc', 7: 'abc', 8: 'abcdefg', 9: 'abcfgd' };
  function digit(x, d, on) { const s = SEG[d] || '', W2 = 80, H2 = 150, T = 16, y = 25; const segs = { a: [x, y, W2, T], d: [x, y + H2 - T, W2, T], g: [x, y + H2 / 2 - T / 2, W2, T], f: [x, y, T, H2 / 2], b: [x + W2 - T, y, T, H2 / 2], e: [x, y + H2 / 2, T, H2 / 2], c: [x + W2 - T, y + H2 / 2, T, H2 / 2] }; for (const k in segs) { ctx.fillStyle = s.includes(k) ? on : 'rgba(255,255,255,.06)'; ctx.fillRect(...segs[k]); } }
  m.userData.set = (secs, col = o.col || '#ffd27a') => { secs = Math.max(0, Math.ceil(secs)); const mm = String(Math.floor(secs / 60)).padStart(2, '0'), ss = String(secs % 60).padStart(2, '0'); ctx.fillStyle = '#120a06'; ctx.fillRect(0, 0, 512, 200); [mm[0], mm[1]].forEach((d, i) => digit(40 + i * 100, d, col)); ctx.fillStyle = col; ctx.fillRect(248, 70, 16, 16); ctx.fillRect(248, 120, 16, 16); [ss[0], ss[1]].forEach((d, i) => digit(290 + i * 100, d, col)); tex.needsUpdate = true; };
  m.userData.set(o.secs ?? 3600); return m;
}

// ---------- giant mystery cube with doors (doors open with userData.open(k)) ----------
export function mysteryCube(o = {}) {
  const S = o.size || 60, g = new THREE.Group(), gm = mat('#fff', { map: glyphTex(3), emissiveMap: glyphTex(3), emissive: '#ffcc66', emissiveIntensity: .35, roughness: .5 });
  g.add(at(box(S, S, S, gm), 0, S / 2, 0));
  const frame = GOLD(), dw = S * .22, dh = S * .36;
  g.add(at(box(dw + 3, dh + 2, 1.2, frame), 0, dh / 2 + 1, S / 2 + .3));
  const portal = new THREE.Mesh(new THREE.PlaneGeometry(dw, dh), mat('#fff', { emissive: o.inside || '#b07aff', emissiveIntensity: 1.6 })); portal.position.set(0, dh / 2, S / 2 + .9); g.add(portal);
  const doors = []; for (const s of [-1, 1]) { const p = new THREE.Group(); p.position.set(s * dw / 2, 0, S / 2 + 1.1); const d = box(dw / 2, dh, .6, mat('#fff', { map: glyphTex(1), metalness: .3 })); d.position.set(-s * dw / 4, dh / 2, 0); p.add(d); g.add(p); doors.push([p, s]); }
  const cd = countdown({ w: dw * .9 }); cd.position.set(0, dh + 5, S / 2 + .95); g.add(cd);
  g.userData = { portal, countdown: cd, open(k) { doors.forEach(([p, s]) => p.rotation.y = -s * k * 1.9); portal.visible = k > .02; } };
  g.userData.open(0); scene.add(g); return g;
}

// ---------- golden portal door ----------
export function portalDoor(o = {}) {
  const g = new THREE.Group(), gm = GOLD(), w = o.w || 6, h = o.h || 9;
  g.add(at(box(w + 1.4, h + 1.2, 1, gm), 0, (h + 1.2) / 2, -.2), at(ball(1.2, gm, 2), 0, h + 1.2, -.2));
  const light = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat('#000', { emissive: o.col || '#fff3c0', emissiveIntensity: o.glow ?? .9 })); light.position.set(0, h / 2, .31); g.add(light);
  const doors = []; for (const s of [-1, 1]) { const p = new THREE.Group(); p.position.set(s * w / 2, 0, .4); p.add(at(box(w / 2, h, .4, gm), -s * w / 4, h / 2, 0)); g.add(p); doors.push([p, s]); }
  g.userData = { open(k) { doors.forEach(([p, s]) => p.rotation.y = -s * k * 1.7); light.visible = k > .02; } }; g.userData.open(0); scene.add(g); return g;
}

// ---------- treasure chest ----------
export function chest(o = {}) {
  const g = new THREE.Group(), wd = mat('#8a5a2a'), gm = GOLD(); g.add(at(box(3, 1.8, 2, wd), 0, .9, 0), at(box(3.1, .25, 2.1, gm), 0, 1.6, 0), at(box(.5, .7, .1, gm), 0, 1.3, 1.02));
  const lid = new THREE.Group(); lid.position.set(0, 1.8, -1); lid.add(at(box(3, .8, 2, wd), 0, .4, 1)); g.add(lid);
  const gl = new THREE.PointLight(0xffc860, 0, 10, 1.5); gl.position.set(0, 2.4, 0); g.add(gl);
  const coins = at(box(2.6, .3, 1.6, glow('#ffcc33', 1.5)), 0, 1.75, 0); g.add(coins);
  g.userData.open = (k) => { lid.rotation.x = -k * 1.9; gl.intensity = k * 25; coins.visible = k > .1; }; g.userData.open(0); scene.add(g); return g;
}

// ---------- signboard / note / chalkboard text (Arabic works: pass dir:'rtl' or rely on LANG) ----------
export function textPanel(text, o = {}) {
  const w = o.w || 6, h = o.h || 3, px = 1024, py = Math.round(px * h / w), rtl = (o.dir || (LANG === 'ar' ? 'rtl' : 'ltr')) === 'rtl';
  const tex = canvasTex(px, py, (g) => { g.fillStyle = o.bg || '#fdf6e3'; g.fillRect(0, 0, px, py); if (o.lines) { g.strokeStyle = 'rgba(80,120,200,.35)'; g.lineWidth = 3; for (let y = 120; y < py; y += 90) { g.beginPath(); g.moveTo(40, y); g.lineTo(px - 40, y); g.stroke(); } }
    g.fillStyle = o.col || '#1c1c28'; g.direction = rtl ? 'rtl' : 'ltr'; g.textAlign = o.align || 'center'; const fs = o.size || 110; g.font = o.font || (rtl ? `${fs}px Ar` : `800 ${fs}px Pop`);
    String(text).split('\n').forEach((ln, i, all) => g.fillText(ln, o.align === 'left' ? 60 : o.align === 'right' ? px - 60 : px / 2, py / 2 + (i - (all.length - 1) / 2) * fs * 1.25 + fs * .35)); });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat('#fff', { map: tex, roughness: .8, side: THREE.DoubleSide })); m.castShadow = true;
  if (o.post) { const g = new THREE.Group(); g.add(at(box(.4, o.post, .4, mat('#6b4a2a')), 0, o.post / 2, -.15), at(m, 0, o.post + h / 2 - .4, 0)); scene.add(g); return g; }
  scene.add(m); return m;
}

// ---------- wall clock (set(hours, minutes)) ----------
export function clock(o = {}) {
  const g = new THREE.Group(), r = o.r || 2; g.add(at(cyl(r + .25, r + .25, .4, mat(o.rim || '#c8a040', { metalness: .5 }), 40), 0, 0, 0)); g.children[0].rotation.x = Math.PI / 2;
  g.add(at(new THREE.Mesh(new THREE.CircleGeometry(r, 48), mat('#fff', { map: canvasTex(256, 256, (c) => { c.fillStyle = '#fffbea'; c.fillRect(0, 0, 256, 256); c.fillStyle = '#111'; c.font = 'bold 34px sans-serif'; c.textAlign = 'center'; for (let i = 1; i <= 12; i++) { const a = i / 12 * Math.PI * 2 - Math.PI / 2; c.fillText(i, 128 + Math.cos(a) * 96, 140 + Math.sin(a) * 96); } }) })), 0, 0, .22));
  const hand = (l, w, c) => { const m = box(w, l, .06, mat(c)); m.geometry.translate(0, l / 2, 0); m.position.z = .28; g.add(m); return m; };
  const hh = hand(r * .5, .14, '#111'), mm = hand(r * .8, .09, '#111'), ss = hand(r * .85, .04, '#d12a2a');
  g.userData.set = (hours, mins, secs = 0) => { hh.rotation.z = -((hours % 12) + mins / 60) / 12 * Math.PI * 2; mm.rotation.z = -mins / 60 * Math.PI * 2; ss.rotation.z = -secs / 60 * Math.PI * 2; };
  g.userData.set(12, 0); scene.add(g); return g;
}

// ---------- car ----------
export function car(o = {}) {
  const g = new THREE.Group(), m = mat(o.col || '#ef4444', { roughness: .3, metalness: .2 }); g.add(at(rbox(4.4, 1.6, 9, .4, m), 0, 1.6, 0), at(rbox(4, 1.6, 4.8, .4, mat('#9fd8ff', { roughness: .1 })), 0, 3.1, -.6));
  const wheels = []; for (const [x, z] of [[-2.2, 2.8], [2.2, 2.8], [-2.2, -2.8], [2.2, -2.8]]) { const w = cyl(.9, .9, .7, mat('#1a1a1a'), 20); w.rotation.z = Math.PI / 2; at(w, x, .9, z); g.add(w); wheels.push(w); }
  for (const s of [-1, 1]) g.add(at(box(.8, .4, .1, glow('#fff6c8', 2)), s * 1.4, 1.7, 4.52));
  g.userData.tick = (t, speed = 0) => wheels.forEach(w => w.rotation.x = t * speed); scene.add(g); return g;
}

// ---------- TV remote (pause power) ----------
export function remote(o = {}) { const g = new THREE.Group(); g.add(rbox(.7, 2.2, .3, .12, mat('#1f2937')), at(ball(.16, glow('#ef4444', 2), 1), 0, .75, .16)); for (let i = 0; i < 6; i++) g.add(at(box(.18, .14, .06, mat('#9ca3af')), (i % 2 - .5) * .3, .2 - Math.floor(i / 2) * .3, .16)); scene.add(g); return g; }
// ---------- trophy ----------
export function trophy() { const g = new THREE.Group(), gm = GOLD(); g.add(at(box(1.4, .4, 1.4, mat('#3a2a1a')), 0, .2, 0), at(cyl(.2, .3, 1, gm), 0, .9, 0), at(cyl(.9, .4, 1.2, gm, 24), 0, 2, 0)); scene.add(g); return g; }
// ---------- turn any avatar into a gold statue (on a pedestal) ----------
export function goldify(avatarGroup, o = {}) { const gm = GOLD(); avatarGroup.traverse(n => { if (n.isMesh && !n.geometry.type.includes('Plane')) n.material = gm; }); if (o.pedestal !== false) { const p = cyl(2.6, 3, 2.4, gm, 8); p.position.y = -1.2; avatarGroup.add(p); avatarGroup.position.y += 2.4; } return avatarGroup; }
// ---------- throne ----------
export function throne(o = {}) { const g = new THREE.Group(), gm = GOLD(), red = mat(o.col || '#b91c1c'); g.add(at(box(4, 2.4, 3.4, gm), 0, 1.2, 0), at(box(3.4, .5, 2.8, red), 0, 2.6, .2), at(box(4, 6, .8, gm), 0, 4, -1.4), at(box(3, 4.2, .2, red), 0, 4.4, -.95)); scene.add(g); return g; }

export const PROPS = { countdown, mysteryCube, portalDoor, chest, textPanel, clock, car, remote, trophy, goldify, throne, glyphTex };
