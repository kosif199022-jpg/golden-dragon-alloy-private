/* Mayar cinema engine: draws one frame of a film for time t on a 1080x1920 canvas.
   Layers: footage (pre-graded frames) or generated scenes -> transitions -> light -> typography -> grain/vignette.
   window.__kosif = { duration, seek(t) } is the contract with tools/render_html.cjs (seek driver). */
(() => {
  const SPEC = window.SPEC;
  const W = 1080, H = 1920, FPS = SPEC.fps || 30;
  const cv = document.getElementById('c');
  const g = cv.getContext('2d');

  // ---------- helpers
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  const ease = p => p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;      // easeInOutCubic
  const easeOut = p => 1 - Math.pow(1 - p, 3);
  const expoOut = p => p >= 1 ? 1 : 1 - Math.pow(2, -10 * p);
  const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';
  const arNum = n => Math.round(n).toLocaleString('en-US').replace(/\d/g, d => AR_DIGITS[d]).replace(/,/g, '٬');
  function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

  // ---------- frame cache
  const cache = new Map();
  function img(src) {
    if (cache.has(src)) return cache.get(src);
    const im = new Image();
    const p = new Promise((res, rej) => { im.onload = () => res(im); im.onerror = () => rej(new Error('missing ' + src)); });
    im.src = src;
    const entry = p.then(i => i.decode ? i.decode().then(() => i) : i);
    cache.set(src, entry);
    if (cache.size > 40) cache.delete(cache.keys().next().value);
    return entry;
  }
  function frameSrc(shot, local) {
    const sp = shot.speed || 1;
    let i = Math.floor(local * sp * FPS) + 1;
    i = Math.max(1, Math.min(shot.frames, i));
    return `${shot.dir}/${String(i).padStart(5, '0')}.jpg`;
  }

  // ---------- generated scenes
  const stars = (() => { const r = rng(7); return Array.from({ length: 1400 }, () => ({ x: r(), y: r(), z: r(), tw: r() * 6.28 })); })();
  function sceneStars(local, d, s) {
    // a sea of gold points (each one a reader) that converges into one light
    const conv = s.converge ? ease(clamp((local - (s.convergeAt || 0)) / (s.convergeDur || 2.5))) : 0;
    const grd = g.createRadialGradient(W / 2, H * 0.45, 50, W / 2, H * 0.5, H * 0.8);
    grd.addColorStop(0, '#13213f'); grd.addColorStop(1, '#03060d');
    g.fillStyle = grd; g.fillRect(0, 0, W, H);
    const drift = local * 12;
    g.globalCompositeOperation = 'lighter';
    for (const p of stars) {
      let x = p.x * W, y = ((p.y * H + drift * (0.3 + p.z)) % H);
      x = lerp(x, W / 2, conv); y = lerp(y, H * 0.45, conv);
      const a = (0.35 + 0.65 * Math.abs(Math.sin(p.tw + local * 1.7))) * Math.pow(1 - conv, 2);
      if (a < 0.01) continue; // stacked points would add up to a hard white block at the centre
      const r = 0.8 + p.z * 2.2;
      g.fillStyle = `rgba(255,${200 + p.z * 40 | 0},120,${a})`;
      g.beginPath(); g.arc(x, y, r, 0, 6.283); g.fill();
    }
    if (conv > 0) { // the one light
      const R = 40 + 260 * conv;
      const c = g.createRadialGradient(W / 2, H * 0.45, 0, W / 2, H * 0.45, R);
      c.addColorStop(0, `rgba(255,245,215,${conv})`); c.addColorStop(0.25, `rgba(255,210,120,${0.8 * conv})`); c.addColorStop(1, 'rgba(255,180,80,0)');
      g.fillStyle = c; g.beginPath(); g.arc(W / 2, H * 0.45, R, 0, 6.283); g.fill();
    }
    g.globalCompositeOperation = 'source-over';
  }
  function sceneEnd(local, d, s) {
    // deep night with a slow flag-coloured dawn rising from the bottom
    g.fillStyle = '#05070c'; g.fillRect(0, 0, W, H);
    const p = ease(clamp(local / Math.max(1, d - 0.5)));
    const y = lerp(H * 1.1, H * 0.55, p);
    const bands = [['#c8102e', 0], ['#f4f1ea', 0.33], ['#111111', 0.66]];
    g.globalCompositeOperation = 'lighter';
    const glow = g.createRadialGradient(W / 2, y, 0, W / 2, y, H * 0.9);
    glow.addColorStop(0, 'rgba(232,181,74,0.55)'); glow.addColorStop(0.4, 'rgba(200,16,46,0.18)'); glow.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = glow; g.fillRect(0, 0, W, H);
    g.globalCompositeOperation = 'source-over';
    // fine gold dust
    const r = rng(11);
    for (let i = 0; i < 260; i++) {
      const x = r() * W, yy = (r() * H - local * (20 + r() * 40) + H * 2) % H, a = 0.2 + 0.6 * r();
      g.fillStyle = `rgba(255,217,138,${a * 0.6})`; g.fillRect(x, yy, 2, 2);
    }
    void bands;
  }
  function sceneBlack() { g.fillStyle = '#000'; g.fillRect(0, 0, W, H); }

  // ---------- footage
  async function drawShot(shot, t, alpha = 1, extraScale = 1, blur = 0) {
    const local = t - shot.t, d = shot.d;
    g.save(); g.globalAlpha = alpha;
    if (shot.type === 'clip') {
      const im = await img(frameSrc(shot, Math.max(0, local)));
      const kb = shot.kb || {};
      const p = ease(clamp(local / d));
      const sc = lerp(kb.s0 || 1.0, kb.s1 || 1.06, p) * extraScale;
      const ox = lerp(kb.x0 || 0, kb.x1 || 0, p) * W, oy = lerp(kb.y0 || 0, kb.y1 || 0, p) * H;
      if (blur) g.filter = `blur(${blur}px)`;
      g.translate(W / 2 + ox, H / 2 + oy); g.scale(sc, sc);
      g.drawImage(im, -W / 2, -H / 2, W, H);
    } else if (shot.type === 'stars') sceneStars(local, d, shot);
    else if (shot.type === 'end') sceneEnd(local, d, shot);
    else sceneBlack();
    g.restore();
  }
  function shotAt(t) { let s = SPEC.shots[0]; for (const x of SPEC.shots) if (t >= x.t) s = x; return s; }
  function nextOf(s) { const i = SPEC.shots.indexOf(s); return SPEC.shots[i + 1]; }

  async function drawBase(t) {
    const cur = shotAt(t);
    const nxt = nextOf(cur), prv = SPEC.shots[SPEC.shots.indexOf(cur) - 1];
    // transition window around each cut: [cut - d/2, cut + d/2], type stored on the incoming shot
    const inc = (nxt && t > nxt.t - (nxt.tr?.d || 0) / 2) ? nxt : cur;
    const out = inc === cur ? prv : cur;
    const tr = inc.tr;
    if (tr && out && Math.abs(t - inc.t) < tr.d / 2) {
      const p = clamp((t - (inc.t - tr.d / 2)) / tr.d);
      if (tr.type === 'dissolve' || tr.type === 'leak') {
        await drawShot(out, t, 1); await drawShot(inc, t, ease(p));
      } else if (tr.type === 'zoom') {
        if (p < 0.5) await drawShot(out, t, 1, 1 + 0.35 * ease(p * 2), 14 * p * 2);
        else await drawShot(inc, t, 1, 1 + 0.25 * (1 - ease((p - 0.5) * 2)), 14 * (1 - (p - 0.5) * 2));
      } else if (tr.type === 'iris') {
        // shape morph: a disc grows from the centre crosshair carrying the next shot (flooded first, then eased in)
        await drawShot(out, t, 1, 1 + 0.06 * ease(p));
        const e = ease(p), R = e * Math.hypot(W, H) * 0.55;
        g.save(); g.beginPath(); g.arc(W / 2, H / 2, Math.max(1, R), 0, 6.283); g.clip();
        g.fillStyle = tr.flood || '#0b1020'; g.fillRect(0, 0, W, H);
        await drawShot(inc, t, clamp(e * 1.6), lerp(0.93, 1, e));
        g.restore();
        if (p < 0.98) { g.strokeStyle = `rgba(255,217,138,${0.8 * (1 - e)})`; g.lineWidth = 4; g.beginPath(); g.arc(W / 2, H / 2, Math.max(1, R), 0, 6.283); g.stroke(); }
      } else if (tr.type === 'flag') {
        await drawShot(out, t, 1);
        g.save(); const e = ease(p);
        g.beginPath(); g.rect(W - e * W * 1.4, 0, W * 1.4, H); g.clip();
        await drawShot(inc, t, 1); g.restore();
        const x = W - e * W * 1.4; // three flag bands lead the wipe
        const cols = ['#c8102e', '#f4f1ea', '#0b0b0b'];
        cols.forEach((c, i) => { g.fillStyle = c; g.fillRect(x - 70 * (i + 1), 0, 70, H); });
      } else { // cut (+ optional flash layer from the fx list)
        await drawShot(t < inc.t ? out : inc, t, 1);
      }
      if (tr.type === 'leak') leak(Math.sin(p * Math.PI), inc.t);
      return;
    }
    await drawShot(cur, t, 1);
  }

  // ---------- light
  function leak(a, seed) {
    if (a <= 0) return;
    const r = rng(Math.floor(seed * 100));
    g.save(); g.globalCompositeOperation = 'screen';
    for (let i = 0; i < 3; i++) {
      const x = r() * W, y = r() * H, R = 500 + r() * 700;
      const c = g.createRadialGradient(x, y, 0, x, y, R);
      c.addColorStop(0, `rgba(255,${120 + r() * 80 | 0},40,${0.75 * a})`); c.addColorStop(1, 'rgba(255,90,0,0)');
      g.fillStyle = c; g.fillRect(0, 0, W, H);
    }
    g.restore();
  }
  function flash(a) { if (a <= 0) return; g.save(); g.globalCompositeOperation = 'screen'; g.fillStyle = `rgba(255,248,235,${a})`; g.fillRect(0, 0, W, H); g.restore(); }

  // ---------- typography
  const FONTS = { ruqaa: 'Ruqaa', cairo: 'CairoBlack', cairo7: 'CairoBold', amiri: 'Amiri', messiri: 'Messiri', tajawal: 'Tajawal', kufi: 'Kufi', serif: 'InstrSerif' };
  function setFont(tx, size) { g.font = `${size}px "${FONTS[tx.font || 'cairo']}"`; }
  function fitSize(tx, text, size, maxW) { setFont(tx, size); let s = size; while (g.measureText(text).width > maxW && s > 20) { s -= 4; setFont(tx, s); } return s; }
  function scrim(y, h, a) {
    const c = g.createLinearGradient(0, y - h, 0, y + h);
    c.addColorStop(0, 'rgba(0,0,0,0)'); c.addColorStop(0.5, `rgba(0,0,0,${a})`); c.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = c; g.fillRect(0, y - h, W, h * 2);
  }
  function fillText(tx, text, x, y, color, glow) {
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.direction = 'rtl';
    if (tx.gold) {
      const m = g.measureText(text), hh = (tx.size || 120) * 0.7;
      const gr = g.createLinearGradient(0, y - hh, 0, y + hh);
      gr.addColorStop(0, '#FFF1C4'); gr.addColorStop(0.45, '#FFD98A'); gr.addColorStop(0.55, '#E8B54A'); gr.addColorStop(1, '#A8761F');
      color = gr; void m;
    }
    g.shadowColor = glow || 'rgba(0,0,0,0.65)'; g.shadowBlur = glow ? 40 : 24; g.shadowOffsetY = glow ? 0 : 4;
    g.fillStyle = color; g.fillText(text, x, y);
    g.shadowBlur = 0; g.shadowOffsetY = 0;
  }
  function drawText(tx, t) {
    const local = t - tx.t, d = tx.d;
    if (local < 0 || local > d) return;
    const fadeOut = tx.out === false ? 1 : clamp((d - local) / (tx.outDur || 0.45));
    const x = (tx.x ?? 0.5) * W, y = (tx.y ?? 0.5) * H;
    const color = tx.color || '#ffffff', glow = tx.glow;
    let size = tx.size || 110;
    if (tx.scrim) scrim(y, size * 1.4, tx.scrim * fadeOut);
    g.save();
    if (tx.anim === 'counter') {
      const p = expoOut(clamp(local / (tx.count || 2.2)));
      const text = arNum(lerp(tx.from || 0, tx.to, p));
      size = fitSize(tx, arNum(tx.to), size, W * 0.9);
      g.globalAlpha = clamp(local / 0.3) * fadeOut;
      fillText(tx, text, x, y, color, glow);
    } else if (tx.anim === 'big') { // payoff word: blur to sharp, small rise, a slow settle (no scale pop); leaves the same way
      const p = easeOut(clamp(local / (tx.in || 0.8)));
      const q = tx.out === false ? 0 : 1 - fadeOut;
      size = fitSize(tx, tx.text, size, W * 0.88);
      g.globalAlpha = p * fadeOut;
      g.translate(x, y - q * 30 + (1 - p) * 40); const s = lerp(tx.from || 1.04, 1, p); g.scale(s, s);
      g.filter = `blur(${((1 - p) + q) * 16}px)`;
      fillText(tx, tx.text, 0, 0, color, glow);
    } else if (tx.anim === 'karaoke') { // TYPE-17: a dim line whose words light up gold exactly when she says them
      size = fitSize(tx, tx.words.map(w => w.w).join(' '), size, W * 0.9);
      const gap = size * 0.28, ws = tx.words.map(w => w.w);
      const widths = ws.map(w => g.measureText(w).width);
      const total = widths.reduce((a, b) => a + b, 0) + gap * (ws.length - 1);
      const lineIn = easeOut(clamp(local / 0.5));
      let cx = x + total / 2;
      tx.words.forEach((w, i) => {
        const on = easeOut(clamp((t - w.s) / 0.18));
        g.save();
        g.globalAlpha = lineIn * fadeOut * (0.32 + 0.68 * on);
        g.filter = `blur(${(1 - lineIn) * 10}px)`;
        fillText(on > 0.5 ? { ...tx, gold: true } : tx, w.w, cx - widths[i] / 2, y - on * 6, on > 0.5 ? color : '#c9c2b4', on > 0.5 ? (tx.glow || 'rgba(232,181,74,0.45)') : null);
        g.restore();
        cx -= widths[i] + gap;
      });
    } else if (tx.anim === 'wipe') { // right-to-left reveal, follows Arabic reading direction
      size = fitSize(tx, tx.text, size, W * 0.9);
      const m = g.measureText(tx.text).width;
      const p = ease(clamp(local / (tx.in || 0.9)));
      g.globalAlpha = fadeOut;
      g.beginPath(); g.rect(x + m / 2 - m * p - 30, y - size, m * p + 60, size * 2); g.clip();
      fillText(tx, tx.text, x, y, color, glow);
    } else { // 'rise' (and 'stamp' = a quicker rise on a beat): word by word, blurred to sharp, small rise; leaves the same way
      const quick = tx.anim === 'stamp';
      size = fitSize(tx, tx.text, size, W * 0.9);
      const words = tx.text.split(' ');
      const gap = size * 0.28;
      const widths = words.map(w => g.measureText(w).width);
      const total = widths.reduce((a, b) => a + b, 0) + gap * (words.length - 1);
      const stag = tx.stagger ?? (quick ? 0.06 : 0.09), dur = quick ? 0.3 : 0.55, outDur = tx.outDur || 0.4;
      let cx = x + total / 2; // start at the right edge (Arabic reads right to left)
      words.forEach((w, i) => {
        const pin = easeOut(clamp((local - i * stag) / dur));
        const pout = tx.out === false ? 0 : easeOut(clamp((local - (d - outDur - (words.length - 1 - i) * stag * 0.5)) / outDur));
        const p = pin * (1 - pout);
        g.save();
        g.globalAlpha = p;
        g.filter = `blur(${(1 - pin) * 14 + pout * 10}px)`;
        const wx = cx - widths[i] / 2;
        fillText(tx, w, wx, y + (1 - pin) * 34 - pout * 24, color, glow);
        g.restore();
        cx -= widths[i] + gap;
      });
    }
    g.restore();
  }

  // ---------- finishing
  const grainTiles = [];
  for (let k = 0; k < 6; k++) {
    const c = document.createElement('canvas'); c.width = 270; c.height = 480;
    const cx = c.getContext('2d'), id = cx.createImageData(270, 480), r = rng(100 + k);
    for (let i = 0; i < id.data.length; i += 4) { const v = r() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
    cx.putImageData(id, 0, 0); grainTiles.push(c);
  }
  function finish(t) {
    const fx = SPEC.fx || {};
    // vignette
    const v = g.createRadialGradient(W / 2, H / 2, H * 0.32, W / 2, H / 2, H * 0.75);
    v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, `rgba(0,0,0,${fx.vignette ?? 0.55})`);
    g.fillStyle = v; g.fillRect(0, 0, W, H);
    // grain
    g.save(); g.globalAlpha = fx.grain ?? 0.05; g.globalCompositeOperation = 'overlay';
    g.imageSmoothingEnabled = false;
    g.drawImage(grainTiles[Math.floor(t * FPS) % grainTiles.length], 0, 0, W, H);
    g.restore();
    // fade from / to black at the film edges
    const fi = clamp(t / (fx.fadeIn ?? 0.6)), fo = clamp((SPEC.duration - t) / (fx.fadeOut ?? 1.2));
    const a = 1 - Math.min(fi, fo);
    if (a > 0) { g.fillStyle = `rgba(0,0,0,${a})`; g.fillRect(0, 0, W, H); }
  }

  async function render(t) {
    g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.filter = 'none';
    await drawBase(t);
    for (const f of (SPEC.flashes || [])) flash(Math.max(0, 1 - Math.abs(t - f.t) / (f.d || 0.25)) * (f.a ?? 0.9));
    for (const l of (SPEC.leaks || [])) if (t >= l.t && t <= l.t + l.d) leak(Math.sin(((t - l.t) / l.d) * Math.PI) * (l.a ?? 0.7), l.t);
    for (const tx of SPEC.texts) drawText(tx, t);
    finish(t);
  }

  // preload fonts, then expose the seek contract
  const faces = [['Ruqaa', 'ArefRuqaa-Bold.ttf'], ['CairoBlack', 'Cairo-900.ttf'], ['CairoBold', 'Cairo-700.ttf'], ['Amiri', 'Amiri-Bold.ttf'],
    ['Messiri', 'ElMessiri-700.ttf'], ['Tajawal', 'Tajawal-Black.ttf'], ['Kufi', 'ReemKufi-700.ttf'], ['InstrSerif', 'InstrumentSerif-Italic.ttf']];
  // fonts are embedded as base64 (fonts.js): Chromium refuses FontFace fetches from file://
  const ready = Promise.all(faces.map(([n, f]) => {
    const bin = Uint8Array.from(atob(window.FONTDATA[f]), ch => ch.charCodeAt(0));
    return new FontFace(n, bin.buffer).load().then(ff => document.fonts.add(ff));
  }));
  window.__kosifReady = ready;
  window.__kosif = { duration: SPEC.duration, seek: async t => { await ready; await render(t); } };
  // preview: ?t=12.5 draws one frame
  const q = new URLSearchParams(location.search).get('t');
  if (q !== null) ready.then(() => render(parseFloat(q)));
})();
