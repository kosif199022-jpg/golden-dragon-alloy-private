/* medal: one shape carries the film (the saas-animation manner, first delivered 2026-11-06).
 * A gold medal drops onto a flag-red field, squashes, then grows into the first shot. Every later shot grows out of
 * the one before, by its move: 'iris' (a circle opens from the centre), 'flip' (the frame closes into a card that
 * flips edge-on to the next shot), 'flood' (the card floods gold and grows to fill the frame; the next shot eases in
 * out of the gold). At CFG.end.at the frame shrinks back into a circle that becomes the medal again.
 * Nothing cross-dissolves, and the subject stays in the centre.
 * CFG knobs: field, ink, medal_text, grain. Shot fields: move, at (move time, default the shot start), fill (iris
 * colour: 'ink', 'field' or a CSS colour; by default irises alternate ink and field).
 */
const FIELD = C.field || '#b5121b', INK = C.ink || '#0b0b10', MEDAL = C.medal_text ?? '١';
const LOOK = 'contrast(1.05) saturate(1.05)';
const T0 = S.length ? S[0].st : Math.min(2.5, DUR / 2);  // the medal starts to grow into the first shot
const kI = cl(T0 / 2.5, .1, 1);                         // shorter intro when the first shot starts early
const END = C.end && C.end.at != null ? C.end.at : Math.max(T0 + 1, DUR - 4.1);
const B = { medalIn: .35 * kI, medalLand: 1.5 * kI, squash: T0 - .45 * kI, grow: T0, open: T0 + .8,
  shrink: END, medal: END + .7 };

// moves: shot 0 grows out of the medal, the others arrive by iris / flip / flood at time `at`
const MV = S.map((s, i) => ({ i, move: i ? (s.move || 'iris') : 'grow', at: i ? (s.at ?? s.st) : T0, fill: s.fill }));
let irisN = 0;
for (const m of MV) {
  if (m.move !== 'iris') continue;
  m.color = m.fill === 'field' ? FIELD : m.fill === 'ink' ? INK : (m.fill || (irisN % 2 ? FIELD : INK));
  irisN++;
}

// card runs: from the card closing (0.8 s before the first flip) to the flood that opens the frame again
const RUNS = [];
(function cardRuns() {
  let run = null;
  for (const m of MV) {
    if (m.move === 'flip') {
      if (!run) run = { a: m.at - .8, card: m.at - .3, base: m.i - 1, first: m.at, flips: [] };
      run.flips.push(m);
    } else if (m.move === 'flood') {
      if (!run) run = { a: m.at - .65, card: null, base: m.i - 1, first: m.at, flips: [] };
      run.flood = m.at;
      run.b = m.at;
      RUNS.push(run);
      run = null;
    } else if (run) {
      run.b = m.at;  // a card run left open (build_style.py warns): it just ends at the next move
      RUNS.push(run);
      run = null;
    }
  }
  if (run) { run.b = B.shrink; RUNS.push(run); }
})();

function goldFill(cx, cy, r) {
  const gr = g.createRadialGradient(cx - r * .35, cy - r * .4, r * .1, cx, cy, r);
  gr.addColorStop(0, '#fff1b8');
  gr.addColorStop(.45, '#e9c46a');
  gr.addColorStop(1, '#a8781f');
  return gr;
}

function medal(cx, cy, r, sx = 1, sy = 1, shine = 0) {
  g.save();
  g.translate(cx, cy);
  g.scale(sx, sy);
  g.beginPath();
  g.arc(0, 0, r, 0, 7);
  g.fillStyle = goldFill(0, 0, r);
  g.fill();
  g.lineWidth = r * .06;
  g.strokeStyle = 'rgba(120,80,20,.55)';
  g.beginPath();
  g.arc(0, 0, r * .82, 0, 7);
  g.stroke();
  if (MEDAL) {
    g.font = font('Ruqaa', r * 1.05);
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillStyle = 'rgba(110,70,15,.85)';
    g.fillText(MEDAL, 0, r * .06);
  }
  if (shine > 0 && shine < 1) {
    g.save();
    g.beginPath();
    g.arc(0, 0, r, 0, 7);
    g.clip();
    const x = lerp(-r * 1.6, r * 1.6, shine), sh = g.createLinearGradient(x - r * .3, 0, x + r * .3, 0);
    sh.addColorStop(0, 'rgba(255,255,255,0)');
    sh.addColorStop(.5, 'rgba(255,255,255,.55)');
    sh.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = sh;
    g.fillRect(-r, -r, 2 * r, 2 * r);
    g.restore();
  }
  g.restore();
}

// a shot full-bleed with a slow push that never reverses
const mshot = (s, t, o = {}) => drawShot(s, t, { filter: LOOK, push: .07, prog: seg(t, s.st - .6, s.en + .6), ...o });

function lowerShade(a) {
  if (a <= 0) return;
  g.save();
  g.globalAlpha = a;
  const sh = g.createLinearGradient(0, 1300, 0, H);
  sh.addColorStop(0, 'rgba(0,0,0,0)');
  sh.addColorStop(1, 'rgba(0,0,0,.6)');
  g.fillStyle = sh;
  g.fillRect(0, 1300, W, H - 1300);
  g.restore();
}

async function intro(t) {
  const d = eo(seg(t, B.medalIn, B.medalLand)), y = lerp(-200, 960, d);
  let sx = 1, sy = 1;
  const q = seg(t, B.squash, B.grow);
  if (q > 0 && q < 1) { const k = Math.sin(q * Math.PI) * .08; sx = 1 + k; sy = 1 - k; }
  if (t >= B.grow && S.length) {
    const r = lerp(170, 1150, expo(seg(t, B.grow, B.open)));
    g.save();
    g.beginPath();
    g.arc(540, 960, r, 0, 7);
    g.clip();
    g.fillStyle = goldFill(540, 960, r);
    g.fillRect(0, 0, W, H);
    const e = seg(t, B.grow + .25, B.open);
    if (e > 0) {
      g.save();
      g.beginPath();
      g.arc(540, 960, r * .96, 0, 7);
      g.clip();
      await mshot(S[0], t, { scale: lerp(.93, 1, eo(e)) });
      g.restore();
    }
    g.restore();
  } else medal(540, y, 170, sx, sy, seg(t, B.medalLand + .05, B.squash - .05));
  const T = C.title;
  if (T && T.text) words(T.text, t, T.start ?? kI, T.end ?? B.grow + .15, T.y || 1260,
    { size: T.size || 78, family: T.font, stagger: .08, soft: true, rise: 18, out: .45 });
}

// the frame closes into a card, flips edge-on to swap shots, then floods gold and grows to fill the frame
async function cardRun(run, t) {
  const c = run.card == null ? 0 : eio(seg(t, run.card - .5, run.card + .3));
  const cw = lerp(W, 780, c), ch = lerp(H, 1380, c), rad = lerp(0, 56, c);
  if (c > 0) await mshot(S[run.base], cl(t, 0, run.first + 3), { filter: `blur(${(18 * c).toFixed(1)}px) brightness(.55)` });
  let k = run.base, fx = 1;
  for (const f of run.flips) {
    if (t < f.at - .2) continue;
    const q = seg(t, f.at - .2, f.at + .25);
    k = q < .5 ? f.i - 1 : f.i;
    fx = Math.abs(Math.cos(q * Math.PI));
  }
  const fl = run.flood != null ? seg(t, run.flood - .65, run.flood) : 0;
  const gw = lerp(cw, W * 1.05, eio(fl)), gh = lerp(ch, H * 1.05, eio(fl)), gr = lerp(rad, 0, fl);
  g.save();
  g.translate(540, 960);
  g.scale(Math.max(fx, .02), 1);
  g.shadowColor = 'rgba(0,0,0,.45)';
  g.shadowBlur = 60 * c;
  rr(-gw / 2, -gh / 2, gw, gh, gr);
  g.fillStyle = INK;
  g.fill();
  g.shadowBlur = 0;
  g.clip();
  g.translate(-540, -960);
  await mshot(S[k], t, { scale: c > 0 ? .78 + .22 * (1 - c) : 1 });
  if (fl > 0) {
    g.fillStyle = goldFill(540, 960, 1100);
    g.globalAlpha = eo(cl(fl * 1.6));
    g.fillRect(0, 0, W, H);
  }
  g.restore();
}

// full frame: the shot whose move has happened, with its iris or gold ease-in while it is still arriving
async function fullState(t) {
  let m = MV[0];
  for (const x of MV) if (x.at <= t) m = x;
  const s = S[m.i];
  if (m.move === 'iris' && t < m.at + .85) {
    await mshot(S[m.i - 1], t);
    const q = seg(t, m.at, m.at + .85), r = lerp(0, 1150, eio(q));
    g.save();
    g.beginPath();
    g.arc(540, 900, r, 0, 7);
    g.clip();
    g.fillStyle = m.color;
    g.fillRect(0, 0, W, H);
    await mshot(s, t, { scale: lerp(.93, 1, eo(q)) });
    g.restore();
  } else if (m.move === 'flood' && t < m.at + .5) {
    g.fillStyle = goldFill(540, 960, 1100);
    g.fillRect(0, 0, W, H);
    await mshot(s, t, { scale: lerp(.93, 1, eo(seg(t, m.at, m.at + .5))) });
  } else await mshot(s, t);
}

// the whole frame shrinks back into a circle, and the circle becomes the medal again
async function outro(t) {
  const k = expo(seg(t, B.shrink, B.medal)), r = lerp(1150, 170, k);
  g.save();
  g.beginPath();
  g.arc(540, 960, r, 0, 7);
  g.clip();
  if (S.length) { const s = S[S.length - 1]; await mshot(s, Math.min(t, s.en + .5)); }
  const m = seg(t, B.medal - .25, B.medal + .35);
  if (m > 0) {
    g.fillStyle = goldFill(540, 960, r);
    g.globalAlpha = eo(m);
    g.fillRect(0, 0, W, H);
  }
  g.restore();
  if (t >= B.medal + .35) medal(540, 960, 170, 1, 1, seg(t, B.medal + .5, B.medal + 1.1));
  const E = C.end || {};
  words(E.title, t, B.medal + .3, DUR + 1, 1260, { size: E.size || 84, stagger: .08, soft: true, rise: 18, out: .45 });
  credit(t, B.medal + 1.4, 1560, { sizes: [36, 30], gap: 52, fade: .7 });
}

async function render(t) {
  g.fillStyle = FIELD;
  g.fillRect(0, 0, W, H);
  if (t < B.open) await intro(t);
  else if (t >= B.shrink) await outro(t);
  else {
    const run = RUNS.find((r) => t >= r.a && t < r.b);
    if (run) await cardRun(run, t);
    else await fullState(t);
  }
  // one line per shot, lower centre, under the subject
  const L = C.lines || [];
  let shade = 0;
  for (const q of L) shade = Math.max(shade, cl((t - q.s + .3) / .4) * cl((q.e + .2 - t) / .4));
  lowerShade(shade);
  for (const q of L) words(q.t, t, q.s, q.e, q.y || 1600, { size: q.size || 64, family: q.font, gold: q.gold,
    soft: !q.gold, stagger: .08, rise: 18, out: .45 });
  grain(t, C.grain ?? .03, 900);
  dim(cl((t - (DUR - .6)) / .6) * .85);
  watermark();
}
boot(render);
