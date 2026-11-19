/* beat: cut on the beat (first used for «قوم يا مصري», 2026-11-08). A punch-in on every cut, a whip smear on every
 * second cut, a three-panel split (CFG.tri) and heavy Lalezar slams (CFG.slams). build_style.py puts shots and slams
 * on the beat grid; CFG.beat is the beat period in seconds.
 * CFG knobs: grade, punch, whip, bar (slam underline colour, null hides it), vignette, grain.
 */
const P = C.beat || .5, TRI = C.tri || [];
const triIx = new Set(TRI.flatMap((x) => x.ix));
const MAIN = S.map((s, i) => i).filter((i) => !triIx.has(i));
const GR = C.grade || 'contrast(1.12) saturate(1.15)';
const PUNCH = C.punch ?? .12;

function slam(txt, t, a, e) {
  if (!txt || t < a || t > e) return;
  const lt = t - a, k = eo(cl(lt / .18)), out = cl((t - (e - .12)) / .12), long = txt.length > 8;
  g.save();
  g.translate(540, 960);
  const sc = lerp(1.7, 1, k) * (1 + .04 * Math.sin(lt * 40) * Math.exp(-lt * 12));
  g.scale(sc, sc);
  g.globalAlpha = k * (1 - out);
  g.font = font('Lalezar', long ? 150 : 230);
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  g.lineWidth = 14;
  g.strokeStyle = 'rgba(0,0,0,.55)';
  g.strokeText(txt, 0, 0, 1000);
  const gr = g.createLinearGradient(0, -110, 0, 110);
  gr.addColorStop(0, '#ffffff');
  gr.addColorStop(.58, '#ffffff');
  gr.addColorStop(1, '#e9c46a');
  g.fillStyle = gr;
  g.fillText(txt, 0, 0, 1000);
  if (C.bar !== null) {
    g.fillStyle = C.bar || '#c8102e';
    g.fillRect(-140, long ? 95 : 135, 280, 12);
  }
  g.restore();
}

// a shot with a punch-in that decays right after its cut
async function shotAt(i, t, o = {}) {
  const s = S[i], lt = t - s.st, punch = 1 + PUNCH * Math.exp(-lt * 9);
  await drawShot(s, t, { filter: GR, push: .04, scale: punch, ...o });
}

// three vertical panels arrive one per beat, then the middle one opens to full frame on the way out
async function triptych(tri, t) {
  const open = seg(t, tri.en - .45, tri.en);
  for (const j of (open > 0 ? [0, 2, 1] : [0, 1, 2])) {
    const a = tri.st + j * P, k = eio(seg(t, a, a + .3));
    if (k <= 0) continue;
    let x = j * 360, w = 360;
    if (open > 0 && j === 1) { x = lerp(360, 0, eio(open)); w = lerp(360, W, eio(open)); }
    g.save();
    g.translate(0, (1 - k) * (j % 2 ? -H : H));
    await drawShot(S[tri.ix[j]], t, { x, y: 0, w, h: H, filter: GR, push: .05 });
    g.restore();
  }
  const sep = H * (1 - open);
  g.fillStyle = '#000';
  g.fillRect(358, 0, 4, sep);
  g.fillRect(718, 0, 4, sep);
}

function beatEnd(t) {
  const E = C.end;
  if (!E || E.at == null || t < E.at) return;
  dim(.5 * eo(seg(t, E.at, E.at + .8)));
  const k = eo(seg(t, E.at + .2, E.at + 1.1));
  g.save();
  g.globalAlpha = k;
  g.textAlign = 'center';
  g.direction = 'rtl';
  g.shadowColor = 'rgba(0,0,0,.7)';
  g.shadowBlur = 24;
  if (E.title) {
    g.font = font('Lalezar', E.size || 170);
    g.fillStyle = '#fff';
    g.fillText(E.title, 540, 880 + (1 - k) * 30, 1000);
  }
  if (E.sub) {
    g.font = font('Tajawal', 54);
    g.fillStyle = goldG(930, 990);
    g.fillText(E.sub, 540, 990, 1000);
  }
  g.restore();
  credit(t, E.at + 1.6, 1500);
}

async function render(t) {
  g.fillStyle = '#000';
  g.fillRect(0, 0, W, H);
  const tri = TRI.find((x) => t >= x.st && t < x.en);
  if (tri) await triptych(tri, t);
  else if (MAIN.length) {
    let m = 0;
    for (let j = 0; j < MAIN.length; j++) if (S[MAIN[j]].st <= t) m = j;
    const i = MAIN[m], s = S[i], lt = t - s.st;
    const whip = C.whip !== false && m > 0 && m % 2 === 0 && !s.broll && !S[MAIN[m - 1]].broll && lt < .16;
    if (whip) {
      // directional smear: the old frame leaves to the left, the new one enters from the right, both ghosted
      const k = lt / .16;
      for (let r = 0; r < 5; r++) await shotAt(MAIN[m - 1], t, { dx: lerp(0, -W * .6, k) - r * 40, alpha: .35 });
      for (let r = 0; r < 5; r++) await shotAt(i, t, { dx: lerp(W * .6, 0, k) + r * 40, alpha: .3 + .14 * k });
    } else await shotAt(i, t);
  }
  vignette(C.vignette ?? .45);
  for (const q of C.slams || []) slam(q.t, t, q.s, q.e);
  specLines(t, 1620, 62);
  beatEnd(t);
  grain(t, C.grain ?? .04);
  fades(t);
  watermark();
}
boot(render);
