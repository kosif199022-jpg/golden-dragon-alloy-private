// «كبّر نفسك»: Cap and Nadara meet a mountain lion. Same flat stickman look as the Abu Cap reels (@elkosif1),
// drawn entirely in code. 1080x1920, 30 fps, seekable: window.renderFrame(frame).
const W = 1080, H = 1920, FPS = 30, DUR = 27.0;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eio = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eout = t => 1 - Math.pow(1 - t, 3);
const back = t => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const INK = '#151515', LW = 5;
const GROUND = 1560;                       // feet line
const COL = { cap: '#e0303a', capDark: '#b31f28', nad: '#3a78c9', nadDark: '#2a5c9e', skin: '#f4f4f4' };

// ---------------- background (sky, sun, clouds, mountains, hill, trees, fence, barn, grass) ----------------
let BG = null;
function buildBG() {
  const b = document.createElement('canvas'); b.width = W; b.height = H; const c = b.getContext('2d');
  const sky = c.createLinearGradient(0, 0, 0, 1200); sky.addColorStop(0, '#9fd3ea'); sky.addColorStop(1, '#cdebf6');
  c.fillStyle = sky; c.fillRect(0, 0, W, H);
  // mountains (lavender with snow caps)
  const mtn = (x, peak, w, col) => {
    c.beginPath(); c.moveTo(x - w, 1180); c.lineTo(x, peak); c.lineTo(x + w, 1180); c.closePath(); c.fillStyle = col; c.fill();
    c.lineWidth = 3; c.strokeStyle = '#6f73a8'; c.stroke();
    const k = .22; c.beginPath(); c.moveTo(x, peak); c.lineTo(x - w * k, peak + (1180 - peak) * k);
    for (let i = 0; i < 4; i++) c.lineTo(x - w * k + (i + .5) * w * k / 2, peak + (1180 - peak) * k + (i % 2 ? -14 : 12));
    c.lineTo(x + w * k, peak + (1180 - peak) * k); c.closePath(); c.fillStyle = '#ffffff'; c.fill(); c.stroke();
  };
  mtn(170, 560, 420, '#a3a7d4'); mtn(880, 520, 460, '#9da1d0'); mtn(560, 690, 380, '#b0b4dc');
  // rolling hill
  c.beginPath(); c.moveTo(0, 1010); c.bezierCurveTo(300, 930, 650, 1060, 1080, 960); c.lineTo(1080, 1300); c.lineTo(0, 1300); c.closePath();
  c.fillStyle = '#9fdc72'; c.fill(); c.lineWidth = 4; c.strokeStyle = '#6aa64a'; c.stroke();
  // lollipop trees
  const tree = (x, y, r) => { c.fillStyle = '#7a4b25'; c.fillRect(x - 7, y, 14, 120); c.beginPath(); c.arc(x, y, r, 0, 7); c.fillStyle = '#86d957'; c.fill(); c.lineWidth = 4; c.strokeStyle = '#4f8f2e'; c.stroke(); };
  tree(80, 860, 78); tree(620, 905, 58);
  // red barn (right)
  c.save(); c.translate(940, 860);
  c.beginPath(); c.moveTo(-110, 60); c.lineTo(0, -40); c.lineTo(140, 60); c.closePath(); c.fillStyle = '#7b4a2b'; c.fill(); c.lineWidth = 4; c.strokeStyle = INK; c.stroke();
  c.fillStyle = '#cf2f37'; c.fillRect(-95, 58, 220, 170); c.strokeRect(-95, 58, 220, 170);
  c.fillStyle = '#fff'; c.fillRect(-20, 130, 70, 98); c.strokeRect(-20, 130, 70, 98);
  c.beginPath(); c.moveTo(-20, 130); c.lineTo(50, 228); c.moveTo(50, 130); c.lineTo(-20, 228); c.lineWidth = 6; c.strokeStyle = '#cf2f37'; c.stroke(); c.restore();
  // fence
  for (let x = -10; x < W + 40; x += 62) {
    c.beginPath(); c.moveTo(x, 1215); c.lineTo(x, 1110); c.lineTo(x + 18, 1090); c.lineTo(x + 36, 1110); c.lineTo(x + 36, 1215); c.closePath();
    c.fillStyle = '#d7a46a'; c.fill(); c.lineWidth = 3; c.strokeStyle = '#7a5530'; c.stroke();
  }
  for (const y of [1130, 1180]) { c.fillStyle = '#c99358'; c.fillRect(0, y, W, 16); c.strokeStyle = '#7a5530'; c.strokeRect(-2, y, W + 4, 16); }
  // grass field
  const g = c.createLinearGradient(0, 1200, 0, H); g.addColorStop(0, '#8fe05a'); g.addColorStop(1, '#5fbd3c');
  c.fillStyle = g; c.fillRect(0, 1210, W, H); c.beginPath(); c.moveTo(0, 1210); c.lineTo(W, 1210); c.lineWidth = 4; c.strokeStyle = '#4c9a2c'; c.stroke();
  // grass tufts and flowers
  const R = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(7);
  c.strokeStyle = '#3f8a25'; c.lineWidth = 3;
  for (let i = 0; i < 70; i++) { const x = R() * W, y = 1250 + R() * 640; c.beginPath(); c.moveTo(x - 8, y); c.lineTo(x - 12, y - 16); c.moveTo(x, y); c.lineTo(x, y - 20); c.moveTo(x + 8, y); c.lineTo(x + 12, y - 15); c.stroke(); }
  const flower = (x, y, col) => { for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3; c.beginPath(); c.arc(x + Math.cos(a) * 11, y + Math.sin(a) * 11, 9, 0, 7); c.fillStyle = col; c.fill(); c.lineWidth = 2; c.strokeStyle = INK; c.stroke(); } c.beginPath(); c.arc(x, y, 7, 0, 7); c.fillStyle = '#ffd23a'; c.fill(); c.stroke(); };
  [[120, 1680, '#e8434f'], [210, 1720, '#ffd23a'], [960, 1700, '#b66ad6'], [1010, 1760, '#ffffff'], [60, 1800, '#ff8fb1'], [820, 1820, '#e8434f']].forEach(f => flower(...f));
  // birds
  c.strokeStyle = '#333'; c.lineWidth = 3;
  for (const [x, y] of [[150, 420], [205, 400], [255, 430]]) { c.beginPath(); c.moveTo(x - 14, y); c.quadraticCurveTo(x - 7, y - 9, x, y); c.quadraticCurveTo(x + 7, y - 9, x + 14, y); c.stroke(); }
  BG = b;
}
function cloud(c, x, y, s) {
  c.save(); c.translate(x, y); c.scale(s, s); c.beginPath();
  c.arc(-60, 10, 38, 0, 7); c.arc(-15, -18, 50, 0, 7); c.arc(40, -5, 42, 0, 7); c.arc(80, 15, 30, 0, 7); c.rect(-60, 10, 140, 35);
  c.fillStyle = '#fff'; c.fill(); c.restore();
}
function sun(c, t) {
  c.save(); c.translate(905, 230); c.rotate(t * .25);
  c.strokeStyle = '#f2c94c'; c.lineWidth = 7; c.lineCap = 'round';
  for (let i = 0; i < 12; i++) { c.rotate(Math.PI / 6); c.beginPath(); c.moveTo(0, -88); c.lineTo(0, -112); c.stroke(); }
  c.restore(); c.beginPath(); c.arc(905, 230, 70, 0, 7); c.fillStyle = '#f6d35b'; c.fill();
}
function drawWorld(t) {
  ctx.drawImage(BG, 0, 0); sun(ctx, t);
  cloud(ctx, ((t * 18 + 230) % 1400) - 200, 260, 1.0); cloud(ctx, ((t * 12 + 900) % 1400) - 200, 420, .7); cloud(ctx, ((t * 15 + 520) % 1400) - 200, 150, .55);
}

// ---------------- stickman ----------------
// p: {x, y (feet), kind 'cap'|'nad', dir (+1 faces right), walk (phase, NaN = stand), lift, lean,
//     armL/armR: [dx,dy] hand target relative to shoulder, eyes 'dot'|'wide'|'happy'|'tiny', mouth 'smile'|'o'|'shout'|'flat'|'grin', fright}
function limb(c, pts, w = LW) { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]); c.lineWidth = w; c.strokeStyle = INK; c.lineCap = 'round'; c.lineJoin = 'round'; c.stroke(); }
function elbow(S, Hn, bend) { const mx = (S[0] + Hn[0]) / 2, my = (S[1] + Hn[1]) / 2, dx = Hn[0] - S[0], dy = Hn[1] - S[1], d = Math.hypot(dx, dy) || 1, k = Math.max(0, 160 - d) * .45 * bend; return [mx - dy / d * k, my + dx / d * k]; }
function stick(c, p) {
  const leg = 225, torso = 200, hr = 56, col = p.kind === 'cap' ? COL.cap : COL.nad, dark = p.kind === 'cap' ? COL.capDark : COL.nad;
  c.save(); c.translate(p.x, p.y - (p.lift || 0)); if (p.rot) c.rotate(p.rot);
  // legs
  const ph = p.walk, wk = Number.isFinite(ph);
  const fL = wk ? [-14 + Math.sin(ph) * 46, -Math.max(0, Math.cos(ph)) * 22] : [-22 - (p.spread || 0), 0];
  const fR = wk ? [14 - Math.sin(ph) * 46, -Math.max(0, -Math.cos(ph)) * 22] : [22 + (p.spread || 0), 0];
  const hip = [0, -leg];
  for (const f of [fL, fR]) {
    const kx = (hip[0] + f[0]) / 2 + (wk ? 10 * p.dir : 0), ky = (hip[1] + f[1]) / 2;
    limb(c, [[hip[0] + (f === fL ? -9 : 9), hip[1]], [kx + (f === fL ? -6 : 6), ky], f]);
    c.beginPath(); c.ellipse(f[0] + 12 * p.dir, f[1] - 6, 22, 10, 0, 0, 7); c.fillStyle = dark; c.fill(); c.lineWidth = 3.5; c.strokeStyle = INK; c.stroke();
  }
  // torso (rounded capsule) with lean
  c.save(); c.translate(0, -leg); c.rotate((p.lean || 0));
  const top = -torso;
  c.beginPath(); c.roundRect(-32, top, 64, torso + 10, 30); c.fillStyle = col; c.fill(); c.lineWidth = LW; c.strokeStyle = INK; c.stroke();
  c.beginPath(); c.moveTo(-14, top + 30); c.lineTo(-14, -12); c.lineWidth = 3; c.strokeStyle = 'rgba(0,0,0,.18)'; c.stroke();
  // arms
  const SL = [-24, top + 34], SR = [24, top + 34];
  const aL = p.armL || [-30, 150], aR = p.armR || [30, 150];
  for (const [S, a, s] of [[SL, aL, -1], [SR, aR, 1]]) {
    const Hn = [S[0] + a[0], S[1] + a[1]], E = elbow(S, Hn, s * (a[2] ?? 1));
    limb(c, [S, E, Hn]);
    c.beginPath(); c.arc(Hn[0], Hn[1], 11, 0, 7); c.fillStyle = '#fff'; c.fill(); c.lineWidth = 3.5; c.strokeStyle = INK; c.stroke();
  }
  if (p.cape) p.cape(c, [SL[0] + aL[0], SL[1] + aL[1]], [SR[0] + aR[0], SR[1] + aR[1]], top);
  // head
  c.save(); c.translate(0, top - hr + 8); c.rotate(p.headRot || 0);
  if (p.kind === 'nad') {        // spiky hair behind the head
    c.beginPath(); const n = 15;
    for (let i = 0; i <= n; i++) { const a = Math.PI * (1.02 + i / n * .96), r = i % 2 ? hr + 4 : hr + 30 + (p.fright || 0) * 18; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); }
    c.closePath(); c.fillStyle = INK; c.fill();
  }
  c.beginPath(); c.arc(0, 0, hr, 0, 7); c.fillStyle = COL.skin; c.fill(); c.lineWidth = LW; c.strokeStyle = INK; c.stroke();
  const d = p.dir, ex = 18, ey = -6, look = (p.look ?? d) * 6;
  // eyes
  const eye = (x) => {
    if (p.eyes === 'happy') { c.beginPath(); c.arc(x, ey + 4, 9, Math.PI * 1.1, Math.PI * 1.9); c.lineWidth = 4; c.strokeStyle = INK; c.stroke(); return; }
    if (p.eyes === 'closed') { c.beginPath(); c.moveTo(x - 9, ey); c.lineTo(x + 9, ey); c.lineWidth = 4; c.strokeStyle = INK; c.stroke(); return; }
    const big = p.eyes === 'wide' ? 15 : 11;
    c.beginPath(); c.arc(x, ey, big, 0, 7); c.fillStyle = '#fff'; c.fill(); c.lineWidth = 2.5; c.strokeStyle = INK; c.stroke();
    c.beginPath(); c.arc(x + look * .6, ey + (p.eyes === 'wide' ? 0 : 1), p.eyes === 'wide' ? 4 : 5.5, 0, 7); c.fillStyle = INK; c.fill();
  };
  eye(-ex + d * 6); eye(ex + d * 6);
  if (p.kind === 'nad') {        // round glasses
    c.lineWidth = 3.5; c.strokeStyle = INK;
    for (const x of [-ex + d * 6, ex + d * 6]) { c.beginPath(); c.arc(x, ey, 17, 0, 7); c.stroke(); }
    c.beginPath(); c.moveTo(-1 + d * 6, ey); c.lineTo(1 + d * 6, ey); c.stroke();
  } else {                         // rosy cheeks
    c.fillStyle = 'rgba(240,120,140,.45)';
    for (const x of [-30 + d * 6, 30 + d * 6]) { c.beginPath(); c.ellipse(x, 16, 9, 6, 0, 0, 7); c.fill(); }
  }
  // mouth
  c.lineWidth = 4; c.strokeStyle = INK; const mx = d * 8, my = 26;
  if (p.mouth === 'o') { c.beginPath(); c.ellipse(mx, my, 8, 11, 0, 0, 7); c.fillStyle = '#5a1b1b'; c.fill(); c.stroke(); }
  else if (p.mouth === 'shout') { c.beginPath(); c.ellipse(mx, my + 2, 16, 15, 0, 0, 7); c.fillStyle = '#5a1b1b'; c.fill(); c.stroke(); c.beginPath(); c.ellipse(mx, my + 10, 8, 4, 0, 0, 7); c.fillStyle = '#e86b6b'; c.fill(); }
  else if (p.mouth === 'flat') { c.beginPath(); c.moveTo(mx - 12, my); c.lineTo(mx + 12, my); c.stroke(); }
  else if (p.mouth === 'grin') { c.beginPath(); c.arc(mx, my - 6, 18, .15 * Math.PI, .85 * Math.PI); c.closePath(); c.fillStyle = '#fff'; c.fill(); c.stroke(); }
  else if (p.mouth === 'worry') { c.beginPath(); c.moveTo(mx - 12, my + 4); c.quadraticCurveTo(mx - 4, my - 4, mx, my + 2); c.quadraticCurveTo(mx + 6, my + 8, mx + 12, my); c.stroke(); }
  else { c.beginPath(); c.arc(mx, my - 8, 14, .2 * Math.PI, .8 * Math.PI); c.stroke(); }
  if (p.kind === 'cap') {          // red baseball cap, brim towards the facing side
    c.save(); c.translate(0, -(p.capPop || 0)); c.rotate(-(p.capPop || 0) * .004 * d);
    c.beginPath(); c.arc(0, -16, hr + 2, Math.PI * 1.05, Math.PI * 1.95); c.closePath(); c.fillStyle = COL.cap; c.fill(); c.lineWidth = LW; c.strokeStyle = INK; c.stroke();
    c.beginPath(); c.ellipse(d * 62, -20, 40, 10, 0, 0, 7); c.fillStyle = COL.cap; c.fill(); c.stroke();
    c.beginPath(); c.arc(0, -16 - hr + 2, 6, 0, 7); c.fillStyle = COL.capDark; c.fill(); c.stroke();
    c.beginPath(); c.arc(0, -16, hr - 18, Math.PI * 1.25, Math.PI * 1.75); c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,.55)'; c.stroke();
    c.restore();
  }
  if (p.sweat) { c.save(); c.globalAlpha = p.sweat; c.beginPath(); c.moveTo(-d * 58, -40); c.quadraticCurveTo(-d * 70, -18, -d * 58, -12); c.quadraticCurveTo(-d * 46, -18, -d * 58, -40); c.fillStyle = '#7fd0ff'; c.fill(); c.lineWidth = 2.5; c.strokeStyle = INK; c.stroke(); c.restore(); }
  c.restore(); c.restore(); c.restore();
}
function shoulderY(feetY) { return feetY - 225 - 200 + 30; }

// ---------------- mountain lion ----------------
// q: {x, y (paws), dir (-1 faces left), mode 'crouch'|'growl'|'scared'|'run', t, ph}
function puma(c, q) {
  const s = q.s || 1.38; c.save(); c.translate(q.x, q.y); c.scale(q.dir * -s, s);   // drawn facing left
  const tan = '#d6a159', light = '#f0d2a0', dk = '#8c5d2a';
  const run = q.mode === 'run', scared = q.mode === 'scared', crouch = q.mode === 'crouch' || q.mode === 'growl';
  const bodyY = crouch ? -120 : -150, ph = q.ph || 0;
  // tail
  c.beginPath(); c.moveTo(120, bodyY - 10);
  if (scared) c.bezierCurveTo(190, bodyY + 40, 170, bodyY + 90, 120, bodyY + 70);
  else c.bezierCurveTo(210, bodyY - 40, 230, bodyY - 140 + Math.sin(q.t * 6) * 15, 200, bodyY - 150 + Math.sin(q.t * 6) * 15);
  c.lineWidth = 22; c.strokeStyle = INK; c.lineCap = 'round'; c.stroke(); c.lineWidth = 15; c.strokeStyle = tan; c.stroke();
  // legs
  const legs = [[-85, 0], [-55, 1.5], [75, 3], [105, 4.5]];
  for (const [lx, o] of legs) {
    const sw = run ? Math.sin(ph + o) * 45 : 0, hgt = -bodyY - 10;
    c.beginPath(); c.moveTo(lx, bodyY + 30); c.lineTo(lx + sw * .4, bodyY + 30 + hgt * .55); c.lineTo(lx + sw, -4);
    c.lineWidth = 30; c.strokeStyle = INK; c.lineCap = 'round'; c.stroke(); c.lineWidth = 22; c.strokeStyle = tan; c.stroke();
    c.beginPath(); c.ellipse(lx + sw - 6, -6, 20, 11, 0, 0, 7); c.fillStyle = light; c.fill(); c.lineWidth = 4; c.strokeStyle = INK; c.stroke();
  }
  // body
  c.beginPath(); c.ellipse(15, bodyY, 140, crouch ? 58 : 64, crouch ? .06 : 0, 0, 7); c.fillStyle = tan; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.beginPath(); c.ellipse(5, bodyY + 30, 95, 24, 0, 0, Math.PI); c.fillStyle = light; c.fill();
  // head
  const hx = -150, hy = bodyY - (crouch ? 30 : 60);
  c.save(); c.translate(hx, hy); if (q.mode === 'growl') c.rotate(-.08 + Math.sin(q.t * 40) * .02);
  for (const ex of [-38, 30]) {    // ears
    c.save(); c.translate(ex, -58); c.rotate(scared ? (ex < 0 ? -1.1 : 1.1) : 0);
    c.beginPath(); c.moveTo(-22, 10); c.lineTo(0, -30); c.lineTo(22, 10); c.closePath(); c.fillStyle = tan; c.fill(); c.lineWidth = 5; c.strokeStyle = INK; c.stroke();
    c.beginPath(); c.moveTo(-10, 4); c.lineTo(0, -16); c.lineTo(10, 4); c.closePath(); c.fillStyle = '#e8a0a0'; c.fill(); c.restore();
  }
  c.beginPath(); c.arc(0, 0, 70, 0, 7); c.fillStyle = tan; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.beginPath(); c.ellipse(-22, 30, 40, 30, 0, 0, 7); c.fillStyle = light; c.fill();
  // eyes
  const eyeR = scared ? 6 : 13;
  for (const ex of [-34, 8]) {
    c.beginPath(); c.ellipse(ex, -14, 15, crouch ? 9 : 15, crouch ? (ex < 0 ? .35 : -.35) : 0, 0, 7); c.fillStyle = scared ? '#fff' : '#f3e06b'; c.fill(); c.lineWidth = 3.5; c.strokeStyle = INK; c.stroke();
    c.beginPath(); c.ellipse(ex - 3, -14, scared ? eyeR * .5 : 4, scared ? eyeR * .5 : (crouch ? 7 : 11), 0, 0, 7); c.fillStyle = INK; c.fill();
  }
  if (crouch) { c.lineWidth = 6; c.beginPath(); c.moveTo(-56, -40); c.lineTo(-22, -28); c.moveTo(-6, -28); c.lineTo(24, -40); c.stroke(); }
  // nose + mouth
  c.beginPath(); c.moveTo(-40, 14); c.lineTo(-24, 14); c.lineTo(-32, 24); c.closePath(); c.fillStyle = '#8b4a4a'; c.fill(); c.stroke();
  if (q.mode === 'growl') {
    c.beginPath(); c.ellipse(-30, 50, 28, 22, 0, 0, 7); c.fillStyle = '#5a1b1b'; c.fill(); c.lineWidth = 4; c.stroke();
    c.fillStyle = '#fff'; for (const tx of [-46, -14]) { c.beginPath(); c.moveTo(tx - 6, 32); c.lineTo(tx, 48); c.lineTo(tx + 6, 32); c.closePath(); c.fill(); c.stroke(); }
  } else if (scared) { c.beginPath(); c.moveTo(-50, 50); for (let i = 0; i < 5; i++) c.lineTo(-44 + i * 8, i % 2 ? 44 : 52); c.lineWidth = 3.5; c.stroke(); }
  else { c.beginPath(); c.moveTo(-32, 24); c.quadraticCurveTo(-40, 40, -50, 34); c.moveTo(-32, 24); c.quadraticCurveTo(-24, 40, -14, 34); c.lineWidth = 3.5; c.stroke(); }
  c.lineWidth = 2.5; for (const [y, k] of [[22, -1], [32, -1]]) { c.beginPath(); c.moveTo(-60, y); c.lineTo(-95, y + k * 6); c.stroke(); }
  if (q.sweat) { c.globalAlpha = q.sweat; c.beginPath(); c.moveTo(48, -50); c.quadraticCurveTo(60, -28, 48, -22); c.quadraticCurveTo(36, -28, 48, -50); c.fillStyle = '#7fd0ff'; c.fill(); c.lineWidth = 2.5; c.stroke(); c.globalAlpha = 1; }
  c.restore(); c.restore();
}

// red jacket held wide above the head: one giant silhouette from Cap's hands down to Nadara's hips
function coat(c, nad, cap) {
  const top = cap.y - 225 - 200 + 34;                 // Cap's shoulder line
  const hl = [cap.x - 24 + cap.armL[0], top + cap.armL[1]], hr = [cap.x + 24 + cap.armR[0], top + cap.armR[1]];
  const hipY = nad.y - 225 + 20;
  c.save(); c.globalAlpha = cap.coat; c.translate(nad.x, nad.y); c.rotate(nad.rot || 0); c.translate(-nad.x, -nad.y);
  c.beginPath(); c.moveTo(hl[0], hl[1]);
  c.quadraticCurveTo(hl[0] - 40, (hl[1] + hipY) / 2, nad.x - 150, hipY);
  for (let i = 1; i <= 6; i++) c.lineTo(nad.x - 150 + i * 50, hipY + (i % 2 ? 26 : 0));
  c.quadraticCurveTo(hr[0] + 40, (hr[1] + hipY) / 2, hr[0], hr[1]);
  c.quadraticCurveTo(cap.x, top - 120, hl[0], hl[1]); c.closePath();
  c.fillStyle = '#c42a33'; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.lineWidth = 3; c.strokeStyle = 'rgba(0,0,0,.28)';
  for (const k of [-.5, 0, .5]) { c.beginPath(); c.moveTo(cap.x + k * 120, top - 40); c.lineTo(nad.x + k * 220, hipY); c.stroke(); }
  c.restore();
}

// ---------------- props & effects ----------------
function bush(c, x, y, shake) {
  c.save(); c.translate(x + Math.sin(shake * 50) * 10 * (shake > 0 ? 1 : 0), y);
  c.beginPath(); c.arc(-90, -60, 70, 0, 7); c.arc(0, -100, 90, 0, 7); c.arc(95, -60, 75, 0, 7); c.rect(-150, -60, 300, 60);
  c.fillStyle = '#4fae35'; c.fill(); c.lineWidth = 5; c.strokeStyle = '#2f7a1f'; c.stroke();
  c.fillStyle = '#6cc94b'; c.beginPath(); c.arc(-30, -130, 30, 0, 7); c.arc(70, -90, 22, 0, 7); c.fill();
  c.restore();
}
function text(c, s, x, y, size, color, font = 'AlmaraiXB', outline = INK, ow = 10) {
  c.save(); c.font = `${size}px ${font}`; c.textAlign = 'center'; c.direction = 'rtl'; c.lineJoin = 'round';
  if (outline) { c.lineWidth = ow; c.strokeStyle = outline; c.strokeText(s, x, y); }
  c.fillStyle = color; c.fillText(s, x, y); c.restore();
}
function pop(c, s, x, y, a, size = 90, col = '#ffd23a') { if (a <= 0) return; c.save(); c.translate(x, y); const k = back(clamp(a)); c.scale(k, k); text(c, s, 0, 0, size, col, 'AlmaraiXB', INK, 12); c.restore(); }
function bubble(c, x, y, w, h, a, inner) {
  if (a <= 0) return; c.save(); c.globalAlpha = clamp(a * 2); c.translate(x, y); const k = eout(clamp(a)); c.scale(k, k);
  for (const [dx, dy, r] of [[150, h / 2 + 50, 14], [175, h / 2 + 85, 9]]) { c.beginPath(); c.arc(dx, dy, r, 0, 7); c.fillStyle = '#fff'; c.fill(); c.lineWidth = 4; c.strokeStyle = INK; c.stroke(); }
  c.beginPath(); c.ellipse(0, 0, w / 2, h / 2, 0, 0, 7); c.fillStyle = '#fff'; c.fill(); c.lineWidth = 5; c.strokeStyle = INK; c.stroke();
  inner(c); c.restore();
}
function bulb(c, x, y, a) {
  if (a <= 0) return; c.save(); c.translate(x, y); const k = back(clamp(a)); c.scale(k, k);
  c.strokeStyle = '#f2b705'; c.lineWidth = 6; c.lineCap = 'round';
  for (let i = 0; i < 8; i++) { const an = i * Math.PI / 4; c.beginPath(); c.moveTo(Math.cos(an) * 62, Math.sin(an) * 62 - 10); c.lineTo(Math.cos(an) * 84, Math.sin(an) * 84 - 10); c.stroke(); }
  c.beginPath(); c.arc(0, -10, 42, 0, 7); c.fillStyle = '#ffe14d'; c.fill(); c.lineWidth = 5; c.strokeStyle = INK; c.stroke();
  c.fillStyle = '#9a9a9a'; c.fillRect(-18, 28, 36, 26); c.strokeRect(-18, 28, 36, 26); c.restore();
}
function speedLines(c, x, y, a, dir = 1) { if (a <= 0) return; c.save(); c.globalAlpha = a; c.strokeStyle = INK; c.lineWidth = 5; c.lineCap = 'round'; for (const dy of [-90, -40, 10]) { c.beginPath(); c.moveTo(x, y + dy); c.lineTo(x - dir * 90, y + dy); c.stroke(); } c.restore(); }
function dust(c, x, y, a) { if (a <= 0) return; c.save(); c.globalAlpha = (1 - a) * .9; for (let i = 0; i < 5; i++) { c.beginPath(); c.arc(x - i * 40 * a - 20, y - 20 - (i % 2) * 20, 22 + a * 30, 0, 7); c.fillStyle = '#e9dcc2'; c.fill(); c.lineWidth = 3; c.strokeStyle = '#b9a98a'; c.stroke(); } c.restore(); }
function roarLines(c, x, y, a, t) { if (a <= 0) return; c.save(); c.strokeStyle = INK; c.lineWidth = 6; c.lineCap = 'round'; c.globalAlpha = a; for (let i = 0; i < 3; i++) { const r = 60 + i * 40 + (t * 160 % 40); c.beginPath(); c.arc(x, y, r, Math.PI * .8, Math.PI * 1.2); c.stroke(); } c.restore(); }
function shoutLines(c, x, y, a, t) { if (a <= 0) return; c.save(); c.strokeStyle = INK; c.lineWidth = 6; c.lineCap = 'round'; c.globalAlpha = a; for (let i = 0; i < 3; i++) { const r = 70 + i * 40 + (t * 160 % 40); c.beginPath(); c.arc(x, y, r, -Math.PI * .22, Math.PI * .22); c.stroke(); } c.restore(); }
function sparkle(c, x, y, a) { if (a <= 0 || a >= 1) return; c.save(); c.translate(x, y); c.globalAlpha = 1 - a; c.scale(.6 + a, .6 + a); c.fillStyle = '#ffd23a'; c.strokeStyle = INK; c.lineWidth = 4; c.beginPath(); for (let i = 0; i < 10; i++) { const an = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 22 : 60; c.lineTo(Math.cos(an) * r, Math.sin(an) * r); } c.closePath(); c.fill(); c.stroke(); c.restore(); }
function credit(c) { c.save(); c.font = '600 26px PlexSerifB'; c.direction = 'ltr'; c.textAlign = 'right'; c.fillStyle = 'rgba(255,255,255,.92)'; c.shadowColor = 'rgba(0,0,0,.5)'; c.shadowBlur = 4; c.fillText('© Mahmoud Elkosif', 1050, 1890); c.restore(); }

// ---------------- story ----------------
function scene(t) {
  // positions
  const walkA = seg(t, 0, 3.0);
  let nad = { kind: 'nad', x: lerp(-300, 270, eout(walkA)), y: GROUND, dir: 1, eyes: 'dot', mouth: 'smile' };
  let cap = { kind: 'cap', x: lerp(-100, 480, eout(walkA)), y: GROUND, dir: 1, eyes: 'dot', mouth: 'grin' };
  if (t < 3.0) { nad.walk = t * 9; cap.walk = t * 9 + 1.6; cap.armR = [40, 140]; }
  // the bush rustles, both turn to look
  const rustle = t > 3.2 && t < 4.4 ? 1 : 0;
  if (t >= 3.0 && t < 4.4) { nad.mouth = 'flat'; cap.mouth = 'flat'; nad.headRot = .08; cap.headRot = .08; }
  // lion reveal + fright
  const fr = seg(t, 4.5, 4.75), frDown = seg(t, 4.75, 5.1);
  if (t >= 4.5) { nad.eyes = cap.eyes = 'wide'; nad.mouth = cap.mouth = 'o'; nad.fright = 1; cap.capPop = 50 * Math.sin(Math.PI * clamp((t - 4.5) / .6)); }
  if (t >= 4.5 && t < 5.1) { const j = Math.sin(Math.PI * seg(t, 4.5, 5.1)) * 70; nad.lift = j; cap.lift = j * .9; nad.armL = [-80, -120]; nad.armR = [80, -120]; cap.armL = [-80, -130]; cap.armR = [80, -130]; }
  if (t >= 5.1 && t < 7.2) { nad.armL = [-75, -15]; nad.armR = [75, -15]; cap.armL = [-75, -15]; cap.armR = [75, -15]; nad.lean = -.06 + Math.sin(t * 50) * .02; cap.lean = -.05 + Math.sin(t * 47) * .02; }
  // Nadara tries to run, Cap grabs him
  if (t >= 7.2 && t < 10.8) {
    nad.dir = -1; nad.x = 270 - 50 * eout(seg(t, 7.2, 7.6)); nad.walk = t * 26; nad.lean = .18; nad.armL = [-60, 40]; nad.armR = [60, 60]; nad.mouth = 'shout'; nad.eyes = 'wide'; nad.look = -1;
    cap.armL = [-(cap.x - nad.x) + 40, 20, -1]; cap.mouth = 'flat'; cap.eyes = 'dot'; cap.headRot = Math.sin(t * 18) * .18 * (t < 8.4 ? 1 : 0); cap.look = -1;
    if (t > 8.4) { nad.walk = NaN; nad.dir = 1; nad.lean = 0; nad.mouth = 'worry'; nad.look = 1; nad.armL = [-30, 150]; nad.armR = [30, 150]; }
  }
  if (t >= 9.6 && t < 10.8) { cap.eyes = 'dot'; cap.mouth = 'grin'; cap.armL = [-30, 150]; cap.armR = [70, -160]; }
  // Cap jumps onto Nadara's shoulders
  const NX = 280;
  if (t >= 10.8) { nad.x = lerp(220, NX, seg(t, 10.8, 11.4)); nad.walk = NaN; nad.dir = 1; nad.lean = 0; nad.eyes = 'wide'; nad.mouth = 'o'; }
  const jump = seg(t, 10.9, 11.7);
  if (t >= 10.8) {
    const sy = shoulderY(GROUND) + 2, j = eio(jump);
    cap.x = lerp(480, NX, j); cap.y = lerp(GROUND, sy, j) - Math.sin(Math.PI * j) * 260; cap.walk = NaN; cap.eyes = 'happy'; cap.mouth = 'grin';
    cap.armL = [-70, -60]; cap.armR = [70, -60];
    if (t < 11.7) { nad.armL = [-40, 140]; nad.armR = [40, 140]; }
  }
  // giant pose: arms wide up, jacket spread, both shout
  const giant = seg(t, 11.9, 12.4);
  if (t >= 11.9 && t < 16.8) {
    const sway = Math.sin(t * 5) * .035, sh = Math.sin(t * 60) * 4;
    nad.armL = [-30, -100]; nad.armR = [30, -100];        // holds Cap's ankles
    nad.mouth = 'shout'; nad.eyes = 'wide'; nad.rot = sway; cap.rot = sway * 1.6;
    cap.x = NX + sway * 420; cap.eyes = 'dot'; cap.mouth = 'shout';
    const up = eout(giant); cap.armL = [lerp(-70, -190, up), lerp(-60, -150, up) + sh]; cap.armR = [lerp(70, 190, up), lerp(-60, -150, up) - sh];
    cap.coat = up;     // the jacket is drawn behind both of them in renderFrame
  }
  // after the lion flees: wobble, hop down, high five
  if (t >= 16.8 && t < 17.8) {
    const w = Math.sin((t - 16.8) * 14) * .12 * (1 - seg(t, 16.8, 17.8));
    nad.rot = w; cap.rot = w * 1.4; cap.x = NX + w * 600; nad.eyes = 'wide'; nad.mouth = 'worry'; cap.eyes = 'wide'; cap.mouth = 'o';
    cap.armL = [-120, -40]; cap.armR = [120, -40]; nad.armL = [-30, -100]; nad.armR = [30, -100];
  }
  const hop = seg(t, 17.8, 18.4);
  if (t >= 17.8) {
    const j = eio(hop); cap.x = lerp(NX, 520, j); cap.y = lerp(shoulderY(GROUND) + 2, GROUND, j) - Math.sin(Math.PI * j) * 160; cap.rot = 0; nad.rot = 0;
    cap.eyes = 'happy'; cap.mouth = 'grin'; nad.eyes = 'dot'; nad.mouth = 'smile'; nad.armL = [-30, 150]; nad.armR = [30, 150]; cap.armL = [-40, 140]; cap.armR = [40, 140];
  }
  if (t >= 18.5) {    // high five over the middle
    const k = eout(seg(t, 18.5, 18.9)) * (1 - eout(seg(t, 19.6, 20.0)));
    nad.armR = [lerp(30, 120, k), lerp(150, -130, k)]; cap.armL = [lerp(-40, -120, k), lerp(140, -130, k)];
    nad.eyes = cap.eyes = 'happy'; nad.mouth = cap.mouth = 'grin';
  }
  if (t >= 20.0) { nad.eyes = (t % 3.1 < .12) ? 'closed' : 'dot'; cap.eyes = (t % 2.7 < .12) ? 'closed' : 'dot'; cap.armR = [60, -150]; }   // Cap: thumbs-up pose
  return { nad, cap };
}
function lion(t) {
  if (t < 4.45) return null;
  const leap = seg(t, 4.45, 4.85);
  let q = { x: lerp(1150, 880, eout(leap)), y: GROUND + 10 - Math.sin(Math.PI * leap) * 120, dir: -1, mode: 'growl', t };
  if (t > 4.85 && t < 7.2) q.mode = 'growl';
  if (t >= 7.2 && t < 12.2) { q.mode = 'crouch'; q.x = 880 - 30 * eio(seg(t, 7.2, 10.5)); }
  if (t >= 12.2) { q.mode = 'scared'; q.x = 850 + 80 * eio(seg(t, 13.2, 14.6)); q.sweat = seg(t, 12.8, 13.1); q.y = GROUND + 10 + Math.sin(t * 60) * 3 * (t < 15 ? 1 : 0); }
  if (t >= 15.0) { q.mode = 'run'; q.dir = 1; q.ph = t * 30; q.x = 930 + 1500 * Math.pow(seg(t, 15.1, 16.4), 1.6); q.y = GROUND + 10; }
  return q;
}

function camera(t) {   // punch-ins on the reveal and on the giant moment
  const z1 = Math.sin(Math.PI * seg(t, 4.5, 7.2)) * .14, z2 = Math.sin(Math.PI * seg(t, 12.0, 15.0)) * .08;
  if (z1 > 0) return { s: 1 + z1, cx: 700, cy: 1300 };
  if (z2 > 0) return { s: 1 + z2, cx: 560, cy: 1100 };
  return { s: 1, cx: 540, cy: 960 };
}

function endCard(t, a) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a;
  const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#9fd3ea'); g.addColorStop(.62, '#bfe3f2'); g.addColorStop(1, '#2b3c4f');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalAlpha = a * .5; ctx.fillStyle = '#5b6b86';
  ctx.beginPath(); ctx.moveTo(0, 1920); ctx.lineTo(260, 1650); ctx.lineTo(520, 1920); ctx.moveTo(560, 1920); ctx.lineTo(860, 1610); ctx.lineTo(1160, 1920); ctx.fill(); ctx.restore();
  sun(ctx, t); ctx.save(); ctx.translate(905, 0); ctx.restore();
  cloud(ctx, 840, 1330, .9); cloud(ctx, 260, 560, .6); cloud(ctx, 1000, 300, .5);
  const bob = Math.sin(t * 3) * 10;
  cloud(ctx, 520, 1420 + bob, 2.2);
  const k = eout(seg(t, 23.4, 24.0));
  stick(ctx, { kind: 'nad', x: 420, y: 1380 + bob, dir: 1, eyes: 'dot', mouth: 'flat', armL: [-30, 150], armR: [30, 150], lift: (1 - k) * 40 });
  stick(ctx, { kind: 'cap', x: 640, y: 1380 + bob, dir: -1, eyes: 'dot', mouth: 'o', armL: [-140, -70], armR: [40, 140], lift: (1 - k) * 40 });
  const ta = seg(t, 24.0, 24.6);
  ctx.save(); ctx.globalAlpha = a * ta; ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 10;
  ctx.font = '62px PlexSerifB'; ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff';
  const s1 = 'Mahmoud Elkosif', s2 = 'مونتاج وإخراج';
  ctx.font = '60px PlexSerifB'; const w1 = ctx.measureText(s1).width; ctx.font = '62px AmiriB'; const w2 = ctx.measureText(s2).width;
  const x0 = 540 - (w1 + w2 + 18) / 2;
  ctx.font = '62px AmiriB'; ctx.direction = 'rtl'; ctx.textAlign = 'right'; ctx.fillText(s2, x0 + w2, 1700);
  ctx.direction = 'ltr'; ctx.textAlign = 'left'; ctx.font = '60px PlexSerifB'; ctx.fillText(s1, x0 + w2 + 18, 1700);
  ctx.direction = 'rtl'; ctx.textAlign = 'center'; ctx.font = '54px AmiriB'; ctx.fillStyle = '#f7d046'; ctx.fillText('تابعني على فيسبوك', 540, 1790);
  ctx.restore(); ctx.restore();
}

window.renderFrame = async function (fr) {
  const t = fr / FPS;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  const cam = camera(t);
  ctx.save(); ctx.translate(cam.cx, cam.cy); ctx.scale(cam.s, cam.s); ctx.translate(-cam.cx, -cam.cy);
  drawWorld(t);
  const { nad, cap } = scene(t), q = lion(t);
  // bush (lion hides behind it until the leap)
  const shake = t > 3.2 && t < 4.5 ? (t - 3.2) : 0;
  if (q && t < 4.85) { puma(ctx, q); bush(ctx, 960, GROUND + 40, shake); } else { bush(ctx, 960, GROUND + 40, shake); }
  if (t > 3.3 && t < 4.4) { pop(ctx, '؟', nad.x, 900, seg(t, 3.4, 3.6), 110); pop(ctx, '؟', cap.x + 20, 900, seg(t, 3.55, 3.75), 110); }
  if (cap.coat > 0) coat(ctx, nad, cap);
  stick(ctx, nad); stick(ctx, cap);
  if (q && t >= 4.85) puma(ctx, q);
  if (q && q.mode === 'growl') roarLines(ctx, q.x - 250, q.y - 130, seg(t, 4.9, 5.1) * (1 - seg(t, 6.9, 7.2)), t);
  if (t > 4.6 && t < 7.0) pop(ctx, '!!', 380, 840, seg(t, 4.6, 4.8), 130, '#ff4a4a');
  // Cap's thought: running = getting chased
  bubble(ctx, 690, 640, 420, 260, seg(t, 7.8, 8.15) * (1 - seg(t, 9.4, 9.6)), c => {
    c.save(); c.scale(.42, .42); c.translate(-120, 230);
    stick(c, { kind: 'nad', x: -120, y: 0, dir: -1, walk: t * 30, lean: .2, eyes: 'wide', mouth: 'shout', armL: [-60, 40], armR: [60, 60] });
    puma(c, { x: 330, y: 0, dir: -1, mode: 'run', t, ph: t * 30, s: 1.05 }); c.restore();
    c.save(); c.globalAlpha = seg(t, 8.5, 8.7); c.strokeStyle = '#e8262f'; c.lineWidth = 16; c.lineCap = 'round';
    c.beginPath(); c.moveTo(-130, -90); c.lineTo(130, 90); c.moveTo(130, -90); c.lineTo(-130, 90); c.stroke(); c.restore();
  });
  bulb(ctx, cap.x + 10, 760, seg(t, 9.7, 10.0) * (1 - seg(t, 10.7, 10.9)));
  if (t >= 12.2 && t < 15.2) { shoutLines(ctx, cap.x + 110, 560, seg(t, 12.2, 12.4), t); pop(ctx, '!!!', cap.x + 40, 420, seg(t, 12.3, 12.5), 140, '#ff4a4a'); }
  if (t >= 15.0 && t < 16.6) { speedLines(ctx, q.x - 230, q.y - 140, 1 - seg(t, 16.2, 16.6), 1); dust(ctx, q.x - 200, q.y, seg(t, 15.0, 16.0)); }
  sparkle(ctx, 395, 1080, seg(t, 18.85, 19.5));
  ctx.restore();
  // on-screen words: the hook and the tip
  const hook = seg(t, .3, .7) * (1 - seg(t, 2.6, 3.0));
  if (hook > 0) { ctx.save(); ctx.globalAlpha = hook; text(ctx, 'لو أسد الجبل طلعلك…', 540, 470, 84, '#ffffff'); text(ctx, 'تعمل إيه؟', 540, 580, 96, '#ffd23a'); ctx.restore(); }
  const tip = seg(t, 20.0, 20.4) * (1 - seg(t, 22.9, 23.2));
  if (tip > 0) {
    ctx.save(); ctx.globalAlpha = tip; const k = back(clamp(seg(t, 20.0, 20.4))); ctx.translate(540, 470); ctx.scale(k, k);
    text(ctx, 'ماتجريش… وكبّر حجمك', 0, 0, 86, '#ffffff'); text(ctx, 'وقول بصوت عالي!', 0, 110, 82, '#ffd23a'); ctx.restore();
  }
  endCard(t, seg(t, 23.0, 23.5));
  credit(ctx);
  return true;
};

(async () => {
  buildBG();
  window.FRAMES = Math.round(DUR * FPS);
  await Promise.all(['AmiriB', 'AlmaraiXB', 'PlexSerifB'].map(f => document.fonts.load(`60px ${f}`, 'أبج ABC')));
  await document.fonts.ready; window.ready = true;
})();
