/* Maven Reels kit. (c) 2026 Maven, @maven.iqq / maveniqq. See rights/MAVEN-RIGHTS.txt
   A reel is one HTML page. Everything on it is drawn by this kit (DOM + SVG) and moved by one clock:
   reel.seek(t) puts every element where it must be at second t. render.mjs calls seek for every frame.
   Read references/kit.md before writing a reel. */
(function () {
  "use strict";
  const R = {};
  const NS = "http://www.w3.org/2000/svg";
  /* fonts ship with the skill: assets/fonts next to this kit folder */
  const KIT = document.currentScript ? document.currentScript.src.replace(/[^/]*$/, "") : "";
  const fontCss = document.createElement("style");
  fontCss.textContent = [["Lalezar", "Lalezar-Regular.ttf", 400], ["IBM Plex Sans Arabic", "IBMPlexSansArabic-Regular.ttf", 400],
    ["IBM Plex Sans Arabic", "IBMPlexSansArabic-Medium.ttf", 500], ["IBM Plex Sans Arabic", "IBMPlexSansArabic-SemiBold.ttf", 600]]
    .map(([f, file, w]) => `@font-face{font-family:'${f}';src:url('${KIT}../assets/fonts/${file}');font-weight:${w}}`).join("");
  document.head.appendChild(fontCss);

  /* ---------- maths ---------- */
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  const ease = {
    linear: p => p,
    in: p => p * p * p,
    out: p => 1 - Math.pow(1 - p, 3),
    inOut: p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    back: p => { const c = 1.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); },
    soft: p => 1 - Math.pow(1 - p, 5),
  };
  /* keyframes: k(t, [[t0, v0], [t1, v1, "back"], ...]) -> value. v can be a number or an array of numbers.
     The easing name on a key is used on the way INTO that key (default inOut). */
  function k(t, keys, fallback) {
    if (!keys || !keys.length) return fallback;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t1, v1, e] = keys[i];
      if (t <= t1) {
        const [t0, v0] = keys[i - 1];
        const p = (ease[e || "inOut"] || ease.inOut)(clamp((t - t0) / Math.max(t1 - t0, 1e-6)));
        return Array.isArray(v0) ? v0.map((a, j) => lerp(a, v1[j], p)) : lerp(v0, v1, p);
      }
    }
    return keys[keys.length - 1][1];
  }
  /* 0 -> 1 with a springy overshoot, starting at t0 */
  const pop = (t, t0, d = .38) => (t < t0 ? 0 : ease.back(clamp((t - t0) / d)));
  const fade = (t, t0, d = .25) => clamp((t - t0) / d);
  /* small repeatable wobble, same every render */
  const wob = (t, speed = 1, seed = 0) => Math.sin(t * 6.283 * speed + seed * 12.9898) * .5 + Math.sin(t * 3.7 * speed + seed * 4.1) * .5;
  Object.assign(R, { clamp, lerp, ease, k, pop, fade, wob });

  /* ---------- DOM helpers ---------- */
  function el(tag, attrs = {}, parent) {
    const svgTag = /^(svg|g|path|rect|circle|ellipse|line|polygon|polyline|defs|linearGradient|radialGradient|stop|text|filter|feGaussianBlur|feOffset|feMerge|feMergeNode|clipPath|use)$/.test(tag);
    const e = svgTag ? document.createElementNS(NS, tag) : document.createElement(tag);
    for (const [a, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (a === "style" && typeof v === "object") Object.assign(e.style, v);
      else if (a === "html") e.innerHTML = v;
      else if (a === "text") e.textContent = v;
      else e.setAttribute(a, v);
    }
    if (parent) parent.appendChild(e);
    return e;
  }
  /* a block of SVG markup in a box: svg(parent, w, h, '<rect .../>', {x, y}) */
  function svg(parent, w, h, inner, at = {}) {
    const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, style: { position: "absolute", left: (at.x || 0) + "px", top: (at.y || 0) + "px", overflow: "visible" } }, parent);
    s.innerHTML = inner;
    return s;
  }
  function box(parent, x, y, w, h, style = {}) {
    return el("div", { style: { position: "absolute", left: x + "px", top: y + "px", width: w + "px", height: h + "px", ...style } }, parent);
  }
  Object.assign(R, { el, svg, box });

  /* shaded colour helpers for the soft clay look */
  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const f = amt < 0 ? 0 : 255, p = Math.abs(amt);
    r = Math.round((f - r) * p + r); g = Math.round((f - g) * p + g); b = Math.round((f - b) * p + b);
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }
  let gid = 0;
  /* vertical clay gradient id for a colour, defined once in the shared <defs> */
  function clay(hex, dir = "v") {
    const id = "c" + (gid++);
    const d = R._defs;
    const g = el("linearGradient", dir === "v" ? { id, x1: 0, y1: 0, x2: 0, y2: 1 } : { id, x1: 0, y1: 0, x2: 1, y2: 0 }, d);
    el("stop", { offset: "0", "stop-color": shade(hex, .22) }, g);
    el("stop", { offset: ".55", "stop-color": hex }, g);
    el("stop", { offset: "1", "stop-color": shade(hex, -.22) }, g);
    return `url(#${id})`;
  }
  Object.assign(R, { shade, clay });

  /* ---------- the reel ---------- */
  R.reel = function (opt = {}) {
    const W = opt.w || 1080, H = opt.h || 1920;
    document.documentElement.style.cssText = `margin:0;background:#000`;
    document.body.style.cssText = `margin:0;width:${W}px;height:${H}px;overflow:hidden;background:${opt.bg || "#000"}`;
    const stage = box(document.body, 0, 0, W, H, { overflow: "hidden", direction: opt.lang === "ar" ? "rtl" : "ltr" });
    stage.className = "stage";
    const defsSvg = el("svg", { width: 0, height: 0, style: { position: "absolute" } }, document.body);
    R._defs = el("defs", {}, defsSvg);
    R._defs.innerHTML = `<filter id="soft" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur in="SourceAlpha" stdDeviation="6"/><feOffset dy="8"/><feComponentTransfer><feFuncA type="linear" slope=".28"/></feComponentTransfer><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
    const updaters = [];
    const reel = {
      W, H, stage, lang: opt.lang || "ar", fps: opt.fps || 30, duration: opt.duration || 10,
      cues: [],                         // [{t, kind, note}] sound cues, read by render.mjs --cues
      on(fn) { updaters.push(fn); return fn; },
      seek(t) { for (const f of updaters) f(t); },
      cue(t, kind, note) { this.cues.push({ t: +t.toFixed(3), kind, note: note || "" }); },
    };
    /* render.mjs waits for this: fonts loaded and every element built */
    reel.ready = () => Promise.all([document.fonts.load("100px Lalezar"), document.fonts.load("600 40px 'IBM Plex Sans Arabic'"), document.fonts.ready]);
    window.reel = reel;
    return reel;
  };

  /* ---------- camera: a world bigger than the screen, moved by keyframes ---------- */
  R.world = function (reel, w = reel.W, h = reel.H) {
    const outer = box(reel.stage, 0, 0, reel.W, reel.H);
    const inner = box(outer, 0, 0, w, h, { transformOrigin: "0 0" });
    const cam = { el: inner, keys: [[0, [w / 2, h / 2, 1]]], shake: [] };
    /* cam.to(t, cx, cy, zoom, ease) : at time t the screen centre looks at (cx, cy) with this zoom */
    cam.to = (t, cx, cy, z = 1, e) => { cam.keys.push([t, [cx, cy, z], e]); cam.keys.sort((a, b) => a[0] - b[0]); return cam; };
    cam.punch = (t, amt = .04, d = .35) => { cam.shake.push([t, amt, d]); return cam; };
    reel.on(t => {
      let [cx, cy, z] = k(t, cam.keys);
      for (const [t0, a, d] of cam.shake) if (t >= t0 && t < t0 + d) z *= 1 + a * Math.sin(Math.PI * (t - t0) / d);
      const drift = 1 + .004 * Math.sin(t * .9);                     // never fully still
      z *= drift;
      inner.style.transform = `translate(${reel.W / 2 - cx * z}px, ${reel.H / 2 - cy * z}px) scale(${z})`;
    });
    return cam;
  };

  /* anything can be animated with keyframes on x, y, scale, rot, opacity:
     R.anim(reel, element, {x:[[t,v]...], y:..., s:..., r:..., o:...}, {ox, oy}) */
  R.anim = function (reel, node, keys, origin = {}) {
    node.style.transformOrigin = `${origin.ox ?? "50%"} ${origin.oy ?? "100%"}`;
    reel.on(t => {
      const x = k(t, keys.x, 0), y = k(t, keys.y, 0), s = k(t, keys.s, 1), r = k(t, keys.r, 0), o = k(t, keys.o, 1);
      node.style.transform = `translate(${x}px,${y}px) rotate(${r}deg) scale(${s})`;
      node.style.opacity = o;
      node.style.visibility = o <= 0.001 || s <= 0.001 ? "hidden" : "inherit";
    });
    return node;
  };
  /* build-in: element drops from above and lands with a squash, at t0 */
  R.drop = function (reel, node, t0, opt = {}) {
    const h = opt.height ?? 160, d = opt.d ?? .45;
    node.style.transformOrigin = "50% 100%";
    reel.on(t => {
      if (t < t0) { node.style.visibility = "hidden"; return; }
      node.style.visibility = "inherit";
      const p = clamp((t - t0) / d);
      const land = t - t0 - d;
      const sq = land > 0 && land < .25 ? Math.sin(Math.PI * land / .25) * .08 : 0;
      node.style.transform = `translateY(${-h * Math.pow(1 - p, 2)}px) scale(${1 + sq},${1 - sq})`;
      node.style.opacity = clamp(p * 3);
    });
    reel.cue(t0 + d, "land", opt.note);
    return node;
  };
  /* build-in: element pops from nothing at t0 */
  R.popIn = function (reel, node, t0, opt = {}) {
    node.style.transformOrigin = opt.origin || "50% 100%";
    reel.on(t => {
      const s = pop(t, t0, opt.d ?? .38);
      const out = opt.out != null ? 1 - ease.in(clamp((t - opt.out) / .25)) : 1;
      node.style.transform = `scale(${s * out})`;
      node.style.visibility = s * out <= 0.001 ? "hidden" : "inherit";
    });
    if (opt.sound !== false) reel.cue(t0, "pop", opt.note);
    return node;
  };

  /* ---------- scenery ---------- */
  R.sky = function (reel, parent, opt = {}) {
    const w = opt.w || reel.W, h = opt.h || reel.H;
    const top = opt.top || "#8cc6ec", bottom = opt.bottom || "#e4f3fb";
    const sky = box(parent, opt.x || 0, opt.y || 0, w, h, { background: `linear-gradient(${top}, ${bottom})` });
    if (opt.night) {                       // [[t, 0..1]] how dark the sky is
      const dark = box(sky, 0, 0, w, h, { background: `linear-gradient(#0f1d3d, #3c4f86 70%, #f2a46b)` });
      reel.on(t => { dark.style.opacity = k(t, opt.night, 0); });
    }
    const clouds = [];
    const n = opt.clouds ?? Math.round(w / 260);
    for (let i = 0; i < n; i++) {
      const cw = 110 + ((i * 53) % 90), cx = (i * 397) % w, cy = 60 + ((i * 131) % Math.max(h * .3, 100));
      const c = svg(sky, cw, cw * .5, `<g filter="url(#soft)" opacity=".95"><ellipse cx="${cw * .5}" cy="${cw * .34}" rx="${cw * .48}" ry="${cw * .16}" fill="#fff"/><circle cx="${cw * .38}" cy="${cw * .24}" r="${cw * .17}" fill="#fff"/><circle cx="${cw * .6}" cy="${cw * .2}" r="${cw * .21}" fill="#fff"/></g>`, { x: cx, y: cy });
      clouds.push([c, cx, 8 + (i % 3) * 5]);
    }
    reel.on(t => { for (const [c, x0, sp] of clouds) c.style.left = (((x0 + t * sp) % (w + 300)) - 150) + "px"; });
    return sky;
  };
  R.skyline = function (parent, x, y, w, opt = {}) {
    const col = opt.color || "#c9dcea", n = Math.round(w / 90);
    let s = "";
    for (let i = 0; i < n; i++) {
      const bh = 160 + ((i * 97) % 220), bw = 70 + ((i * 37) % 50), bx = i * (w / n);
      s += `<rect x="${bx}" y="${400 - bh}" width="${bw}" height="${bh}" rx="6" fill="${col}"/>`;
      for (let r = 0; r < bh / 40 - 1; r++) for (let c = 0; c < bw / 26 - 1; c++)
        s += `<rect x="${bx + 10 + c * 24}" y="${400 - bh + 14 + r * 38}" width="12" height="18" rx="2" fill="${shade(col, .35)}"/>`;
    }
    return svg(parent, w, 400, `<g opacity="${opt.opacity ?? .9}">${s}</g>`, { x, y: y - 400 });
  };
  R.palm = function (parent, x, y, s = 1) {
    return svg(parent, 140 * s, 220 * s, `<g transform="scale(${s})" filter="url(#soft)"><path d="M66 220 C70 160 64 110 72 70" stroke="#9a7046" stroke-width="12" fill="none" stroke-linecap="round"/><g fill="#3f9b57"><path d="M72 70 C40 40 10 50 0 70 C30 56 50 62 72 74Z"/><path d="M72 70 C100 36 130 44 140 64 C112 52 92 60 72 74Z"/><path d="M72 70 C60 30 76 6 96 0 C84 24 82 48 74 72Z"/><path d="M72 70 C44 64 26 86 24 104 C40 84 56 78 72 74Z"/><path d="M72 70 C100 66 118 86 118 106 C102 86 88 78 72 74Z"/></g></g>`, { x: x - 70 * s, y: y - 220 * s });
  };
  R.bush = (parent, x, y, s = 1, c = "#4caa5e") => svg(parent, 120 * s, 70 * s, `<g transform="scale(${s})" filter="url(#soft)"><circle cx="30" cy="45" r="26" fill="${c}"/><circle cx="62" cy="34" r="34" fill="${shade(c, .1)}"/><circle cx="92" cy="46" r="24" fill="${shade(c, -.08)}"/></g>`, { x: x - 60 * s, y: y - 70 * s });
  /* road with a pavement on top; y is the pavement's top edge */
  R.street = function (parent, x, y, w, opt = {}) {
    const h = opt.h || 520;
    let dash = "";
    for (let i = 0; i < w / 150; i++) dash += `<rect x="${i * 150 + 20}" y="${h * .52}" width="80" height="12" rx="6" fill="#f2efe4"/>`;
    let tiles = "";
    for (let i = 0; i < w / 90; i++) tiles += `<line x1="${i * 90}" y1="0" x2="${i * 90 - 14}" y2="96" stroke="#d3d8dc" stroke-width="3"/>`;
    return svg(parent, w, h, `<rect width="${w}" height="100" fill="#eceff1"/>${tiles}<line x1="0" y1="48" x2="${w}" y2="48" stroke="#d3d8dc" stroke-width="3"/><rect y="96" width="${w}" height="22" fill="#c3c9ce"/><rect y="118" width="${w}" height="${h - 118}" fill="url(#road)"/>${dash.replace(/y="[0-9.]+"/g, `y="${h * .3}"`)}<defs><linearGradient id="road" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#55606a"/><stop offset="1" stop-color="#2d353c"/></linearGradient></defs>`, { x, y });
  };

  /* a shop front. Returns {root, parts:{wall, sign, door, window, awning}} so parts can drop in one by one */
  R.shop = function (parent, x, y, opt = {}) {
    const w = opt.w || 640, h = opt.h || 520, main = opt.color || "#1f6b4f", wall = opt.wall || "#f5ead2";
    const root = box(parent, x - w / 2, y - h, w, h);
    const parts = {};
    parts.wall = svg(root, w, h, `<g filter="url(#soft)"><rect x="0" y="40" width="${w}" height="${h - 40}" rx="18" fill="${clay(wall)}"/><rect x="0" y="${h - 120}" width="${w}" height="120" rx="12" fill="${clay(main)}"/><rect x="-14" y="24" width="${w + 28}" height="34" rx="12" fill="${clay(shade(wall, -.12))}"/></g>`);
    parts.window = svg(root, w * .42, h * .42, `<g filter="url(#soft)"><rect width="${w * .42}" height="${h * .42}" rx="16" fill="${shade(main, -.3)}"/><rect x="12" y="12" width="${w * .42 - 24}" height="${h * .42 - 24}" rx="10" fill="#bfe3f2"/><path d="M24 ${h * .3} L${w * .14} 24" stroke="#fff" stroke-width="10" opacity=".55" stroke-linecap="round"/></g>`, { x: w * .06, y: h * .3 });
    parts.door = svg(root, w * .26, h * .58, `<g filter="url(#soft)"><rect width="${w * .26}" height="${h * .58}" rx="14" fill="${clay(main)}"/><rect x="14" y="14" width="${w * .26 - 28}" height="${h * .3}" rx="8" fill="#bfe3f2"/><circle cx="${w * .26 - 22}" cy="${h * .36}" r="7" fill="#e8c46a"/></g>`, { x: w * .62, y: h * .42 });
    const sw = opt.signW || w * .7;
    parts.sign = svg(root, sw, 110, `<g filter="url(#soft)"><rect width="${sw}" height="110" rx="20" fill="${clay(main)}"/><rect x="8" y="8" width="${sw - 16}" height="94" rx="14" fill="none" stroke="#e8c46a" stroke-width="4"/><text x="${sw / 2}" y="76" text-anchor="middle" font-family="Lalezar" font-size="66" fill="#f6dc8c">${opt.sign || ""}</text></g>`, { x: (w - sw) / 2, y: -70 });
    if (opt.awning !== false) {
      let stripes = "";
      const n = 8;
      for (let i = 0; i < n; i++) stripes += `<path d="M${i * w / n} 0 h${w / n} v70 q-${w / n / 2} 30 -${w / n} 0z" fill="${i % 2 ? "#fff" : opt.awning || "#d9534f"}"/>`;
      parts.awning = svg(root, w, 110, `<g filter="url(#soft)">${stripes}</g>`, { x: 0, y: h * .18 });
    }
    return { root, parts, w, h };
  };

  /* a room inside a house: back wall, floor, window; returns root */
  R.room = function (parent, x, y, w, h, opt = {}) {
    const root = box(parent, x, y, w, h);
    const wall = opt.wall || "#f4e6cf", floor = opt.floor || "#c99a6b";
    svg(root, w, h, `<rect width="${w}" height="${h * .72}" fill="${clay(wall)}"/><rect y="${h * .72}" width="${w}" height="${h * .28}" fill="${clay(floor)}"/><rect y="${h * .72 - 14}" width="${w}" height="16" fill="${shade(wall, -.25)}"/><g filter="url(#soft)"><rect x="${w * .62}" y="${h * .16}" width="${w * .26}" height="${h * .26}" rx="12" fill="#fff"/><rect x="${w * .62 + 12}" y="${h * .16 + 12}" width="${w * .26 - 24}" height="${h * .26 - 24}" rx="6" fill="#a8d8f0"/><line x1="${w * .75}" y1="${h * .16}" x2="${w * .75}" y2="${h * .42}" stroke="#fff" stroke-width="10"/></g>`);
    return root;
  };
  R.sofa = (parent, x, y, s = 1, c = "#3c6fd1") => svg(parent, 420 * s, 220 * s, `<g transform="scale(${s})" filter="url(#soft)"><rect x="20" y="10" width="380" height="130" rx="40" fill="${clay(c)}"/><rect x="0" y="90" width="420" height="100" rx="40" fill="${clay(shade(c, .08))}"/><rect x="40" y="185" width="22" height="30" rx="6" fill="#6b4a2f"/><rect x="358" y="185" width="22" height="30" rx="6" fill="#6b4a2f"/></g>`, { x: x - 210 * s, y: y - 215 * s });

  /* ---------- flowers ---------- */
  /* one flower head as SVG markup at (x, y): kind "rose" | "daisy" | "tulip" */
  R.flowerSvg = function (x, y, r, color, kind = "rose") {
    if (kind === "daisy") {
      let p = "";
      for (let i = 0; i < 10; i++) p += `<ellipse cx="${x}" cy="${y - r * .62}" rx="${r * .26}" ry="${r * .52}" fill="${color}" transform="rotate(${i * 36} ${x} ${y})"/>`;
      return p + `<circle cx="${x}" cy="${y}" r="${r * .34}" fill="#f2b33d"/>`;
    }
    if (kind === "tulip") return `<path d="M${x - r * .7} ${y - r * .5} q${r * .1} ${r * 1.3} ${r * .7} ${r * 1.1} q${r * .6} ${r * .2} ${r * .7} -${r * 1.1} l-${r * .35} ${r * .35} l-${r * .35} -${r * .55} l-${r * .35} ${r * .55}z" fill="${color}"/><path d="M${x - r * .2} ${y - r * .3} q${r * .2} ${r * .6} ${r * .2} ${r * .9}" stroke="${shade(color, .35)}" stroke-width="${r * .12}" fill="none"/>`;
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="${shade(color, -.12)}"/><circle cx="${x - r * .1}" cy="${y - r * .12}" r="${r * .72}" fill="${color}"/><path d="M${x - r * .45} ${y - r * .1} a${r * .45} ${r * .45} 0 1 1 ${r * .7} ${r * .3} a${r * .25} ${r * .25} 0 1 1 -${r * .35} -${r * .3}" stroke="${shade(color, -.3)}" stroke-width="${r * .1}" fill="none" stroke-linecap="round"/>`;
  };
  /* a wrapped bouquet, (x, y) = bottom tip. opt: {s, colors, kind, paper} */
  R.bouquet = function (parent, x, y, opt = {}) {
    const s = opt.s || 1, cols = opt.colors || ["#e8455a", "#f28ab0", "#f6c14b", "#ffffff", "#c9405e"];
    const kinds = opt.kinds || ["rose", "daisy", "rose", "tulip", "rose"];
    let heads = "", leaves = "";
    const spots = [[60, 52], [32, 66], [88, 66], [46, 34], [76, 36], [60, 74], [20, 46], [100, 48]];
    spots.forEach(([fx, fy], i) => {
      leaves += `<ellipse cx="${fx + (i % 2 ? 12 : -12)}" cy="${fy + 14}" rx="12" ry="6" fill="#4f9d5c" transform="rotate(${i % 2 ? 30 : -30} ${fx} ${fy})"/>`;
      heads += R.flowerSvg(fx, fy, 15, cols[i % cols.length], kinds[i % kinds.length]);
    });
    const paper = opt.paper || "#f3dcc4";
    return svg(parent, 120 * s, 200 * s, `<g transform="scale(${s})" filter="url(#soft)">${leaves}${heads}<path d="M8 70 L60 196 L112 70 Q60 96 8 70Z" fill="${clay(paper)}"/><path d="M44 150 q16 8 32 0 l-4 14 q-12 6 -24 0z" fill="#d9536a"/></g>`, { x: x - 60 * s, y: y - 196 * s });
  };
  /* a bucket of flowers on the ground, (x, y) = floor. Returns a box; box.flowers is the bunch */
  R.bucket = function (parent, x, y, opt = {}) {
    const s = opt.s || 1, c = opt.color || "#e8455a", kind = opt.kind || "rose", pot = opt.pot || "#7a8a99";
    let st = "", hd = "";
    for (let i = 0; i < 7; i++) {
      const fx = 22 + i * 13 + (i % 2) * 4, fy = 30 + (i % 3) * 14;
      st += `<path d="M${fx} ${fy} L${60 + (fx - 60) * .3} 120" stroke="#4f9d5c" stroke-width="4"/>`;
      hd += R.flowerSvg(fx, fy, 13, i % 3 === 2 ? shade(c, .25) : c, kind);
    }
    const wrap = box(parent, x - 60 * s, y - 186 * s, 120 * s, 190 * s);
    wrap.flowers = svg(wrap, 120 * s, 190 * s, `<g transform="scale(${s})" filter="url(#soft)">${st}${hd}</g>`);
    wrap.flowers.style.transformOrigin = "50% 62%";
    svg(wrap, 120 * s, 190 * s, `<g transform="scale(${s})" filter="url(#soft)"><path d="M24 110 h72 l-8 76 h-56z" fill="${clay(pot)}"/><rect x="20" y="104" width="80" height="12" rx="5" fill="${shade(pot, .2)}"/></g>`);
    return wrap;   /* wrap.flowers is the bunch alone, to hide or shrink it */
  };

  /* ---------- people: soft, round, toy-like ---------- */
  const SKIN = ["#f1c9a5", "#e0ac84", "#c98d64", "#9c6a46"];
  /* R.person(parent, x, y, {shirt, skin, hair, beard, apron, s, face}) ; (x, y) = feet.
     Returns {root, body, arm, move(keys), at} */
  R.person = function (reel, parent, x, y, opt = {}) {
    const s = opt.s || 1, shirt = opt.shirt || "#e85d4a", skin = opt.skin || SKIN[1], hair = opt.hair || "#2b1d14";
    const pants = opt.pants || "#2f3b57";
    const W = 120, H = 300;
    const root = box(parent, x - W * s / 2, y - H * s, W * s, H * s, { transformOrigin: "50% 100%" });
    const beard = opt.beard ? `<path d="M34 92 Q60 128 86 92 Q84 112 60 116 Q36 112 34 92Z" fill="${hair}"/>` : "";
    const apron = opt.apron ? `<path d="M36 128 h48 v86 q-24 10 -48 0z" fill="${opt.apron}" opacity=".95"/>` : "";
    const face = opt.face === "sad"
      ? `<path d="M50 96 q10 -7 20 0" stroke="#3a2418" stroke-width="4" fill="none" stroke-linecap="round"/>`
      : opt.face === "wow" ? `<ellipse cx="60" cy="96" rx="6" ry="8" fill="#3a2418"/>`
      : `<path d="M50 92 q10 9 20 0" stroke="#3a2418" stroke-width="4" fill="none" stroke-linecap="round"/>`;
    svg(root, W, H, `<ellipse cx="60" cy="290" rx="46" ry="11" fill="#000" opacity=".16"/>`);
    const legs = svg(root, W, H, `<g><rect x="38" y="200" width="20" height="82" rx="10" fill="${clay(pants)}"/><rect x="62" y="200" width="20" height="82" rx="10" fill="${clay(pants)}"/><ellipse cx="46" cy="284" rx="16" ry="9" fill="#1e1e22"/><ellipse cx="74" cy="284" rx="16" ry="9" fill="#1e1e22"/></g>`);
    const body = svg(root, W, H, `<g filter="url(#soft)"><rect x="26" y="118" width="68" height="100" rx="30" fill="${clay(shirt)}"/>${apron}<rect x="50" y="104" width="20" height="20" rx="8" fill="${shade(skin, -.1)}"/><circle cx="60" cy="70" r="44" fill="${clay(skin)}"/><path d="M16 66 Q18 18 60 20 Q102 18 104 62 Q92 44 60 42 Q28 44 16 66Z" fill="${hair}"/>${beard}<circle cx="45" cy="72" r="6" fill="#2a1a10"/><circle cx="75" cy="72" r="6" fill="#2a1a10"/><circle cx="47" cy="70" r="2" fill="#fff"/><circle cx="77" cy="70" r="2" fill="#fff"/>${face}<circle cx="36" cy="86" r="7" fill="#f08c7a" opacity=".35"/><circle cx="84" cy="86" r="7" fill="#f08c7a" opacity=".35"/></g>`);
    const arm = svg(root, W, H, `<rect x="88" y="124" width="18" height="70" rx="9" fill="${clay(shirt)}"/><circle cx="97" cy="194" r="10" fill="${skin}"/>`);
    arm.style.transformOrigin = `${97 / W * 100}% ${130 / H * 100}%`;
    const armL = svg(root, W, H, `<rect x="14" y="124" width="18" height="70" rx="9" fill="${clay(shade(shirt, -.08))}"/><circle cx="23" cy="194" r="10" fill="${skin}"/>`);
    root.style.transform = `scale(${s})`;
    root.style.width = W + "px"; root.style.height = H + "px";
    root.style.left = (x - W / 2) + "px"; root.style.top = (y - H) + "px";
    const p = { root, body, arm, armL, legs, keys: { x: [[0, 0]], y: [[0, 0]], o: [[0, 1]] }, walk: [], wave: [], sitAt: [] };
    p.move = (t0, t1, dx, dy = 0) => {               // walk by (dx, dy) between t0 and t1
      const last = p.keys.x[p.keys.x.length - 1][1], lastY = p.keys.y[p.keys.y.length - 1][1];
      p.keys.x.push([t0, last], [t1, last + dx, "linear"]);
      p.keys.y.push([t0, lastY], [t1, lastY + dy, "linear"]);
      p.walk.push([t0, t1]);
      return p;
    };
    p.show = (t0, t1) => { p.keys.o = [[t0 - .01, 0], [t0, 1, "linear"]].concat(t1 != null ? [[t1, 1], [t1 + .01, 0, "linear"]] : []); return p; };
    p.waveAt = (t0, d = 1) => { p.wave.push([t0, d]); return p; };
    p.face = dir => { root.dataset.flip = dir < 0 ? 1 : 0; return p; };
    const seed = (x * 7 + y * 3) % 10;
    reel.on(t => {
      const walking = p.walk.find(([a, b]) => t >= a && t < b);
      const bob = walking ? Math.abs(Math.sin((t - walking[0]) * 11)) * -10 : wob(t, .35, seed) * 2.5;
      const step = walking ? Math.sin((t - walking[0]) * 11) * 9 : 0;
      const flip = root.dataset.flip === "1" ? -1 : 1;
      root.style.transform = `translate(${k(t, p.keys.x)}px, ${k(t, p.keys.y) + bob}px) scale(${s * flip}, ${s})`;
      const o = k(t, p.keys.o);
      root.style.opacity = o; root.style.visibility = o < .01 ? "hidden" : "inherit";
      legs.style.transform = `skewX(${step * .4}deg)`;
      const w = p.wave.find(([a, d]) => t >= a && t < a + d);
      arm.style.transform = w ? `rotate(${-120 + Math.sin((t - w[0]) * 14) * 22}deg)` : `rotate(${step * 1.5}deg)`;
      armL.style.transformOrigin = `${23 / W * 100}% ${130 / H * 100}%`;
      armL.style.transform = `rotate(${-step * 1.5}deg)`;
    });
    return p;
  };
  R.SKIN = SKIN;

  /* ---------- word-by-word caption (one word at a time, pops on its spoken time) ----------
     words: [[word, start], ...] (from words.json or R.timing). opt: {y, size, color, font, until, hold, emph:{index:color}} */
  R.caption = function (reel, words, opt = {}) {
    const y = opt.y ?? reel.H * .22, size = opt.size || 120;
    const node = box(reel.stage, 0, y - size, reel.W, size * 1.6, {
      display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center",
      font: `${size}px ${opt.font || "Lalezar"}`, color: opt.color || "#fff",
      textShadow: opt.shadow || "0 6px 0 rgba(0,0,0,.18), 0 10px 26px rgba(0,0,0,.35)", whiteSpace: "nowrap", zIndex: 50,
    });
    const span = el("span", { style: { display: "inline-block", transformOrigin: "50% 70%" } }, node);
    const ends = opt.ends;
    reel.on(t => {
      let i = -1;
      for (let j = 0; j < words.length; j++) if (t >= words[j][1] - .03) i = j;
      const end = i >= 0 ? (ends ? ends[i] + (opt.hold ?? .35) : (words[i + 1] ? words[i + 1][1] : Infinity)) : 0;
      if (i < 0 || t > end || (opt.until != null && t > opt.until)) { span.style.visibility = "hidden"; return; }
      const [w] = words[i];
      if (span.textContent !== w) span.textContent = w;
      span.style.visibility = "inherit";
      span.style.color = (opt.emph && opt.emph[i]) || "";
      const p = pop(t, words[i][1] - .03, .22);
      span.style.transform = `scale(${.6 + .4 * p}) translateY(${(1 - p) * 30}px)`;
      span.style.opacity = clamp(p * 2);
    });
    return node;
  };

  /* script -> word times. lines: ["first line", "second line"], words: words.json data or null.
     With a voice, keeps the voice's times and the script's spelling. Without one, assumes wps words a second. */
  R.timing = function (lines, voice, opt = {}) {
    const wps = opt.wps || 2.6, gap = opt.gap ?? .3, start = opt.start ?? .15;
    const script = lines.map(l => l.split(/\s+/).filter(Boolean));
    const flat = script.flat();
    let out = [], ends = [], lineStarts = [];
    if (voice && voice.words && voice.words.length) {
      /* align script words to heard words (edit distance on normalised words), so a misheard or
         merged word only shifts itself; script words with no partner are spread between neighbours */
      const norm = w => w.toLowerCase().normalize("NFKD").replace(/[ً-ْـ]/g, "").replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[^\p{L}\p{N}]/gu, "");
      const vw = voice.words, n = flat.length, m = vw.length;
      const a = flat.map(norm), b = vw.map(w => norm(w[0]));
      const same = (x, y) => x === y || (x.length >= 3 && y.length >= 3 && (x.startsWith(y) || y.startsWith(x)));
      const D = Array.from({ length: n + 1 }, (_, i) => Float32Array.from({ length: m + 1 }, (_, j) => i + j));
      for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++)
        D[i][j] = Math.min(D[i - 1][j - 1] + (same(a[i - 1], b[j - 1]) ? 0 : 1), D[i - 1][j] + 1, D[i][j - 1] + 1);
      const at = new Array(n).fill(-1);
      for (let i = n, j = m; i > 0 && j > 0;) {
        if (D[i][j] === D[i - 1][j - 1] + (same(a[i - 1], b[j - 1]) ? 0 : 1)) { at[i - 1] = j - 1; i--; j--; }
        else if (D[i][j] === D[i - 1][j] + 1) i--; else j--;
      }
      const vEnd = j => (voice.ends ? voice.ends[j] : vw[j][1] + .3);
      for (let i = 0; i < n; i++) {
        if (at[i] >= 0) { out.push([flat[i], vw[at[i]][1]]); ends.push(vEnd(at[i])); continue; }
        let p = i - 1; while (p >= 0 && at[p] < 0) p--;
        let q = i + 1; while (q < n && at[q] < 0) q++;
        const t0 = p >= 0 ? vEnd(at[p]) : 0, t1 = q < n ? vw[at[q]][1] : t0 + .4 * (q - p);
        const t = t0 + (t1 - t0) * (i - p) / (q - p) * .999;
        out.push([flat[i], t]); ends.push(t + .3);
      }
      let c = 0;
      for (const l of script) { lineStarts.push(out[c] ? out[c][1] : 0); c += l.length; }
    } else {
      let t = start;
      for (const l of script) {
        lineStarts.push(t);
        for (const w of l) { out.push([w, t]); t += 1 / wps * (w.length > 6 ? 1.25 : 1); ends.push(t - .05); }
        t += gap;
      }
    }
    return { words: out, ends, lines: lineStarts, end: ends[ends.length - 1] || 0 };
  };

  /* ---------- icons (24x24 line icons) ---------- */
  R.icons = {
    store: '<path d="M3 9l1.5-5h15L21 9M3 9h18v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0zM5 13v7h14v-7M10 20v-5h4v5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    people: '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M15 14.5c3 0 6 2 6 5.5"/>',
    ticket: '<path d="M4 7h16v3a2 2 0 0 0 0 4v3H4v-3a2 2 0 0 0 0-4z"/><path d="M14 7v10" stroke-dasharray="2 2"/>',
    phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    home: '<path d="M3 11l9-7 9 7M5 10v10h14V10M10 20v-6h4v6"/>',
    bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    bread: '<path d="M4 13c0-4 3.6-7 8-7s8 3 8 7v5H4z"/><path d="M9 10l-1 3M13 9.5l-1 3.5M17 10.5l-1 2.5"/>',
    fire: '<path d="M12 21c4 0 7-2.7 7-6.5 0-4-3-6.5-4-9.5-1 2-2.5 3-4 3 1-2 0-4-1-5-1.5 3-5 5.5-5 11.5C5 18.3 8 21 12 21z"/>',
    sad: '<circle cx="12" cy="12" r="9"/><path d="M8.5 16.5c2-2 5-2 7 0M9 10h.01M15 10h.01"/>',
    star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/>',
    walk: '<circle cx="13" cy="4.5" r="2"/><path d="M10 21l2-6 3 3v3M8 12l3-4 3 1 2 3M12 8l-1 7"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    car: '<path d="M3 16v-4l2-5h14l2 5v4zM3 16v2h3v-2M18 16v2h3v-2"/><circle cx="7.5" cy="13" r="1"/><circle cx="16.5" cy="13" r="1"/>',
    flower: '<circle cx="12" cy="8" r="2.5"/><path d="M12 5.5c0-2 3-2.5 3 0M14.5 8c2 0 2.5 3 0 3M12 10.5c0 2-3 2.5-3 0M9.5 8c-2 0-2.5-3 0-3M12 10.5V21M12 17c-2-2-4-2-5-1M12 15c2-2 4-2 5-1"/>',
    cup: '<path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 2v3M12 2v3"/>',
  };
  R.icon = (name, size = 48, color = "currentColor", sw = 2) =>
    `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${R.icons[name] || ""}</svg>`;

  /* ---------- story dock: a bar of icons at the bottom; each lights up when its beat is told ----------
     items: [{icon, at}] in story order. opt: {y, accent, bg, from} */
  R.dock = function (reel, items, opt = {}) {
    const size = opt.size || 74, gap = 14, w = items.length * (size + gap) + gap;
    const y = opt.y ?? reel.H - 190;
    const bar = box(reel.stage, (reel.W - w) / 2, y, w, size + gap * 2, {
      background: opt.bg || "rgba(22,30,30,.78)", borderRadius: (size / 2 + gap) + "px", display: "flex", gap: gap + "px",
      padding: gap + "px", boxSizing: "border-box", direction: "ltr", boxShadow: "0 10px 30px rgba(0,0,0,.25)", zIndex: 40,
    });
    const accent = opt.accent || "#e8c46a";
    const slots = (reel.lang === "ar" ? items.slice().reverse() : items).map(it => {
      const s = el("div", { style: { width: size + "px", height: size + "px", borderRadius: "22px", display: "grid", placeItems: "center", border: "3px solid rgba(255,255,255,.12)", color: "rgba(255,255,255,.28)", boxSizing: "border-box" }, html: R.icon(it.icon, size * .52) }, bar);
      return [s, it];
    });
    for (const it of items) reel.cue(it.at, "tick", "dock " + it.icon);
    reel.on(t => {
      const show = opt.from != null ? pop(t, opt.from, .5) : 1;
      bar.style.transform = `translateY(${(1 - show) * 260}px)`;
      for (const [s, it] of slots) {
        const on = t >= it.at, p = pop(t, it.at, .35);
        s.style.color = on ? (it.color || accent) : "rgba(255,255,255,.28)";
        s.style.borderColor = on ? (it.color || accent) : "rgba(255,255,255,.12)";
        s.style.background = on ? "rgba(255,255,255,.08)" : "transparent";
        s.style.transform = on ? `scale(${.8 + .2 * p + (p < 1 ? .15 * Math.sin(p * Math.PI) : 0)})` : "scale(1)";
      }
    });
    return bar;
  };

  /* ---------- phone with an app screen ---------- */
  /* R.phone(reel, parent, x, y, {w, html, accent}) -> {root, screen}. Build the app screen in `screen` with plain HTML. */
  R.phone = function (reel, parent, x, y, opt = {}) {
    const w = opt.w || 360, h = w * 2.05;
    const root = box(parent, x - w / 2, y - h, w, h, {
      background: "#16191c", borderRadius: w * .14 + "px", padding: w * .035 + "px", boxSizing: "border-box",
      boxShadow: "0 30px 60px rgba(0,0,0,.35), inset 0 0 0 3px #2c3238", zIndex: 30,
    });
    const screen = el("div", { style: { width: "100%", height: "100%", borderRadius: w * .11 + "px", background: opt.bg || "#f6f8f7", overflow: "hidden", position: "relative", font: `${w * .055}px 'IBM Plex Sans Arabic'`, color: "#1c2a26", direction: reel.lang === "ar" ? "rtl" : "ltr" } }, root);
    el("div", { style: { position: "absolute", top: w * .03 + "px", left: "50%", width: w * .28 + "px", height: w * .07 + "px", marginLeft: -w * .14 + "px", background: "#16191c", borderRadius: "99px", zIndex: 5 } }, screen);
    if (opt.html) screen.insertAdjacentHTML("beforeend", opt.html);
    return { root, screen, w, h };
  };
  /* a notification that drops from the top of a phone screen */
  R.notify = function (reel, phone, t0, title, body, opt = {}) {
    const w = phone.w;
    const n = el("div", { style: { position: "absolute", left: "5%", right: "5%", top: w * .13 + "px", background: "rgba(255,255,255,.97)", borderRadius: w * .06 + "px", padding: w * .04 + "px", boxShadow: "0 10px 30px rgba(0,0,0,.18)", display: "flex", gap: w * .03 + "px", alignItems: "center", zIndex: 6 } }, phone.screen);
    n.innerHTML = `<div style="flex:none;width:${w * .13}px;height:${w * .13}px;border-radius:${w * .035}px;background:${opt.accent || "#1f6b4f"};display:grid;place-items:center;color:#fff">${R.icon(opt.icon || "bell", w * .08, "#fff", 2.4)}</div><div style="line-height:1.35"><div style="font-weight:600">${title}</div><div style="opacity:.7;font-size:.85em">${body}</div></div>`;
    reel.on(t => {
      const p = pop(t, t0, .45), out = opt.until ? 1 - ease.in(clamp((t - opt.until) / .3)) : 1;
      n.style.transform = `translateY(${(1 - p * out) * -160}%)`;
      n.style.visibility = t < t0 ? "hidden" : "inherit";
    });
    reel.cue(t0, "notify", title);
    return n;
  };
  /* a number on screen that counts between values: R.count(reel, node, [[t, value], ...], {digits:'arab'}) */
  R.count = function (reel, node, keys, opt = {}) {
    const ar = "٠١٢٣٤٥٦٧٨٩";
    reel.on(t => {
      let v = String(Math.round(k(t, keys)));
      if (opt.digits === "arab") v = v.replace(/\d/g, d => ar[d]);
      if (node.textContent !== v) node.textContent = v;
    });
    return node;
  };

  /* ---------- end card ---------- */
  R.endcard = function (reel, at, opt = {}) {
    const card = box(reel.stage, reel.W * .14, reel.H * .62, reel.W * .72, reel.H * .2, {
      background: "#fff", borderRadius: "42px", boxShadow: "0 30px 70px rgba(0,0,0,.25)", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: "10px", zIndex: 60, color: opt.color || "#1f6b4f",
    });
    card.innerHTML = `<div style="width:110px;height:110px;border-radius:30px;background:${opt.color || "#1f6b4f"};display:grid;place-items:center">${opt.logo || R.icon(opt.icon || "star", 64, "#fff", 2.4)}</div><div style="font:96px Lalezar;line-height:1.1">${opt.name || ""}</div><div style="font:600 34px 'IBM Plex Sans Arabic';opacity:.75">${opt.tagline || ""}</div>`;
    R.popIn(reel, card, at, { origin: "50% 50%", d: .5, note: "end card" });
    return card;
  };

  window.R = R;
})();
