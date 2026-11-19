// render_frames.js PAGE DIR --w W --h H --fps F --from A --to B [--format png|jpeg] [--no-clock]
// Deterministic frame capture: the page's time is set per frame, never read from the wall clock.
//  * JS time (Date, performance.now, setTimeout, requestAnimationFrame) runs on Playwright's fake clock.
//  * CSS animations/transitions + Web Animations are paused and seeked; each one's start is the first frame it exists.
//  * Optional hook: window.hfcRender = async (t, frame) => {...} for canvas/three.js/GSAP timelines.
// Workers that start at frame A replay frames 0..A-1 without screenshots, so every worker sees the same state.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const argv = process.argv.slice(2);
const [src, dir] = argv;
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i > 0 ? argv[i + 1] : d; };
const W = +opt('w', 1080), H = +opt('h', 1920), FPS = +opt('fps', 30), A = +opt('from', 0), B = +opt('to', 1);
const fmt = opt('format', 'png'), useClock = !argv.includes('--no-clock');
const url = /^[a-z]+:\/\//i.test(src) ? src : 'file://' + path.resolve(src);
(async () => {
  const b = await chromium.launch({ args: ['--font-render-hinting=none', '--force-color-profile=srgb', '--disable-lcd-text'] });
  const page = await (await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 })).newPage();
  page.on('pageerror', e => console.error('page error:', e.message));
  // install() alone lets fake time flow with the wall clock (measured 2026-11-11: performance.now ran in real time).
  // pauseAt() BEFORE goto freezes it, so page scripts start at the same instant in every worker.
  if (useClock) { await page.clock.install({ time: 0 }); await page.clock.pauseAt(1000); }
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(async () => { if (document.fonts) await document.fonts.ready;
    await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))); });
  let clockMs = 0;
  const step = async (f, shoot) => {
    const tms = f * 1000 / FPS;
    // the fake clock ticks in whole ms (runFor(33.33) advanced 34): step to an integer target so error never accumulates
    const target = Math.round(tms);
    if (useClock && target > clockMs) { await page.clock.runFor(target - clockMs); clockMs = target; }
    await page.evaluate(async ({ t, f }) => {
      const seen = window.__hfcSeen || (window.__hfcSeen = new WeakMap());
      for (const a of document.getAnimations()) {
        if (!seen.has(a)) seen.set(a, t);
        a.pause(); a.currentTime = Math.max(0, (t - seen.get(a)) * 1000);
      }
      if (typeof window.hfcRender === 'function') await window.hfcRender(t, f);
    }, { t: tms / 1000, f });
    if (shoot) {
      const p = path.join(dir, String(f).padStart(6, '0') + (fmt === 'jpeg' ? '.jpg' : '.png'));
      await page.screenshot(fmt === 'jpeg' ? { path: p, type: 'jpeg', quality: 95 } : { path: p });
    }
  };
  for (let f = 0; f < A; f++) await step(f, false);
  for (let f = A; f < B; f++) await step(f, true);
  await b.close();
})().catch(e => { console.error('render_frames: ERROR', e.message); process.exit(1); });
