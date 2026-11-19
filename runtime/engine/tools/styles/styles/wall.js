/* wall: a living wall of looping tiles (first used for «حلوة يا بلدي», 2026-11-08). The camera flies over the wall,
 * dives into one hero tile until it fills the frame, holds, rises back out and travels to the next hero. It ends
 * pulled back on the whole wall, under the end title.
 * CFG: tiles (small looping frame folders, row-major), heroes ({i: tile, a: dive in, b: hold end, s: full-size shot}),
 * cols, loop (tile loop length in s), vignette, grain.
 */
const TW = 340, TH = 604, GAP = 30, COLS = Math.max(1, C.cols || 3);
const TILES = C.tiles || [], HER = C.heroes || [], LOOP = C.loop || 2.9;
const ROWS = Math.max(1, Math.ceil(TILES.length / COLS));
const WALLW = COLS * (TW + GAP) - GAP, WALLH = ROWS * (TH + GAP) - GAP;
const FULL = W / TW;                                   // zoom at which one tile fills the frame
const ZFIT = Math.min(H * .99 / WALLH, W * .99 / WALLW); // zoom that shows the whole wall
const tileXY = (i) => ({ x: (i % COLS) * (TW + GAP) + TW / 2, y: Math.floor(i / COLS) * (TH + GAP) + TH / 2 });

// camera keys [t, x, y, zoom]; eased between, each move one curve
const K = [];
(function keys() {
  const h = HER.map((e) => ({ ...e, ...tileXY(e.i) }));
  if (!h.length) {
    K.push([0, WALLW / 2, WALLH / 2, ZFIT * 1.1], [DUR, WALLW / 2, WALLH / 2, ZFIT]);
    return;
  }
  K.push([0, h[0].x, h[0].y, FULL * 1.02], [h[0].b, h[0].x, h[0].y, FULL]);
  for (let j = 1; j < h.length; j++) {
    const p = h[j - 1], q = h[j], mid = (p.b + q.a) / 2;
    K.push([mid, (p.x + q.x) / 2, (p.y + q.y) / 2, Math.max(.92, ZFIT)]);
    K.push([q.a + 2.2, q.x, q.y, FULL]);
    K.push([q.b, q.x, q.y, FULL * 1.03]);
  }
  const last = h[h.length - 1];
  K.push([last.b + 2.6, WALLW / 2, WALLH / 2, ZFIT * 1.1], [Math.max(DUR, last.b + 2.7), WALLW / 2, WALLH / 2, ZFIT]);
  for (let i = 1; i < K.length; i++) K[i][0] = Math.max(K[i][0], K[i - 1][0]);  // keep key times in order
})();

function cam(t) {
  const i = K.findIndex((k) => k[0] > t);
  if (i < 0) return K[K.length - 1].slice(1);
  if (i === 0) return K[0].slice(1);
  const a = K[i - 1], b = K[i], e = eio(seg(t, a[0], b[0]));
  // zoom eased in log space so the dive feels even
  return [lerp(a[1], b[1], e), lerp(a[2], b[2], e), Math.exp(lerp(Math.log(a[3]), Math.log(b[3]), e))];
}

// a hero tile shows full-size frames once the camera is close; other tiles loop, each at its own offset
async function tileImg(i, t, z) {
  const hero = HER.find((e) => e.i === i && t >= e.a - .2 && t <= e.b + 2);
  if (hero && z > 1.6) return frameOf(hero.s, cl(t, hero.s.st, hero.s.en), 'H' + i);
  const s = TILES[i];
  return frameOf({ ...s, st: 0 }, (t + i * .37) % LOOP, 'T' + i);
}

function wallEnd(t) {
  const E = C.end;
  if (!E || E.at == null || t <= E.at) return;
  const k = eo(seg(t, E.at, E.at + 1.4));
  dim(.62 * k, '5,6,12');
  g.save();
  g.globalAlpha = k;
  g.textAlign = 'center';
  g.direction = 'rtl';
  g.shadowColor = 'rgba(0,0,0,.7)';
  g.shadowBlur = 26;
  if (E.title) {
    g.font = font('Ruqaa', E.size || 160);
    g.fillStyle = goldG(800, 960);
    g.fillText(E.title, 540, 900 + (1 - k) * 24, 1000);
  }
  if (E.sub) {
    g.font = font('Tajawal', 50);
    g.fillStyle = '#fff';
    g.fillText(E.sub, 540, 1010, 1000);
  }
  g.restore();
  credit(t, E.at + 1.4, 1500);
}

async function render(t) {
  const bg = g.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, '#0d1424');
  bg.addColorStop(1, '#1d1206');
  g.fillStyle = bg;
  g.fillRect(0, 0, W, H);
  const [cx, cy, z] = cam(t);
  for (let i = 0; i < TILES.length; i++) {
    const p = tileXY(i), sx = 540 + (p.x - cx) * z, sy = 960 + (p.y - cy) * z, w = TW * z, h = TH * z;
    if (sx + w / 2 < -50 || sx - w / 2 > W + 50 || sy + h / 2 < -50 || sy - h / 2 > H + 50) continue;
    const im = await tileImg(i, t, z), r = Math.min(26, 18 * z);
    g.save();
    rr(sx - w / 2, sy - h / 2, w, h, r);
    g.shadowColor = 'rgba(0,0,0,.55)';
    g.shadowBlur = 30;
    g.fillStyle = '#000';
    g.fill();
    g.shadowBlur = 0;
    g.clip();
    if (im) {
      const k = Math.max(w / im.width, h / im.height), iw = im.width * k, ih = im.height * k;
      g.filter = 'saturate(1.06) contrast(1.05)';
      g.drawImage(im, sx - iw / 2, sy - ih * (TILES[i].fy ?? .5), iw, ih);
    }
    // tiles away from the one the camera dives into sit a little darker, so the eye stays centred
    const d = Math.hypot(sx - 540, sy - 960) / 900;
    g.filter = 'none';
    g.fillStyle = `rgba(5,8,16,${cl(d * .55, 0, .55)})`;
    g.fillRect(sx - w / 2, sy - h / 2, w, h);
    g.restore();
    g.save();
    rr(sx - w / 2, sy - h / 2, w, h, r);
    g.strokeStyle = 'rgba(233,196,106,.35)';
    g.lineWidth = Math.max(1, 1.5 * z / 2);
    g.stroke();
    g.restore();
  }
  vignette(C.vignette ?? .5);
  specLines(t, 1640, 66);
  wallEnd(t);
  grain(t, C.grain ?? .03);
  fades(t);
  watermark();
}
boot(render);
