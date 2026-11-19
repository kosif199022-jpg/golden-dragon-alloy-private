// Build, serve and render the film frame-by-frame in headless Chromium (WebGL via SwiftShader), pipe to ffmpeg.
//   node scripts/export.mjs                      -> out/kitten_rescue.mp4  (1080x1920, 30 fps, 25 s, H.264 High CRF 17)
//   node scripts/export.mjs --stills 0.5,6,12     -> out/stills_grid.jpg
//   node scripts/export.mjs --from 0 --to 300      -> render a frame range (resume / split jobs)
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const FPS = 30, W = 1080, H = 1920; let DUR = 25, N = 750;
mkdirSync(root + '/out', { recursive: true });
if (!args.includes('--no-build')) execSync('npx vite build', { cwd: root, stdio: 'inherit' });
const srv = spawn('npx', ['vite', 'preview', '--port', '4173', '--strictPort'], { cwd: root, stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 2500));

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-sandbox'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('console', (m) => { if (m.type() === 'error') console.error('[page]', m.text()); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.goto('http://localhost:4173/?render=1');
await page.waitForFunction(() => window.__kosif && window.__kosif.ready, null, { timeout: 120000 });
DUR = await page.evaluate(() => window.__kosif.duration); N = Math.round(DUR * FPS);

async function grab(t) {
  const b64 = await page.evaluate((t) => { window.__kosif.seek(t); return document.querySelector('canvas').toDataURL('image/png').split(',')[1]; }, t);
  return Buffer.from(b64, 'base64');
}

try {
  if (args.includes('--stills')) {
    const ts = opt('--stills').split(',').map(Number);
    mkdirSync(root + '/out/stills', { recursive: true });
    const files = [];
    for (const t of ts) { const f = `${root}/out/stills/s_${t.toFixed(2)}.png`; writeFileSync(f, await grab(t)); files.push(f); console.log('still', t); }
    const cols = Math.min(5, files.length);
    execSync(`ffmpeg -v error -y ${files.map((f) => `-i ${f}`).join(' ')} -filter_complex "${files.map((_, i) => `[${i}]scale=270:480[s${i}]`).join(';')};${files.map((_, i) => `[s${i}]`).join('')}xstack=inputs=${files.length}:layout=${files.map((_, i) => `${(i % cols) * 270}_${Math.floor(i / cols) * 480}`).join('|')}:fill=black" ${root}/out/stills_grid.jpg`);
    console.log('wrote out/stills_grid.jpg');
  } else {
    const from = +opt('--from', 0), to = +opt('--to', N);
    const out = opt('--out', `${root}/out/kitten_rescue${from || to !== N ? `_${from}_${to}` : ''}.mp4`);
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      ...(args.includes('--audio') ? ['-i', opt('--audio'), '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k'] : []),
      '-c:v', 'libx264', '-profile:v', 'high', '-crf', '17', '-preset', 'slow', '-pix_fmt', 'yuv420p',
      '-vf', 'scale=out_color_matrix=bt709:out_range=tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
      '-movflags', '+faststart', '-frames:v', String(to - from), out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let n = from; n < to; n++) {
      const png = await grab(n / FPS);
      if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
      if (n % 15 === 0) console.log(`frame ${n}/${to}  ${((Date.now() - t0) / 1000 / (n - from + 1)).toFixed(2)} s/frame`);
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('exit', r));
    console.log('wrote', out);
  }
} finally { await browser.close(); srv.kill(); }
