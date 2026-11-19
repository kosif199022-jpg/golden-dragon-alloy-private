/* chapters: an organised film (first delivered 2026-11-06, after the owner asked for clear order).
 * Full-bleed footage with short dissolves (longer next to b-roll), and every text type in one fixed slot:
 * chapter title at the top, her words at the bottom (CFG.lines, subtitle style), a Quran verse layer in
 * ScheherazadeNew-Bold (CFG.verses; ﴿ ﴾ drawn alone, outside the RTL line, AUDIO_SONGS_QURAN.md §19), and optional
 * gold lyric band (CFG.lyrics), top label cards (CFG.labels) and TV lower-thirds (CFG.lowers), then the end card.
 * Numerals are off unless CFG.numbers === true: the owner turned down numbered chapter cards («شرح للطلاب يتقول
 * الفصل الأول», 2026-11-08); the top slot stays.
 * CFG knobs: dissolve, dissolve_broll, push, numbers, vignette, grain.
 */
const GOLDC = '#e9c46a', RED = '#c8102e';
const LOOK_CH = 'contrast(1.06) saturate(1.05)';
const XD = C.dissolve ?? .16, XB = C.dissolve_broll ?? .5;

// how far a text item is into its life, with fades in and out
const life = (lt, d, i = .35, o = .35) => cl(lt / i) * cl((d - lt) / o);

async function chShot(s, t, a) {
  const p = ease(cl((t - s.st) / (s.en - s.st + .5)));
  await drawShot(s, t, { filter: LOOK_CH, push: C.push ?? .06, prog: p, alpha: a });
}

function chTitle(t) {
  const T = C.title;
  if (!T || !T.text) return;
  const a0 = T.start ?? .3, a1 = T.end ?? 4.3;
  if (t < a0 - .3 || t > a1 + .1) return;
  const a = eo(cl((t - a0) / 1.1)) * cl((a1 - t) / .5);
  g.save();
  g.globalAlpha = a;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  const s = 1.06 - .06 * eo(cl((t - a0 + .3) / 2.5));
  g.translate(540, T.y || 880);
  g.scale(s, s);
  g.shadowColor = 'rgba(0,0,0,.65)';
  g.shadowBlur = 30;
  g.font = font(T.font || 'Ruqaa', T.size || 210);
  g.fillStyle = goldG(-200, 0, GOLD_SOFT);
  g.fillText(T.text, 0, T.sub ? -90 : 0, 1000);
  if (T.sub) {
    g.font = font('Ruqaa', 110);
    g.fillStyle = '#fff';
    g.globalAlpha = a * eo(cl((t - a0 - .8) / .8));
    g.fillText(T.sub, 0, 90, 1000);
  }
  g.restore();
}

// chapter title: one fixed place at the top, gold numeral, white title, a gold line that draws in, then it lifts away
function chapter(c, t) {
  const lt = t - c.s, d = c.d || 2.6;
  if (lt < 0 || lt > d) return;
  const a = cl(lt / .35) * cl((d - lt) / .45);
  const y = 300 - (1 - eo(cl(lt / .5))) * 24;
  g.save();
  g.globalAlpha = a;
  g.direction = 'rtl';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.shadowColor = 'rgba(0,0,0,.75)';
  g.shadowBlur = 18;
  if (c.n && C.numbers === true) {
    g.font = font('Ruqaa', 96);
    g.fillStyle = goldG(y - 110, y - 10, GOLD_SOFT);
    g.fillText(c.n, 540, y - 62);
  }
  g.font = font('Tajawal', 54);
  g.fillStyle = '#fff';
  g.fillText(c.t, 540, y + 26, 1000);
  const w = Math.min(g.measureText(c.t).width + 80, 900) * eo(cl((lt - .15) / .7));
  g.shadowBlur = 0;
  g.strokeStyle = 'rgba(233,196,106,.9)';
  g.lineWidth = 3;
  g.beginPath();
  g.moveTo(540 - w / 2, y + 76);
  g.lineTo(540 + w / 2, y + 76);
  g.stroke();
  g.restore();
}

// her words as subtitles in the bottom slot
function subtitle(q, t) {
  const lt = t - q.s, d = q.e - q.s;
  if (lt < 0 || lt > d) return;
  centerText(q.t, 540, q.y || 1580, { size: q.size || 50, family: q.font, alpha: life(lt, d, .2, .2),
    shadow: 'rgba(0,0,0,.95)', blur: 14, fill: q.gold ? goldG(1550, 1610, GOLD_SOFT) : '#fff' });
}

// Quran verse: ScheherazadeNew-Bold (Amiri lifts the dagger alif U+0670 until it reads «١»), white with a soft gold
// glow, lines split by '|'. ﴿ (U+FD3F) sits right of the first line and ﴾ (U+FD3E) left of the last, each drawn on its
// own with direction 'ltr' at a measured x, never inside the RTL line. The reference (q.u) follows in gold, no brackets.
function verse(q, t) {
  const lt = t - q.s, d = q.e - q.s;
  if (lt < 0 || lt > d) return;
  const a = cl(lt / .8) * cl((d - lt) / .6);
  g.save();
  g.textBaseline = 'middle';
  const bg = g.createLinearGradient(0, 1240, 0, H);
  bg.addColorStop(0, 'rgba(0,0,0,0)');
  bg.addColorStop(.45, 'rgba(0,0,0,.55)');
  bg.addColorStop(1, 'rgba(0,0,0,.7)');
  g.globalAlpha = a;
  g.fillStyle = bg;
  g.fillRect(0, 1240, W, H - 1240);
  const L = String(q.t).split('|');
  const top = 1470 - Math.max(0, L.length - 2) * 104;   // 3+ lines start higher: the reference stays at y <= 1700
  g.font = font('Scheherazade', 60);
  g.shadowColor = 'rgba(233,196,106,.45)';
  g.shadowBlur = 22;
  g.fillStyle = '#fff';
  L.forEach((ln, i) => {
    const b = eo(cl((lt - .3 - i * 1.2) / .9));
    const y = top + i * 104 + (1 - b) * 14;
    g.globalAlpha = a * b;
    g.direction = 'rtl';
    g.textAlign = 'center';
    g.fillText(ln, 540, y, 940);
    const half = Math.min(940, g.measureText(ln).width) / 2;
    g.direction = 'ltr';
    if (i === 0) { g.textAlign = 'left'; g.fillText('\uFD3F', 540 + half + 12, y); }
    if (i === L.length - 1) { g.textAlign = 'right'; g.fillText('\uFD3E', 540 - half - 12, y); }
  });
  if (q.u) {
    g.globalAlpha = a * eo(cl((lt - 1.6) / .8));
    g.shadowBlur = 8;
    g.font = font('Scheherazade', 34);
    g.fillStyle = GOLDC;
    g.direction = 'rtl';
    g.textAlign = 'center';
    g.fillText(q.u, 540, top + L.length * 104 + 6, 1000);
  }
  g.restore();
}

// gold Ruqaa lyric band: dark strip, gold line of text, a gold hairline that grows from the centre
function lyric(q, t) {
  const lt = t - q.s, d = q.e - q.s;
  if (lt < 0 || lt > d) return;
  const y = q.y || 1560;
  g.save();
  g.globalAlpha = life(lt, d, .3, .3);
  const bg = g.createLinearGradient(0, y - 80, 0, y + 80);
  bg.addColorStop(0, 'rgba(0,0,0,0)');
  bg.addColorStop(.25, 'rgba(0,0,0,.62)');
  bg.addColorStop(.75, 'rgba(0,0,0,.62)');
  bg.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = bg;
  g.fillRect(0, y - 80, W, 160);
  g.font = font('Ruqaa', 62);
  g.direction = 'rtl';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  const tw = Math.min(g.measureText(q.t).width, 980), wv = eo(cl(lt / .6));
  g.strokeStyle = 'rgba(233,196,106,.85)';
  g.lineWidth = 2;
  g.beginPath();
  g.moveTo(540 - tw / 2 * wv - 40, y + 62);
  g.lineTo(540 + tw / 2 * wv + 40, y + 62);
  g.stroke();
  g.shadowColor = 'rgba(0,0,0,.8)';
  g.shadowBlur = 12;
  g.fillStyle = goldG(y - 35, y + 35, GOLD_SOFT);
  g.fillText(q.t, 540, y + (1 - eo(cl(lt / .5))) * 14, 980);
  g.restore();
}

// label card at the top: dark box, red bar on the right, white title and a gold line under it
function labelCard(q, t) {
  const lt = t - q.s, d = q.e - q.s;
  if (lt < 0 || lt > d) return;
  g.save();
  g.globalAlpha = life(lt, d, .4, .4);
  g.direction = 'rtl';
  g.textBaseline = 'middle';
  g.font = font('Tajawal', 46);
  const w1 = g.measureText(q.t).width;
  g.font = font('Tajawal', 30);
  const w2 = q.u ? g.measureText(q.u).width : 0;
  const bw = Math.min(1000, Math.max(w1, w2) + 90), bh = q.u ? 128 : 90, x = 540 - bw / 2;
  const y = 250 - (1 - eo(cl(lt / .5))) * 20;
  g.shadowColor = 'rgba(0,0,0,.5)';
  g.shadowBlur = 24;
  g.fillStyle = 'rgba(18,16,14,.78)';
  rr(x, y, bw, bh, 10);
  g.fill();
  g.shadowBlur = 0;
  g.fillStyle = RED;
  g.fillRect(x + bw - 10, y + 12, 6, bh - 24);
  g.strokeStyle = 'rgba(233,196,106,.55)';
  g.lineWidth = 1.5;
  rr(x, y, bw, bh, 10);
  g.stroke();
  g.textAlign = 'center';
  g.font = font('Tajawal', 46);
  g.fillStyle = '#fff';
  g.fillText(q.t, 540, y + 48, bw - 60);
  if (q.u) {
    g.font = font('Tajawal', 30);
    g.fillStyle = GOLDC;
    g.fillText(q.u, 540, y + 96, bw - 60);
  }
  g.restore();
}

// TV lower-third: small gold kicker with hairlines, a light glass card with the name, a flag strip on the right
function lowerThird(q, t) {
  const lt = t - q.s, d = q.e - q.s;
  if (lt < 0 || lt > d) return;
  const s = eo(cl(lt / .6)), y = 1330;
  g.save();
  g.globalAlpha = life(lt, d, .45, .4);
  g.direction = 'rtl';
  g.textBaseline = 'middle';
  g.textAlign = 'center';
  g.font = font('Tajawal', 52);
  const w = Math.min(1000, Math.max(g.measureText(q.t).width, 360) + 110), ww = w * (.85 + .15 * s), x = 540 - ww / 2;
  if (q.u) {
    g.font = font('Tajawal', 28);
    g.fillStyle = GOLDC;
    g.fillText(q.u, 540, y - 40, 900);
    const uw = Math.min(g.measureText(q.u).width, 900) / 2 + 18;
    g.strokeStyle = 'rgba(233,196,106,.7)';
    g.lineWidth = 2;
    g.beginPath();
    g.moveTo(540 - ww / 2, y - 40);
    g.lineTo(540 - uw, y - 40);
    g.moveTo(540 + uw, y - 40);
    g.lineTo(540 + ww / 2, y - 40);
    g.stroke();
  }
  g.shadowColor = 'rgba(0,0,0,.45)';
  g.shadowBlur = 20;
  g.fillStyle = 'rgba(235,238,240,.88)';
  rr(x, y - 8, ww, 88, 14);
  g.fill();
  g.shadowBlur = 0;
  [RED, '#fff', '#111'].forEach((c, i) => { g.fillStyle = c; g.fillRect(x + ww - 56, y + 14 + i * 12, 34, 12); });
  g.font = font('Tajawal', 50);
  g.fillStyle = '#1a1a1a';
  g.fillText(q.t, 540 - 14, y + 38, ww - 120);
  g.restore();
}

function chEnd(t) {
  const E = C.end;
  if (!E || E.at == null || t < E.at) return;
  const lt = t - E.at;
  dim(.6 * cl(lt / 1.2));
  g.save();
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.direction = 'rtl';
  let a = eo(cl((lt - .3) / 1));
  g.globalAlpha = a;
  g.shadowColor = 'rgba(0,0,0,.7)';
  g.shadowBlur = 26;
  if (E.title) {
    g.font = font('Ruqaa', E.size || 150);
    g.fillStyle = goldG(760, 900, GOLD_SOFT);
    g.fillText(E.title, 540, 830 + (1 - a) * 20, 1000);
  }
  a = eo(cl((lt - 1) / .8));
  g.globalAlpha = a;
  g.shadowBlur = 12;
  if (E.sub) {
    g.font = font('Tajawal', 40);
    g.fillStyle = '#fff';
    g.fillText(E.sub, 540, 950, 1000);
  }
  if (E.sub2) {
    g.font = font('Ruqaa', 38);
    g.fillStyle = GOLDC;
    g.fillText(E.sub2, 540, 1020, 1000);
  }
  if (E.flag) {
    g.fillStyle = RED; g.fillRect(450, 1066, 60, 6);
    g.fillStyle = '#fff'; g.fillRect(510, 1066, 60, 6);
    g.fillStyle = '#111'; g.fillRect(570, 1066, 60, 6);
  }
  g.restore();
  credit(t, E.at + 2, 1420, { sizes: [42, 32], gap: 60, baseline: 'middle' });
}

async function render(t) {
  g.fillStyle = '#000';
  g.fillRect(0, 0, W, H);
  if (S.length) {
    const i = shotIndex(t), s = S[i], lt = t - s.st;
    const xd = i > 0 && (s.broll || S[i - 1].broll) ? XB : XD;
    if (i > 0 && lt < xd) {
      await chShot(S[i - 1], t, 1);
      await chShot(s, t, ease(lt / xd));
    } else await chShot(s, t, 1);
  }
  vignette(C.vignette ?? .42, 520);
  grain(t, C.grain ?? .03);
  chTitle(t);
  for (const c of C.chapters || []) chapter(c, t);
  for (const q of C.lines || []) subtitle(q, t);
  for (const q of C.verses || []) verse(q, t);
  for (const q of C.lyrics || []) lyric(q, t);
  for (const q of C.labels || []) labelCard(q, t);
  for (const q of C.lowers || []) lowerThird(q, t);
  chEnd(t);
  fades(t, .4, .6, .9);
  watermark();
}
boot(render);
