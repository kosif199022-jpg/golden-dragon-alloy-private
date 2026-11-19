// Character preview: front + 3/4 turnaround of the man and the kitten, plus key story frames -> out/preview_man.jpg
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
mkdirSync(root + '/out/preview', { recursive: true });
execSync('npx vite build', { cwd: root, stdio: 'ignore' });
const srv = spawn('npx', ['vite', 'preview', '--port', '4173', '--strictPort'], { cwd: root, stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 2500));
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const files = [];
async function shot(q, t, name) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto('http://localhost:4173/?render=1' + q);
  await page.waitForFunction(() => window.__kosif && window.__kosif.ready, null, { timeout: 120000 });
  const b64 = await page.evaluate((t) => { window.__kosif.seek(t); return document.querySelector('canvas').toDataURL('image/png').split(',')[1]; }, t);
  const f = `${root}/out/preview/${name}.png`; writeFileSync(f, Buffer.from(b64, 'base64')); files.push(f); await page.close(); console.log(name);
}
try {
  await shot('&sheet=0', 0, 'a_front');
  await shot('&sheet=0.7', 0, 'b_three_quarter');
  for (const t of [3.95, 7.2, 10.6, 16.5]) await shot('', t, 'c_' + t);
  execSync(`ffmpeg -v error -y ${files.map((f) => `-i ${f}`).join(' ')} -filter_complex "${files.map((_, i) => `[${i}]scale=540:960[s${i}]`).join(';')};${files.map((_, i) => `[s${i}]`).join('')}xstack=inputs=${files.length}:layout=0_0|540_0|1080_0|0_960|540_960|1080_960" ${root}/out/preview_man.jpg`);
  console.log('wrote out/preview_man.jpg');
} finally { await browser.close(); srv.kill(); }
