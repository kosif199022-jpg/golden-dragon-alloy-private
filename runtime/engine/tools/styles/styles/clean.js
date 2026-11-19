/* clean: a clean cinematic tribute (first delivered 2026-11-06 as a 40 s film, for the brief «cinematic,
 * no explaining, only beautiful type»). Full-bleed footage, a gentle push, short dissolves (longer next to b-roll),
 * grain and vignette, a gold Ruqaa title, her words in white Ruqaa revealed word by word, a gold end title.
 * CFG.lines are the quotes: '|' forces a line break, long quotes wrap at 900 px.
 * CFG knobs: dissolve, dissolve_broll, push, vignette, grain.
 */
const LOOK_CL = 'contrast(1.07) saturate(1.04) brightness(1.01)';
const XD_CL = C.dissolve ?? .14, XB_CL = C.dissolve_broll ?? .5;

async function clShot(s, t, a) {
  const p = ease(cl((t - s.st) / (s.en - s.st + .5)));
  await drawShot(s, t, { filter: LOOK_CL, push: C.push ?? .06, prog: p, alpha: a });
}

// split a quote into lines: '|' breaks by hand, otherwise wrap at max px
function wrapLines(txt, max) {
  if (txt.includes('|')) return txt.split('|').map((x) => x.split(/\s+/).filter(Boolean));
  const ws = txt.split(/\s+/).filter(Boolean), L = [];
  let cur = [];
  for (const w of ws) {
    const tr = [...cur, w].join(' ');
    if (cur.length && g.measureText(tr).width > max) { L.push(cur); cur = [w]; } else cur.push(w);
  }
  if (cur.length) L.push(cur);
  return L;
}

// a quote in the lower band: each word fades up with a small rise, spread across the first half of its time
function quote(q, t) {
  const d = q.e - q.s, lt = t - q.s;
  if (!q.t || lt < 0 || lt > d) return;
  g.save();
  g.font = font(q.font || 'Ruqaa', q.size || 76);
  g.direction = 'rtl';
  g.textBaseline = 'middle';
  const L = wrapLines(String(q.t), 900), lh = (q.size || 76) * 1.55, y0 = (q.y || 1560) - (L.length - 1) * lh / 2;
  const sp = g.measureText(' ').width;
  const sh = g.createLinearGradient(0, 1250, 0, H);
  sh.addColorStop(0, 'rgba(0,0,0,0)');
  sh.addColorStop(1, 'rgba(0,0,0,.55)');
  const fo = cl((d - lt) / .4);
  g.globalAlpha = fo * cl(lt / .3);
  g.fillStyle = sh;
  g.fillRect(0, 1250, W, H - 1250);
  const N = L.flat().length, rev = Math.min(d * .55, N * .32);
  let i = 0;
  L.forEach((ln, j) => {
    const tw = ln.reduce((a, w) => a + g.measureText(w).width, 0) + sp * (ln.length - 1);
    let x = 540 + Math.min(tw, 1000) / 2;
    const fit = Math.min(1, 1000 / tw);
    for (const w of ln) {
      const ww = g.measureText(w).width * fit, a = eo(cl((lt - i / N * rev) / .45));
      g.save();
      g.globalAlpha = a * fo;
      g.shadowColor = 'rgba(0,0,0,.75)';
      g.shadowBlur = 18;
      g.fillStyle = q.gold ? goldG(y0 + j * lh - 40, y0 + j * lh + 40, GOLD_SOFT) : '#fff';
      g.textAlign = 'right';
      g.translate(x, y0 + j * lh + (1 - a) * 16);
      g.scale(fit, fit);
      g.fillText(w, 0, 0);
      g.restore();
      x -= ww + sp * fit;
      i++;
    }
  });
  g.restore();
}

function clTitle(t) {
  const T = C.title;
  if (!T || !T.text) return;
  const a0 = T.start ?? .25, a1 = T.end ?? 3.25;
  if (t > a1 + .05) return;
  const a = eo(cl((t - a0) / 1.1)) * cl((a1 - t) / .5);
  if (a <= 0) return;
  g.save();
  g.globalAlpha = a;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  const s = 1.08 - .08 * eo(cl((t - a0 + .25) / 2.2));
  g.translate(540, T.y || 880);
  g.scale(s, s);
  g.font = font(T.font || 'Ruqaa', T.size || 250);
  g.shadowColor = 'rgba(0,0,0,.6)';
  g.shadowBlur = 30;
  g.fillStyle = goldG(-130, 130, GOLD_SOFT);
  g.fillText(T.text, 0, 0, 1000);
  if (T.sub) {
    g.font = font('Tajawal', 54);
    g.fillStyle = '#fff';
    g.fillText(T.sub, 0, 190, 1000);
  }
  g.restore();
}

// the footage darkens from just before the end title, under the grain and the vignette
function clDim(t) {
  const E = C.end;
  if (E && E.at != null && t > E.at - .2) dim(.62 * cl((t - (E.at - .2)) / 1.2));
}

function clEnd(t) {
  const E = C.end;
  if (!E || E.at == null || t < E.at) return;
  const a = eo(cl((t - E.at - .2) / 1.0));
  g.save();
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  g.globalAlpha = a;
  g.shadowColor = 'rgba(0,0,0,.65)';
  g.shadowBlur = 30;
  if (E.title) {
    g.font = font('Ruqaa', E.size || 170);
    g.fillStyle = goldG(760, 980, GOLD_SOFT);
    g.fillText(E.title, 540, 870 + (1 - a) * 20, 1000);
  }
  if (E.sub) {
    g.font = font('Tajawal', 50);
    g.fillStyle = '#fff';
    g.shadowBlur = 14;
    g.fillText(E.sub, 540, 1010, 1000);
  }
  g.restore();
  credit(t, E.at + 1.0, 1440, { sizes: [44, 34], gap: 65, baseline: 'middle' });
}

async function render(t) {
  g.fillStyle = '#000';
  g.fillRect(0, 0, W, H);
  if (S.length) {
    const i = shotIndex(t), s = S[i], lt = t - s.st;
    const xd = i > 0 && (s.broll || S[i - 1].broll) ? XB_CL : XD_CL;
    if (i > 0 && lt < xd) {
      await clShot(S[i - 1], t, 1);
      await clShot(s, t, ease(lt / xd));
    } else await clShot(s, t, 1);
  }
  clDim(t);
  vignette(C.vignette ?? .42, 520);
  grain(t, C.grain ?? .035, 1100);
  clTitle(t);
  for (const q of C.lines || []) quote(q, t);
  clEnd(t);
  fades(t, 0, .5, .85);
  watermark();
}
boot(render);
