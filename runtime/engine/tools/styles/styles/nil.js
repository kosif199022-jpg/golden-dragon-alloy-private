/* nil: slow and warm (first used for «بنت النيل», 2026-11-08). Letterbox bars, a warm grade, long pushes, eased
 * dissolves, a gold Ruqaa title, word-by-word lines and a gold end title.
 * CFG knobs: grade, push, dissolve, letterbox, vignette, grain, leak (light-leak sweep in each dissolve; off by
 * default because the owner removed sun / light-leak washes from his films on 2026-11-01).
 */
const NIL = {
  grade: C.grade || 'sepia(.14) saturate(1.1) contrast(1.07) brightness(1.02)',
  push: C.push ?? .08,
  X: C.dissolve ?? .7,
  bar: C.letterbox ?? 150,
  leak: !!C.leak,
};

// a warm light sweep across the frame while two shots dissolve
function leak(k) {
  if (k <= 0 || k >= 1) return;
  const a = Math.sin(k * Math.PI), x = lerp(-500, W + 500, k);
  g.save();
  g.globalCompositeOperation = 'screen';
  const gr = g.createLinearGradient(x - 420, 0, x + 420, 0);
  gr.addColorStop(0, 'rgba(255,140,40,0)');
  gr.addColorStop(.5, `rgba(255,190,110,${.55 * a})`);
  gr.addColorStop(1, 'rgba(255,140,40,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, W, H);
  g.restore();
}

function nilTitle(t) {
  const T = C.title;
  if (!T || !T.text) return;
  const a0 = T.start ?? .9, a1 = T.end ?? 4.4;
  if (t < a0 || t > a1 + .2) return;
  const a = eo(seg(t, a0, a0 + 1.3)) * cl((a1 - t) / .6);
  g.save();
  g.globalAlpha = a;
  g.textAlign = 'center';
  g.direction = 'rtl';
  g.textBaseline = 'middle';
  g.shadowColor = 'rgba(0,0,0,.6)';
  g.shadowBlur = 30;
  const sc = 1.05 - .05 * eo(seg(t, a0, a1 - .4));
  g.translate(540, T.y || 900);
  g.scale(sc, sc);
  g.font = font(T.font || 'Ruqaa', T.size || 190);
  g.fillStyle = goldG(-120, 60);
  g.fillText(T.text, 0, 0, 1000);
  if (T.sub) {
    g.font = font('Tajawal', 54);
    g.fillStyle = '#fff';
    g.fillText(T.sub, 0, 150, 1000);
  }
  g.restore();
}

function nilEnd(t) {
  const E = C.end;
  if (!E || E.at == null || t <= E.at) return;
  const k = eo(seg(t, E.at, E.at + 1.2));
  if (E.title) {
    g.save();
    g.globalAlpha = k;
    g.textAlign = 'center';
    g.direction = 'rtl';
    g.shadowColor = 'rgba(0,0,0,.7)';
    g.shadowBlur = 26;
    g.font = font('Ruqaa', E.size || 150);
    g.fillStyle = goldG(820, 960);
    g.fillText(E.title, 540, 900 + (1 - k) * 20, 1000);
    g.restore();
  }
  if (E.sub) centerText(E.sub, 540, 1000, { size: 50, alpha: k, baseline: 'alphabetic' });
  credit(t, E.at + 1.0, 1500);
}

async function render(t) {
  g.fillStyle = '#000';
  g.fillRect(0, 0, W, H);
  if (S.length) {
    const i = shotIndex(t), s = S[i], lt = t - s.st, o = { filter: NIL.grade, push: NIL.push };
    if (i > 0 && lt < NIL.X) {
      await drawShot(S[i - 1], t, o);
      await drawShot(s, t, { ...o, alpha: eio(lt / NIL.X) });
      if (NIL.leak) leak(lt / NIL.X);
    } else await drawShot(s, t, o);
  }
  vignette(C.vignette ?? .5);
  const bar = lerp(0, NIL.bar, eo(seg(t, .2, 1.6)));
  if (bar > 0) {
    g.fillStyle = '#000';
    g.fillRect(0, 0, W, bar);
    g.fillRect(0, H - bar, W, bar);
  }
  nilTitle(t);
  specLines(t, 1620, 62);
  nilEnd(t);
  grain(t, C.grain ?? .04);
  fades(t);
  watermark();
}
boot(render);
