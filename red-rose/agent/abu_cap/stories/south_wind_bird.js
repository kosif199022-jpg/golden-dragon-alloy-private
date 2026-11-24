// «كبّر نفسك»: Cap and Nadara meet a mountain lion. Same flat stickman look as the Abu Cap reels (@elkosif1),
// drawn entirely in code. 1080x1920, 30 fps, seekable: window.renderFrame(frame).
const W = 1080, H = 1920, FPS = 30, DUR = 38.0;
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
  if (p.kind === 'cap' && !p.noCap) {          // red baseball cap, brim towards the facing side
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

// ===================== «طائر الريح الجنوبي»: Cap & Nadara rescue the South Wind Bird. No text on screen. =====================
const mix = (a, b, k) => { const pa = a.match(/\w\w/g).map(h => parseInt(h, 16)), pb = b.match(/\w\w/g).map(h => parseInt(h, 16)); return '#' + pa.map((v, i) => Math.round(v + (pb[i] - v) * k).toString(16).padStart(2, '0')).join(''); };
const CLIFF = 1310;            // feet line on the hill top
// storm amount over the film (0 calm .. 1 full storm)
const storm = t => clamp(seg(t, 1.5, 4.5) - seg(t, 21.5, 24.5));
// ---------- the bird ----------
function bird(c, x, y, s, wing, rot = 0, o = {}) {
  c.save(); c.translate(x, y); c.rotate(rot); c.scale(s * (o.flip ? -1 : 1), s);
  if (o.glow) { const g = c.createRadialGradient(0, 0, 10, 0, 0, 220); g.addColorStop(0, `rgba(255,230,150,${.55 * o.glow})`); g.addColorStop(1, 'rgba(255,230,150,0)'); c.fillStyle = g; c.fillRect(-220, -220, 440, 440); }
  // tail: three long curling feathers
  for (const [k, col] of [[-1, '#2bb5b0'], [0, '#f2c14e'], [1, '#2bb5b0']]) {
    c.beginPath(); c.moveTo(-50, 8); c.bezierCurveTo(-120, 20 + k * 30, -170, -10 + k * 60 + Math.sin(wing * 6 + k) * 10, -215, 30 + k * 40);
    c.lineWidth = 16; c.strokeStyle = INK; c.lineCap = 'round'; c.stroke(); c.lineWidth = 10; c.strokeStyle = col; c.stroke();
    c.beginPath(); c.arc(-215, 30 + k * 40, 12, 0, 7); c.fillStyle = col; c.fill(); c.lineWidth = 4; c.strokeStyle = INK; c.stroke();
  }
  const wa = o.hurt ? -.2 : Math.sin(wing) * .9;          // wing angle
  const wingShape = (flipY) => { c.save(); c.translate(-5, -10); c.rotate(-wa * flipY - .2); c.beginPath(); c.moveTo(0, 0); c.bezierCurveTo(-30, -90, -100, -130, -150, -110); c.bezierCurveTo(-110, -80, -90, -40, -40, 10); c.closePath(); c.fillStyle = flipY > 0 ? '#e6fbf7' : '#bfeee8'; c.fill(); c.lineWidth = 5; c.strokeStyle = INK; c.stroke();
    c.lineWidth = 3; for (let k = 0; k < 3; k++) { c.beginPath(); c.moveTo(-50 - k * 25, -60 - k * 10); c.lineTo(-30 - k * 25, -20 - k * 8); c.stroke(); } c.restore(); };
  wingShape(-1);
  c.beginPath(); c.ellipse(0, 0, 70, 46, -.1, 0, 7); c.fillStyle = '#f3fffd'; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.beginPath(); c.ellipse(10, 14, 44, 22, 0, 0, Math.PI); c.fillStyle = '#ffe3a3'; c.fill();
  // head, crest, beak, eye
  c.beginPath(); c.arc(62, -34, 34, 0, 7); c.fillStyle = '#f3fffd'; c.fill(); c.stroke();
  for (const [dx, h, col] of [[46, 48, '#f2c14e'], [60, 58, '#2bb5b0'], [74, 44, '#f2c14e']]) { c.beginPath(); c.moveTo(dx - 7, -62); c.quadraticCurveTo(dx - 14, -62 - h, dx + 6, -62 - h * .8); c.quadraticCurveTo(dx + 2, -70, dx + 7, -62); c.fillStyle = col; c.fill(); c.lineWidth = 4; c.stroke(); }
  c.beginPath(); c.moveTo(92, -38); c.lineTo(126, -28); c.lineTo(92, -20); c.closePath(); c.fillStyle = '#f39a2c'; c.fill(); c.lineWidth = 4; c.stroke();
  if (o.eyes === 'closed' || o.hurt) { c.beginPath(); c.moveTo(66, -40); c.quadraticCurveTo(74, -34, 82, -40); c.lineWidth = 4; c.stroke(); }
  else { c.beginPath(); c.arc(74, -40, 9, 0, 7); c.fillStyle = '#fff'; c.fill(); c.lineWidth = 3; c.stroke(); c.beginPath(); c.arc(76, -40, 4.5, 0, 7); c.fillStyle = INK; c.fill(); }
  if (o.hurt) { c.save(); c.translate(-10, -30); c.rotate(.5); c.fillStyle = '#fff'; c.fillRect(-26, -9, 52, 18); c.strokeStyle = '#d33'; c.lineWidth = 4; c.strokeRect(-26, -9, 52, 18); c.beginPath(); c.moveTo(-8, 0); c.lineTo(8, 0); c.moveTo(0, -6); c.lineTo(0, 6); c.stroke(); c.restore(); }
  wingShape(1);
  // feet
  c.strokeStyle = '#f39a2c'; c.lineWidth = 5; for (const fx of [-10, 15]) { c.beginPath(); c.moveTo(fx, 40); c.lineTo(fx - 4, 62); c.stroke(); }
  c.restore();
}
// ---------- weather ----------
function stormSky(t, k) {
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k * .82;
  const g = ctx.createLinearGradient(0, 0, 0, 1400); g.addColorStop(0, '#1e2134'); g.addColorStop(1, '#4b4c68'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, 1250); ctx.restore();
  ctx.save(); ctx.globalAlpha = k;
  for (let i = 0; i < 6; i++) { ctx.save(); ctx.filter = 'brightness(.45)'; cloud(ctx, ((t * (120 + i * 40) + i * 260) % 1600) - 300, 120 + i * 95, 1.1 + (i % 3) * .3); ctx.restore(); }
  ctx.restore();
}
function rain(t, k) {
  if (k <= 0) return; ctx.save(); ctx.globalAlpha = .5 * k; ctx.strokeStyle = '#cfdcf0'; ctx.lineWidth = 2.5;
  for (let i = 0; i < 170; i++) { const r = (i * 7919 % 1000) / 1000, q = (i * 104729 % 1000) / 1000; const x = ((r * 1400 + t * 700) % 1400) - 160, y = ((q * 2100 + t * 2300) % 2100) - 100; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 26, y + 60); ctx.stroke(); }
  ctx.restore();
}
function windLines(t, k, y0 = 300, y1 = 1500) {
  if (k <= 0) return; ctx.save(); ctx.globalAlpha = .55 * k; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 5; ctx.lineCap = 'round';
  for (let i = 0; i < 12; i++) { const r = (i * 7919 % 1000) / 1000, y = y0 + r * (y1 - y0), x = ((t * 1500 + i * 400) % 1900) - 400;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.bezierCurveTo(x + 120, y - 20, x + 220, y + 25, x + 330, y); ctx.stroke(); }
  ctx.restore();
}
function lightning(t, at) {
  const p = seg(t, at, at + .25); if (p <= 0 || p >= 1) return;
  ctx.save(); ctx.globalAlpha = (1 - p) * .85; ctx.fillStyle = '#eef3ff'; ctx.fillRect(0, 0, W, H); ctx.restore();
  ctx.save(); ctx.globalAlpha = 1 - p; ctx.strokeStyle = '#fffbe0'; ctx.lineWidth = 9; ctx.shadowColor = '#fff7b0'; ctx.shadowBlur = 30;
  ctx.beginPath(); let x = 760, y = 0; ctx.moveTo(x, y); let s0 = Math.round(at * 100) >>> 0; const R = () => (s0 = (s0 * 1664525 + 1013904223) >>> 0) / 4294967296; while (y < 900) { x += (R() - .5) * 120; y += 60 + R() * 60; ctx.lineTo(x, y); } ctx.stroke(); ctx.restore();
}
function tornado(x, ground, h, t, a, w = 1) {
  if (a <= 0) return; ctx.save(); ctx.globalAlpha = a;
  for (let i = 0; i < 14; i++) {
    const k = i / 13, y = ground - k * h, rx = (24 + k * k * 260) * w, sw = Math.sin(t * 6 + k * 5) * 26 * k;
    ctx.beginPath(); ctx.ellipse(x + sw, y, rx, 26 + k * 18, 0, 0, 7); ctx.fillStyle = mix('#3b3f52', '#8d91a8', k); ctx.fill();
    ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(20,20,30,.6)'; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(x + sw, y, rx * .8, 12 + k * 8, 0, (t * 7 + i) % 6, (t * 7 + i) % 6 + 2); ctx.strokeStyle = 'rgba(230,230,245,.6)'; ctx.lineWidth = 3; ctx.stroke();
  }
  for (let i = 0; i < 9; i++) { const ang = t * 5 + i * .7, r = 120 + (i % 3) * 60; ctx.save(); ctx.translate(x + Math.cos(ang) * r, ground - 150 - i * 50 + Math.sin(ang) * 20); ctx.rotate(ang * 2); ctx.fillStyle = '#8a5a30'; ctx.fillRect(-18, -5, 36, 10); ctx.restore(); }
  ctx.restore();
}
// ---------- hill, cliff and sea ----------
function sea(t, s, top = 1360) {
  const g = ctx.createLinearGradient(0, top, 0, H); g.addColorStop(0, mix('#4aa7d6', '#22384d', s)); g.addColorStop(1, mix('#1f6b9a', '#0f1d2b', s));
  ctx.fillStyle = g; ctx.fillRect(0, top, W, H - top);
  ctx.strokeStyle = mix('#d8f2ff', '#9fb3c8', s); ctx.lineWidth = 5; ctx.lineCap = 'round';
  for (let r = 0; r < 7; r++) { const y = top + 40 + r * 85, amp = 8 + s * 26; ctx.beginPath();
    for (let x = -20; x <= W + 20; x += 20) ctx.lineTo(x, y + Math.sin(x * .02 + t * (2 + s * 3) + r) * amp); ctx.stroke(); }
}
function cliffScene(t, s) {     // s = storm 0..1
  const g = ctx.createLinearGradient(0, 0, 0, 1400); g.addColorStop(0, mix('#9fd3ea', '#1e2134', s)); g.addColorStop(1, mix('#cdebf6', '#4b4c68', s));
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  if (s < .6) sun(ctx, t);
  for (let i = 0; i < 4; i++) { ctx.save(); if (s > .3) ctx.filter = `brightness(${1 - s * .55})`; cloud(ctx, ((t * (20 + s * 140) + i * 330) % 1500) - 250, 160 + i * 110, .8 + (i % 2) * .4); ctx.restore(); }
  sea(t, s);
  // the cliff (left two thirds), grass top
  ctx.beginPath(); ctx.moveTo(-10, CLIFF - 40); ctx.bezierCurveTo(200, CLIFF - 90, 520, CLIFF - 10, 760, CLIFF); ctx.lineTo(790, CLIFF + 40); ctx.lineTo(740, H + 10); ctx.lineTo(-10, H + 10); ctx.closePath();
  ctx.fillStyle = mix('#8a6a4a', '#4b3a2c', s); ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = INK; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-10, CLIFF - 40); ctx.bezierCurveTo(200, CLIFF - 90, 520, CLIFF - 10, 760, CLIFF); ctx.lineTo(760, CLIFF + 34); ctx.bezierCurveTo(520, CLIFF + 24, 200, CLIFF - 56, -10, CLIFF - 6); ctx.closePath();
  ctx.fillStyle = mix('#7fd35a', '#3f6b34', s); ctx.fill(); ctx.stroke();
  ctx.strokeStyle = mix('#a07a55', '#5a4433', s); ctx.lineWidth = 4; for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(80 + i * 110, CLIFF + 120 + (i % 2) * 120); ctx.lineTo(140 + i * 110, CLIFF + 160 + (i % 2) * 120); ctx.stroke(); }
}
function edgeTree(t, s, bend) {     // a bent tree at the cliff edge
  ctx.save(); ctx.translate(690, CLIFF + 6); ctx.rotate(bend);
  ctx.beginPath(); ctx.moveTo(-14, 0); ctx.quadraticCurveTo(-30, -120, 10, -230); ctx.lineTo(28, -226); ctx.quadraticCurveTo(-6, -120, 14, 0); ctx.closePath(); ctx.fillStyle = '#6b4526'; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = INK; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(8, -170); ctx.quadraticCurveTo(90, -200, 150, -170); ctx.lineWidth = 12; ctx.strokeStyle = '#6b4526'; ctx.stroke();
  ctx.beginPath(); ctx.arc(20, -250, 70, 0, 7); ctx.arc(-40, -220, 50, 0, 7); ctx.arc(80, -220, 55, 0, 7); ctx.fillStyle = mix('#5cbf44', '#2f5a2a', s); ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = INK; ctx.stroke();
  ctx.restore();
}
function whale(x, y, s, rot, o = {}) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
  ctx.beginPath(); ctx.moveTo(-250, -10); ctx.bezierCurveTo(-200, -150, 160, -170, 260, -40); ctx.bezierCurveTo(300, 40, 240, 120, 80, 120); ctx.bezierCurveTo(-60, 120, -180, 60, -250, -10); ctx.closePath();
  ctx.fillStyle = '#4f6f97'; ctx.fill(); ctx.lineWidth = 8; ctx.strokeStyle = INK; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-120, 70); ctx.bezierCurveTo(-20, 130, 160, 130, 250, 40); ctx.lineTo(240, 70); ctx.bezierCurveTo(140, 150, -20, 150, -120, 70); ctx.fillStyle = '#e7eef6'; ctx.fill();
  for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.moveTo(40 + i * 35, 85 - i * 6); ctx.lineTo(60 + i * 35, 118 - i * 8); ctx.lineWidth = 4; ctx.strokeStyle = '#b9c6d6'; ctx.stroke(); }
  ctx.beginPath(); ctx.moveTo(-250, -10); ctx.bezierCurveTo(-300, -60, -360, -40, -380, -90); ctx.bezierCurveTo(-330, -10, -330, 40, -380, 60); ctx.bezierCurveTo(-330, 50, -290, 30, -250, -10); ctx.fillStyle = '#4f6f97'; ctx.fill(); ctx.lineWidth = 7; ctx.strokeStyle = INK; ctx.stroke();
  if (o.mouth) { ctx.beginPath(); ctx.moveTo(270, -10); ctx.quadraticCurveTo(170, 40 + o.mouth * 40, 60, 20); ctx.lineWidth = 7; ctx.stroke(); }
  ctx.beginPath(); ctx.arc(170, -40, 14, 0, 7); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 4; ctx.stroke(); ctx.beginPath(); ctx.arc(174, -40, 7, 0, 7); ctx.fillStyle = INK; ctx.fill();
  ctx.restore();
}
function whaleTail(x, y, s, k) { ctx.save(); ctx.translate(x, y); ctx.scale(s, s); ctx.rotate(Math.sin(k * 3) * .15);
  ctx.beginPath(); ctx.moveTo(-14, 60); ctx.lineTo(-10, -20); ctx.bezierCurveTo(-60, -60, -120, -40, -140, -80); ctx.bezierCurveTo(-90, -100, -30, -70, 0, -40); ctx.bezierCurveTo(30, -70, 90, -100, 140, -80); ctx.bezierCurveTo(120, -40, 60, -60, 10, -20); ctx.lineTo(14, 60); ctx.closePath();
  ctx.fillStyle = '#4f6f97'; ctx.fill(); ctx.lineWidth = 7; ctx.strokeStyle = INK; ctx.stroke(); ctx.restore(); }
function splash(x, y, k, big = 1) { if (k <= 0 || k >= 1) return; ctx.save(); ctx.globalAlpha = 1 - k;
  for (let i = 0; i < 16; i++) { const a = -Math.PI * (i / 15), r = (60 + i % 3 * 40) * big * (.4 + k * 1.6); ctx.beginPath(); ctx.arc(x + Math.cos(a) * r, y + Math.sin(a) * r * 1.3 + k * k * 120, (16 - i % 4 * 3) * big * (1 - k * .5), 0, 7); ctx.fillStyle = '#e6f6ff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = '#6aa9d0'; ctx.stroke(); }
  ctx.restore(); }
function spout(x, y, k) { if (k <= 0 || k >= 1) return; ctx.save(); ctx.globalAlpha = Math.sin(Math.PI * k); ctx.strokeStyle = '#e6f6ff'; ctx.lineWidth = 10; ctx.lineCap = 'round';
  for (const d of [-1, 0, 1]) { ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + d * 30, y - 160 * k, x + d * 90 * k, y - 120 * k); ctx.stroke(); } ctx.restore(); }
function rainbow(a) { if (a <= 0) return; ctx.save(); ctx.globalAlpha = a * .55; const cols = ['#ff5a5a', '#ffa64d', '#ffe14d', '#6fdc6f', '#5ab4ff', '#9a7bff'];
  cols.forEach((c2, i) => { ctx.beginPath(); ctx.arc(820, 1360, 620 - i * 22, Math.PI, Math.PI * 2); ctx.lineWidth = 22; ctx.strokeStyle = c2; ctx.stroke(); }); ctx.restore(); }
function goldWind(cx, cy, t, a) {   // the warm «south wind» swirling around the bird
  if (a <= 0) return; ctx.save(); ctx.globalAlpha = a; ctx.lineCap = 'round';
  for (let i = 0; i < 5; i++) { const ph = t * 4 + i * 1.3, r = 110 + i * 26; ctx.beginPath(); ctx.arc(cx, cy, r, ph, ph + 1.9); ctx.strokeStyle = i % 2 ? 'rgba(255,214,120,.95)' : 'rgba(255,246,210,.9)'; ctx.lineWidth = 9 - i; ctx.shadowColor = '#ffd36b'; ctx.shadowBlur = 20; ctx.stroke(); }
  ctx.restore(); }
function sunRays(a, t) { if (a <= 0) return; ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.globalAlpha = a; ctx.translate(820, 160);
  for (let i = 0; i < 10; i++) { ctx.rotate(.22); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-60, 1900); ctx.lineTo(60, 1900); ctx.closePath(); ctx.fillStyle = `rgba(255,235,170,${.08 + .04 * Math.sin(t * 2 + i)})`; ctx.fill(); } ctx.restore(); }
function feather(x, y, r, a) { if (a <= 0) return; ctx.save(); ctx.globalAlpha = a; ctx.translate(x, y); ctx.rotate(r); ctx.shadowColor = '#ffd36b'; ctx.shadowBlur = 25;
  ctx.beginPath(); ctx.moveTo(0, -60); ctx.bezierCurveTo(30, -30, 26, 30, 0, 60); ctx.bezierCurveTo(-26, 30, -30, -30, 0, -60); ctx.fillStyle = '#f2c14e'; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = INK; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, -60); ctx.lineTo(0, 80); ctx.stroke(); ctx.restore(); }
function shake(k) { if (k > 0) ctx.translate(Math.sin(performanceT * 90) * 14 * k, Math.cos(performanceT * 77) * 10 * k); }
let performanceT = 0;
function standAt(p, x, y, sc = .82) { ctx.save(); ctx.translate(x, y); ctx.scale(sc, sc); stick(ctx, { ...p, x: 0, y: 0 }); ctx.restore(); }
function debris(t, k) { if (k <= 0) return; for (let i = 0; i < 8; i++) { const r = (i * 7919 % 1000) / 1000, x = ((t * (900 + r * 600) + i * 300) % 1600) - 300, y = 300 + r * 900 + Math.sin(t * 3 + i) * 60;
  ctx.save(); ctx.globalAlpha = k; ctx.translate(x, y); ctx.rotate(t * 8 + i); if (i % 3 === 0) { ctx.fillStyle = '#c89356'; ctx.fillRect(-40, -8, 80, 16); ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.strokeRect(-40, -8, 80, 16); } else { ctx.beginPath(); ctx.ellipse(0, 0, 18, 9, 0, 0, 7); ctx.fillStyle = '#6cbf4a'; ctx.fill(); ctx.strokeStyle = INK; ctx.lineWidth = 2.5; ctx.stroke(); } ctx.restore(); } }

window.renderFrame = async function (fr) {
  const t = fr / FPS; performanceT = t;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.filter = 'none';
  const S = storm(t);
  ctx.save();
  if (t < 4.5) {                                  // ---- S1: calm farm turns into a storm, a tornado forms ----
    drawWorld(t); stormSky(t, S); tornado(900, 1180, 900, t, seg(t, 2.6, 4.2), .7); lightning(t, 3.7);
    const scared = t > 3.0;
    standAt({ kind: 'nad', dir: 1, eyes: scared ? 'wide' : 'dot', mouth: scared ? 'o' : 'smile', fright: scared ? 1 : 0, look: 1, headRot: -.1 * seg(t, 2, 2.6), armL: scared ? [-75, -15] : undefined, armR: scared ? [75, -15] : undefined }, 300, GROUND, 1);
    standAt({ kind: 'cap', dir: 1, eyes: scared ? 'wide' : 'dot', mouth: scared ? 'o' : 'grin', capPop: scared ? 30 * Math.sin(Math.PI * seg(t, 3.7, 4.2)) : 0, look: 1, armL: scared ? [-75, -15] : undefined, armR: scared ? [75, -15] : undefined }, 520, GROUND, 1);
    windLines(t, S); rain(t, S * .8);
  } else if (t < 8.5) {                           // ---- S2: the South Wind Bird fights the storm and is hit ----
    const k = seg(t, 4.5, 8.5); ctx.translate(0, 0);
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1b1d2e'); g.addColorStop(1, '#45465f'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 7; i++) { ctx.save(); ctx.filter = 'brightness(.45)'; cloud(ctx, ((t * (200 + i * 50) + i * 230) % 1700) - 300, 200 + i * 230, 1.3 + (i % 3) * .3); ctx.restore(); }
    tornado(540, 2100, 2200, t, .35, 1.6); rain(t, 1); windLines(t, 1, 100, 1800);
    const hit = seg(t, 6.3, 6.6), fall = seg(t, 6.6, 8.5);
    let bx = 540 + Math.sin(t * 3) * 120 - fall * 200, by = 800 + Math.sin(t * 5) * 60 + fall * fall * 1300, rot = Math.sin(t * 4) * .3 + fall * 6;
    if (t < 6.3) { bx -= (6.3 - t) * 40; }
    bird(ctx, bx, by, 1.15, t * 18, rot, { glow: .6 * (1 - fall), hurt: t > 6.5, eyes: t > 6.5 ? 'closed' : 'open' });
    // a fence plank flies in and hits
    const px = lerp(1300, bx + 60, seg(t, 5.7, 6.35)), py = lerp(400, by - 40, seg(t, 5.7, 6.35));
    if (t < 6.6) { ctx.save(); ctx.translate(px, py); ctx.rotate(t * 12); ctx.fillStyle = '#c89356'; ctx.fillRect(-90, -16, 180, 32); ctx.strokeStyle = INK; ctx.lineWidth = 4; ctx.strokeRect(-90, -16, 180, 32); ctx.restore(); }
    if (hit > 0 && hit < 1) { sparkle(ctx, bx + 40, by - 40, hit); ctx.save(); ctx.globalAlpha = (1 - hit) * .5; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); ctx.restore(); }
    lightning(t, 5.2); lightning(t, 7.6);
  } else if (t < 14) {                            // ---- S3: run up the hill against the wind to the bird in the tree ----
    cliffScene(t, S); tornado(950, 1360, 1000, t, .85, .8);
    const tw = t - 8.5;
    whaleTail(900, 1420, .9, t); splash(900, 1400, seg(t, 11.8, 13.2), 1.2);
    edgeTree(t, S, Math.sin(t * 6) * .05 - .08);
    bird(ctx, 760, CLIFF - 160 + Math.sin(t * 9) * 6, .55, 0, .4 + Math.sin(t * 7) * .1, { hurt: true });
    const run = eio(seg(t, 8.6, 13.6));
    const nx = lerp(-150, 330, run), cxp = lerp(-20, 470, run), lean = .28;
    const ny = CLIFF - 40 + run * 20;
    standAt({ kind: 'nad', dir: 1, walk: tw * 10, lean, eyes: 'wide', mouth: 'shout', fright: 1, armL: [-60, 40], armR: [60, 60] }, nx, ny);
    standAt({ kind: 'cap', dir: 1, walk: tw * 10 + 1.6, lean, eyes: 'dot', mouth: 'flat', noCap: t > 10, armL: [-60, 40], armR: [70, -40] }, cxp, ny + 10);
    if (t > 10 && t < 11.6) { const k = seg(t, 10, 11.6); ctx.save(); ctx.translate(cxp - 400 * k, ny - 560 - 300 * k); ctx.rotate(-k * 9); ctx.beginPath(); ctx.arc(0, 0, 50, Math.PI, 0); ctx.fillStyle = COL.cap; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = INK; ctx.stroke(); ctx.beginPath(); ctx.ellipse(55, 0, 40, 10, 0, 0, 7); ctx.fillStyle = COL.cap; ctx.fill(); ctx.stroke(); ctx.restore(); }
    debris(t, 1); windLines(t, 1); rain(t, .8); lightning(t, 9.4); lightning(t, 12.9);
  } else if (t < 20) {                            // ---- S4: the branch snaps, Cap dives, Nadara holds him, a whale breaches ----
    const zoom = 1 + .25 * eio(seg(t, 14, 15.5)), sh = seg(t, 16.4, 16.8) * (1 - seg(t, 18.6, 19.4));
    ctx.translate(540, 1200); ctx.scale(zoom, zoom); ctx.translate(-600, -1250); shake(sh);
    cliffScene(t, S); tornado(1000, 1360, 1000, t, .6, .8);
    edgeTree(t, S, -.08 + (t > 14.8 ? -.25 * seg(t, 14.8, 15.1) : 0));
    // bird slides off the edge, falls toward the sea
    const slide = seg(t, 14.9, 15.6), drop = seg(t, 15.6, 17.2);
    const caught = t >= 17.2;
    let bx = lerp(760, 820, slide), by = lerp(CLIFF - 160, CLIFF - 40, slide) + drop * drop * 260;
    // Cap dives: hangs over the edge, Nadara holds his ankles
    const dive = eio(seg(t, 15.4, 16.4)), pull = eio(seg(t, 18.4, 19.6));
    const capRot = lerp(0, 1.72, dive) * (1 - pull), capX = lerp(600, 560, dive * (1 - pull)), capY = CLIFF + 6;
    standAt({ kind: 'nad', dir: 1, lean: -.32 * dive, eyes: 'wide', mouth: 'shout', fright: 1, armL: [120 * dive + 30, 150 - 40 * dive], armR: [140 * dive + 30, 140 - 40 * dive], spread: 20 }, 420, CLIFF + 4);
    ctx.save(); ctx.translate(capX, capY); ctx.scale(.82, .82); ctx.rotate(capRot); stick(ctx, { kind: 'cap', x: 0, y: 0, dir: 1, eyes: 'wide', mouth: caught ? 'grin' : 'o', noCap: true, armL: [-40, -170], armR: [40, -170] }); ctx.restore();
    if (caught) { bx = capX + Math.sin(capRot) * 470; by = capY - Math.cos(capRot) * 470 + 20; }
    // the whale breaches below with an open mouth
    const wb = seg(t, 16.3, 18.6), wy = 1700 - Math.sin(Math.PI * wb) * 520, wr = lerp(-.9, .9, wb);
    if (wb > 0 && wb < 1) whale(860, wy, .75, wr, { mouth: Math.sin(Math.PI * wb) });
    splash(860, 1400, seg(t, 16.25, 17.0), 1.6); splash(860, 1400, seg(t, 18.5, 19.4), 1.8);
    bird(ctx, bx, by, .55, t * 6, caught ? .2 : .4 + drop * 2, { hurt: true });
    windLines(t, 1); rain(t, .8); lightning(t, 14.85);
    if (t > 17.15 && t < 17.6) sparkle(ctx, bx, by, seg(t, 17.15, 17.6));
  } else if (t < 24) {                            // ---- S5: shelter behind a rock, the tornado passes, the sky opens ----
    cliffScene(t, S);
    const pass = seg(t, 20.2, 22.6); tornado(lerp(1400, -500, pass), 1360, 1100, t, 1 - seg(t, 22.2, 23), .9);
    ctx.save(); ctx.beginPath(); ctx.moveTo(380, CLIFF + 20); ctx.bezierCurveTo(390, CLIFF - 330, 640, CLIFF - 380, 700, CLIFF + 20); ctx.closePath(); ctx.fillStyle = '#8b8f99'; ctx.fill(); ctx.lineWidth = 6; ctx.strokeStyle = INK; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(470, CLIFF - 200); ctx.lineTo(520, CLIFF - 150); ctx.moveTo(600, CLIFF - 260); ctx.lineTo(630, CLIFF - 200); ctx.lineWidth = 4; ctx.stroke(); ctx.restore();
    const peek = seg(t, 22.8, 23.6);
    standAt({ kind: 'nad', dir: -1, eyes: peek > 0 ? 'dot' : 'closed', mouth: peek > 0 ? 'smile' : 'worry', armL: [-40, 120], armR: [40, 120], lift: -20 }, 330, CLIFF + 6);
    standAt({ kind: 'cap', dir: -1, eyes: peek > 0 ? 'happy' : 'closed', mouth: peek > 0 ? 'grin' : 'flat', noCap: true, armL: [-60, 60], armR: [10, 60], lift: -40 }, 220, CLIFF + 10);
    bird(ctx, 205, CLIFF - 330 - 40, .45, 0, 0, { hurt: true, eyes: 'closed', glow: .4 });
    debris(t, 1 - seg(t, 22, 23)); windLines(t, 1 - seg(t, 22, 23.2)); rain(t, .8 * (1 - seg(t, 22, 23.4)));
    sunRays(seg(t, 23, 24), t);
  } else if (t < 33) {                            // ---- S6: lessons, a fall, the south wind, the bird flies over the whales ----
    cliffScene(t, 0); sunRays(.8, t); rainbow(seg(t, 29, 31));
    whaleTail(860, 1440, .7, t); spout(700, 1420, seg(t, 31, 32.4)); spout(960, 1430, seg(t, 31.4, 32.8));
    const lesson = t < 26.2, tryFall = t >= 26.2 && t < 27.6, run = seg(t, 27.6, 29.4), fly = seg(t, 29, 33);
    const flap = lesson ? Math.sin(t * 14) : 0;
    standAt({ kind: 'cap', dir: 1, eyes: 'happy', mouth: 'grin', noCap: true, armL: [-120, -40 + flap * 90], armR: [120, -40 + flap * 90], lift: lesson ? Math.abs(Math.sin(t * 7)) * 30 : 0, walk: run > 0 && run < 1 ? t * 12 : NaN }, lerp(250, 430, run), CLIFF - 40 + run * 20);
    const nadArms = run > 0 && fly < .02 ? [[-30, -190], [30, -190]] : [[-30, -60], [30, -60]];
    standAt({ kind: 'nad', dir: -1, eyes: tryFall ? 'wide' : 'dot', mouth: tryFall ? 'o' : 'smile', armL: nadArms[0], armR: nadArms[1], walk: run > 0 && run < 1 ? t * 12 + 1.6 : NaN }, lerp(470, 610, run), CLIFF - 30 + run * 20);
    let bx, by, br = 0, wing = 0, glow = 0;
    if (lesson) { bx = 470; by = CLIFF - 520; wing = Math.sin(t * 3) * .3; }
    else if (tryFall) { const k = seg(t, 26.2, 27.6); bx = 470 + k * 60; by = CLIFF - 520 - Math.sin(Math.PI * Math.min(1, k * 1.6)) * 160 + Math.max(0, k * 1.6 - 1) * 400; wing = t * 25; br = k * 2; if (k > .85) sparkle(ctx, bx, CLIFF - 300, seg(t, 27.3, 27.6)); }
    else if (fly <= 0) { bx = lerp(530, 610, run); by = CLIFF - 590 + Math.sin(t * 10) * 8; wing = t * 8; }
    else { const a = fly * Math.PI * 2.2; bx = 600 + Math.sin(a) * 300 * fly + fly * 150; by = CLIFF - 600 - fly * 500 - Math.sin(a * 1.3) * 140; wing = t * 16; br = Math.cos(a) * .3; glow = 1; }
    goldWind(bx, by, t, seg(t, 28.6, 29.4) * (1 - seg(t, 31.5, 33)));
    bird(ctx, bx, by, .7, wing, br, { glow, hurt: false, eyes: 'open' });
  } else {                                        // ---- S7: the bird flies into the sunset and drops a glowing feather ----
    const k = seg(t, 33, 38);
    const g = ctx.createLinearGradient(0, 0, 0, 1400); g.addColorStop(0, '#f6a35a'); g.addColorStop(.6, '#ffd59a'); g.addColorStop(1, '#ffe9c4'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.beginPath(); ctx.arc(780, 1280, 190, 0, 7); ctx.fillStyle = '#ffcf5a'; ctx.fill();
    sea(t, 0); ctx.save(); ctx.globalAlpha = .4; ctx.fillStyle = '#ff9f5a'; ctx.fillRect(0, 1360, W, 560); ctx.restore();
    cliffScene !== null; ctx.save(); ctx.beginPath(); ctx.moveTo(-10, CLIFF + 60); ctx.bezierCurveTo(200, CLIFF + 10, 380, CLIFF + 70, 560, CLIFF + 90); ctx.lineTo(560, H); ctx.lineTo(-10, H); ctx.closePath(); ctx.fillStyle = '#3f2d22'; ctx.fill(); ctx.restore();
    const bx = lerp(520, 830, k), by = lerp(700, 1150, k * k), bs = lerp(.6, .12, k);
    bird(ctx, bx, by, bs, t * 14, -.2, { glow: 1, flip: false });
    const fk = seg(t, 33.4, 36.4), fx = lerp(560, 330, fk) + Math.sin(fk * 9) * 40, fy = lerp(760, CLIFF - 520, fk);
    feather(fx, fy, Math.sin(fk * 9) * .6, 1 - seg(t, 36.4, 36.8));
    const got = seg(t, 36.4, 37);
    ctx.save(); ctx.filter = 'brightness(.55)';
    standAt({ kind: 'nad', dir: 1, eyes: 'happy', mouth: 'grin', armL: [-30, 150], armR: [110, -150 + Math.sin(t * 8) * 30] }, 200, CLIFF + 70);
    standAt({ kind: 'cap', dir: 1, eyes: 'happy', mouth: 'grin', noCap: true, armL: [-40, 140], armR: [40, -150 + got * 60] }, 360, CLIFF + 75);
    ctx.restore();
    if (got > 0) feather(360 + 30, CLIFF + 75 - 520, -.5, 1);
  }
  ctx.restore();
  // whole-film fades and a light grain of drama
  const fin = 1 - seg(t, 0, .5), fout = seg(t, 37.2, 38);
  if (fin + fout > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.max(fin, fout)})`; ctx.fillRect(0, 0, W, H); }
  // shot-change flash
  for (const c0 of [4.5, 8.5, 14, 20, 24, 33]) { const f = Math.exp(-Math.pow((t - c0) / .09, 2)); if (f > .02) { ctx.fillStyle = `rgba(255,255,255,${f * .6})`; ctx.fillRect(0, 0, W, H); } }
  return true;
};
(async () => {
  buildBG();
  window.FRAMES = Math.round(DUR * FPS);
  await Promise.allSettled(['AmiriB'].map(f => document.fonts.load(`60px ${f}`, 'ا')));
  window.ready = true;
})();
