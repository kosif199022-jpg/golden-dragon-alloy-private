#!/usr/bin/env node
'use strict';
/*
 * Black Dragon renderer: a seekable HTML film -> MP4, frames piped straight into ffmpeg (no PNG folder on disk).
 * Page contract: window.__kosif = { duration, seek(t) } (seek may be async); optional window.__kosifReady promise;
 * optional window.__kosif.allowBlack(t) -> true where a black frame is intended (for example a dip to black mid-film).
 *
 *   node render.cjs --in film.html --out film.mp4 [--fps 30] [--start s] [--duration s] [--width 1080 --height 1920] [--crf 17]
 *                   [--recycle 120] [--allow-black-head 0.6] [--allow-black-tail 1.5] [--strict] [--no-guard]
 *   node render.cjs --in film.html --stills 1,4.5,9 --stills-dir dir     (PNG stills, no video)
 *
 * Output follows the KOSIF export standard: H.264 High, CRF 17, preset slow, yuv420p, BT.709 tagged + converted, +faststart.
 *
 * Black-run guard (v1.2). In Nov 2026 headless Chromium gave runs of pure-black frames on canvas pages once one page had
 * rendered many frames; the same seconds rendered in a fresh page were fine. So, for a page that has a canvas:
 *   - each frame is checked: the canvas is read through a 27x48 copy inside the seek call, and a black reading is
 *     confirmed on the captured picture (a PNG byte-identical to an all-black frame needs no decoding at all);
 *   - a black frame after the first --allow-black-head and before the last --allow-black-tail seconds (fades; films
 *     under 6 s scale both defaults by duration/6, like dragon verify), and not
 *     allowed by the page, is retried up to 3 times from a fresher page: reload, new browser context, new browser.
 *     Log lines: "RECOVERED t=.. tries=.. via=.." or "BLACK_UNRECOVERED t=..";
 *   - --recycle N reloads the page every N frames (0 = never); --no-guard turns the check and the retries off;
 *   - --strict: exit code 3 when a frame stayed black (the MP4 is still written, so it can be inspected or patched).
 * Pages without a canvas are not checked. The last line is "SUMMARY frames=.. recovered=.. unrecovered=.. reloads=..".
 *
 * Chunks (v1.3): --start S renders film time S .. S+duration (default: to the end of the film) into its own MP4, so a
 * long film is rendered as chunk k = --start k*L --duration L and joined with ffmpeg concat. Frame i shows film time
 * S + i/fps. The black-guard windows (--allow-black-head/-tail) are relative to the chunk: give a middle chunk
 * --allow-black-head 0 --allow-black-tail 0. Log times are film times.
 */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');

const FLAGS = ['--font-render-hinting=none', '--disable-lcd-text', '--force-color-profile=srgb', '--hide-scrollbars',
  '--disable-partial-raster', '--disable-skia-runtime-opts', '--allow-file-access-from-files'];
const PROBE_SIDE = 48;                          // long side of the canvas probe: 27x48 for a 9:16 canvas
const BLANK_MAX = 8;                            // a probe whose brightest pixel is <= 8 (of 255) reads as black
const PICTURE_BLACK_Y = (17.5 - 16) * 255 / 219; // qa.black_runs' limit (mean Y 17.5, TV range) as full-range luma
const LADDER = ['reload', 'context', 'browser']; // recovery tries, each from a fresher page
const SHORT_CLIP_S = 6;                         // below this the fade windows shrink in proportion (dragon verify)
const COOLDOWN = 30;                            // frames to trust the picture after the canvas misread it as black

function parseArgs(argv) {
  const o = { fps: 30, start: 0, width: 1080, height: 1920, crf: 17, recycle: 120, 'allow-black-head': 0.6, 'allow-black-tail': 1.5,
    guard: true, strict: false, explicit: new Set() };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i].replace(/^--/, '');
    const v = argv[i + 1];
    if (k === 'help' || k === 'h' || k === '-h') { o.help = true; return o; }
    if (['in', 'out', 'stills', 'stills-dir'].includes(k)) { o[k] = v; i++; }
    else if (['fps', 'duration', 'width', 'height', 'crf'].includes(k)) { o[k] = Number(v); i++; }
    else if (k === 'start') {
      o.start = Number(v); i++;
      if (!(o.start >= 0)) throw new Error('--start needs a number >= 0');
    }
    else if (['recycle', 'allow-black-head', 'allow-black-tail'].includes(k)) {
      o[k] = Number(v); i++; o.explicit.add(k);
      if (!(o[k] >= 0)) throw new Error(`--${k} needs a number >= 0`);
    }
    else if (k === 'no-guard') o.guard = false;
    else if (k === 'strict') o.strict = true;
    else throw new Error(`unknown option ${argv[i]}`);
  }
  o.recycle = Math.floor(o.recycle);
  if (!o.in) throw new Error('--in is required');
  if (!o.out && !o.stills) throw new Error('--out or --stills is required');
  return o;
}

function loadPlaywright() {
  const roots = [process.env.KOSIF_ROOT, path.join(process.env.USERPROFILE || process.env.HOME || '', 'kosif-tool'), __dirname]
    .filter(Boolean).map((r) => path.join(r, 'node_modules'));
  return require(require.resolve('playwright', { paths: roots }));
}

// Runs in the page: seek, then read the main canvas through a tiny copy. It must run in the same call as seek: a WebGL
// canvas without preserveDrawingBuffer reads empty once the frame has been composited.
async function seekAndProbe({ t, side }) {
  const k = window.__kosif;
  await k.seek(t);
  const cv = document.querySelector('canvas');
  if (!cv || !cv.width || !cv.height) return { canvas: false };
  try {
    if (typeof k.allowBlack === 'function' && k.allowBlack(t)) return { canvas: true, allowed: true };
  } catch (e) { /* a broken hook allows nothing */ }
  const wide = cv.width >= cv.height;
  const w = wide ? side : Math.max(1, Math.round(side * cv.width / cv.height));
  const h = wide ? Math.max(1, Math.round(side * cv.height / cv.width)) : side;
  try {
    let g = window.__kosifGuardProbe;
    if (!g || g.canvas.width !== w || g.canvas.height !== h) {
      const c = typeof OffscreenCanvas === 'function' ? new OffscreenCanvas(w, h)
        : Object.assign(document.createElement('canvas'), { width: w, height: h });
      g = window.__kosifGuardProbe = c.getContext('2d', { willReadFrequently: true });
    }
    g.clearRect(0, 0, w, h);
    g.imageSmoothingEnabled = true;
    g.imageSmoothingQuality = 'high'; // averages; 'low' point-samples and can miss small type
    g.drawImage(cv, 0, 0, w, h);
    const d = g.getImageData(0, 0, w, h).data;
    let max = 0; // brightest probe pixel; transparent parts count as black
    for (let i = 0; i < d.length; i += 4) max = Math.max(max, Math.max(d[i], d[i + 1], d[i + 2]) * d[i + 3] / 255);
    return { canvas: true, max: Math.round(max) };
  } catch (e) {
    return { canvas: true, max: null }; // unreadable (e.g. tainted): only the exact-black check applies
  }
}

// Runs in the page: mean full-range BT.709 luma of a captured PNG (base64), decoded by the browser at a 96-pixel scale.
async function meanLuma(b64) {
  const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
  const bm = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
  const s = 96 / Math.max(bm.width, bm.height);
  const w = Math.max(1, Math.round(bm.width * s)), h = Math.max(1, Math.round(bm.height * s));
  const g = new OffscreenCanvas(w, h).getContext('2d', { willReadFrequently: true });
  g.imageSmoothingEnabled = true;
  g.imageSmoothingQuality = 'high';
  g.drawImage(bm, 0, 0, w, h);
  bm.close();
  const d = g.getImageData(0, 0, w, h).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
  return sum / (w * h);
}

// One film page that can be reloaded or rebuilt from scratch.
class Session {
  constructor(playwright, o) {
    this.pw = playwright;
    this.o = o;
    this.url = pathToFileURL(path.resolve(o.in)).href;
    this.clip = { x: 0, y: 0, width: o.width, height: o.height, scale: 1 };
    this.browser = this.ctx = this.page = this.cdp = null;
    this.wantBlack = false; // capture an all-black reference frame (guarded video renders only)
    this.black = null;
    this.age = 0;           // frames captured since the page last loaded
  }

  // level 0 = reload the page, 1 = new browser context (a new renderer process), 2 = new browser
  async open(level) {
    if (level >= 2) {
      if (this.browser) await this.browser.close().catch(() => {});
      this.browser = await this.pw.chromium.launch({ headless: true, args: FLAGS });
    }
    if (level >= 1) {
      if (level === 1 && this.ctx) await this.ctx.close().catch(() => {});
      this.ctx = await this.browser.newContext({ viewport: { width: this.o.width, height: this.o.height }, deviceScaleFactor: 1, locale: 'ar' });
      this.page = await this.ctx.newPage();
      this.page.on('pageerror', (e) => console.error('[page error]', e.message));
      this.cdp = await this.ctx.newCDPSession(this.page);
      if (this.wantBlack && !this.black) { // an all-black frame captured exactly like the film frames
        await this.page.setContent('<html style="background:#000"><body></body></html>');
        this.black = Buffer.from(await this.capture(), 'base64');
      }
    }
    await this.page.goto(this.url, { waitUntil: 'load' });
    await this.page.evaluate(() => (window.__kosifReady ? Promise.resolve(window.__kosifReady) : true));
    await this.page.evaluate(() => document.fonts && document.fonts.ready);
    const has = await this.page.evaluate(() => !!(window.__kosif && window.__kosif.seek));
    if (!has) throw new Error('page has no window.__kosif.seek');
    this.age = 0;
  }

  async capture() {
    const { data } = await this.cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, optimizeForSpeed: true, clip: this.clip });
    return data;
  }

  // seek + capture; with probe the canvas reading comes back too
  async shot(t, probe = false) {
    const p = probe ? await this.page.evaluate(seekAndProbe, { t, side: PROBE_SIDE })
      : await this.page.evaluate((x) => window.__kosif.seek(x), t);
    const b64 = await this.capture();
    this.age++;
    return { png: Buffer.from(b64, 'base64'), b64, probe: probe ? p : null };
  }

  async pictureLuma(b64) {
    try { return await this.page.evaluate(meanLuma, b64); } catch (e) { return null; }
  }

  async close() {
    if (this.browser) await this.browser.close();
  }
}

// Checks every frame, retries black ones from a fresher page, recycles the page, and counts what happened.
class Guard {
  constructor(sess, o, duration) {
    this.sess = sess;
    this.o = o;
    this.duration = duration;
    // films under 6 s get smaller fade windows, in proportion (the rule of dragon verify and patch-black), unless the
    // flags were given: a 2 s film used to go unchecked (0.6 + 1.5 s windows) and then failed verify.
    const k = Math.min(1, duration / SHORT_CLIP_S);
    this.head = o.explicit.has('allow-black-head') ? o['allow-black-head'] : o['allow-black-head'] * k;
    this.tail = o.explicit.has('allow-black-tail') ? o['allow-black-tail'] : o['allow-black-tail'] * k;
    this.recovered = this.unrecovered = this.recycleReloads = this.recoveryReloads = this.pictureChecks = 0;
    this.streak = 0;     // consecutive frames that stayed black
    this.cooldown = -1;  // frame index until which a black canvas reading is not checked on the picture
    this.hinted = false;
  }

  async frame(i) {
    const { sess, o } = this;
    const local = i / o.fps;                 // chunk time: the guard windows
    const t = (o.start || 0) + local;        // film time: what the page draws
    if (o.recycle > 0 && sess.age >= o.recycle) { await sess.open(0); this.recycleReloads++; }
    const check = o.guard && local >= this.head && local <= this.duration - this.tail;
    let s = await sess.shot(t, check);
    if (!check || !(await this.isBlack(s, i))) { this.streak = 0; return s.png; }
    // right after a frame that stayed black even in a new browser, try one reload only: that black is likely the page's own
    const tries = this.streak ? 1 : LADDER.length;
    for (let k = 0; k < tries; k++) {
      await sess.open(k);
      this.recoveryReloads++;
      s = await sess.shot(t, true);
      if (!(await this.isBlack(s, i))) {
        console.log(`RECOVERED t=${t.toFixed(3)} tries=${k + 1} via=${LADDER[k]}`);
        this.recovered++;
        this.streak = 0;
        return s.png;
      }
    }
    console.log(`BLACK_UNRECOVERED t=${t.toFixed(3)}`);
    if (!this.hinted) {
      this.hinted = true;
      console.log('  (if this black is intended, the page can declare window.__kosif.allowBlack = (t) => true for it)');
    }
    this.unrecovered++;
    this.streak++;
    return s.png;
  }

  // Black = the PNG is byte-identical to an all-black frame, or the canvas reads black and the whole picture is dark
  // enough for qa.black_runs to flag it (type in DOM layers over a black canvas keeps the frame).
  async isBlack(s, i) {
    const p = s.probe;
    if (!p || !p.canvas || p.allowed) return false;
    if (this.sess.black && s.png.equals(this.sess.black)) return true;
    if (p.max === null || p.max > BLANK_MAX || i < this.cooldown) return false;
    this.pictureChecks++;
    const y = await this.sess.pictureLuma(s.b64);
    if (y === null || y < PICTURE_BLACK_Y) return true;
    this.cooldown = i + COOLDOWN; // the canvas is not the whole picture on this page: stop decoding for a while
    return false;
  }

  summary(frames) {
    return `SUMMARY frames=${frames} recovered=${this.recovered} unrecovered=${this.unrecovered} `
      + `reloads=${this.recycleReloads + this.recoveryReloads} recycle_reloads=${this.recycleReloads} `
      + `recovery_reloads=${this.recoveryReloads} picture_checks=${this.pictureChecks} guard=${this.o.guard ? 'on' : 'off'}`;
  }
}

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help) {
    const doc = fs.readFileSync(__filename, 'utf8').split('/*')[1].split('*/')[0];
    process.stdout.write(doc.split('\n').map(l => l.replace(/^ \* ?/, '')).join('\n').trim() + '\n');
    return;
  }
  const sess = new Session(loadPlaywright(), o);
  sess.wantBlack = o.guard && !o.stills;
  await sess.open(2);
  const filmDuration = await sess.page.evaluate(() => window.__kosif.duration);
  const duration = o.duration || Math.max(0, (filmDuration || 0) - o.start);
  if (!o.stills && o.start > 0 && filmDuration && o.start >= filmDuration) throw new Error(`--start ${o.start} is past the film's end (${filmDuration} s)`);

  if (o.stills) {
    const dir = o['stills-dir'] || path.dirname(path.resolve(o.out || o.in));
    fs.mkdirSync(dir, { recursive: true });
    for (const t of o.stills.split(',').map(Number)) {
      const f = path.join(dir, `still_${t.toFixed(3)}.png`);
      fs.writeFileSync(f, (await sess.shot(t)).png);
      console.log('still', t, f);
    }
    await sess.close();
    return;
  }

  const frames = Math.round(duration * o.fps);
  const ff = spawn('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(o.fps),
    '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow',
    '-crf', String(o.crf), '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
    '-color_trc', 'bt709', '-color_range', 'tv',
    // the generic flags alone left primaries/transfer "unknown" in the old renderer; x264 VUI writes all three
    '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709',
    '-r', String(o.fps), '-movflags', '+faststart', o.out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exited ${c}`)))));
  const guard = new Guard(sess, o, duration);
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    const png = await guard.frame(i);
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 150 === 0 || i === frames - 1) {
      const fpsNow = (i + 1) / ((Date.now() - t0) / 1000);
      console.log(`frame ${i + 1}/${frames}  ${fpsNow.toFixed(2)} fps`);
    }
  }
  ff.stdin.end();
  await done;
  await sess.close();
  console.log('VIDEO', o.out, `${frames} frames`, o.start ? `film ${o.start}-${(o.start + frames / o.fps).toFixed(3)} s` : '');
  console.log(guard.summary(frames));
  if (o.strict && guard.unrecovered) {
    console.error(`render failed: ${guard.unrecovered} frame(s) stayed black (--strict)`);
    process.exitCode = 3;
  }
}

main().catch((e) => { console.error('render failed:', e.message); process.exit(2); });
