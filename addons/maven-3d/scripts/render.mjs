// Render frames from a Maven 3D project on the GPU.
//   node render.mjs <project> frames <fps> [fromFrame] [toFrame]   -> <project>/frames/f00000.jpg ...
//   node render.mjs <project> stills 0.5,1.2,3.0 [outdir]          -> <project>/check/t_0.50.jpg ... (default outdir)
// env PAGE=index.html?story=gallery.js to render another story file.
import { chromium } from 'playwright'; import http from 'http'; import fs from 'fs'; import path from 'path';
const [, , proj, mode, a, b, c] = process.argv;
if (!proj || !mode) { console.log('usage: node render.mjs <project> frames <fps> [from] [to] | stills t1,t2,... [outdir]'); process.exit(1); }
const root = path.resolve(proj, 'web');
const types = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.ttf': 'font/ttf', '.png': 'image/png', '.jpg': 'image/jpeg' };
const srv = http.createServer((q, s) => { const p = path.join(root, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { s.writeHead(404); return s.end(); } s.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(s); }).listen(0);
await new Promise(r => srv.on('listening', r));
const br = await chromium.launch({ args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'] });
const pg = await br.newPage({ viewport: { width: 1080, height: 1920 } });
pg.on('pageerror', e => console.log('PAGE ERROR', e.message)); pg.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
await pg.goto(`http://localhost:${srv.address().port}/${process.env.PAGE || 'index.html'}`);
await pg.waitForFunction(() => window.READY || window.ERR, null, { timeout: 120000 });
const err = await pg.evaluate(() => window.ERR); if (err) { console.log('story error:', err); process.exit(1); }
const gpu = await pg.evaluate(() => { const g = DBG.renderer.getContext(), e = g.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?'; });
if (/SwiftShader/i.test(gpu)) console.log('WARNING: rendering on SwiftShader (CPU), it will be slow:', gpu);
let jobs = [], outdir;
if (mode === 'stills') { outdir = path.resolve(b || path.join(proj, 'check')); jobs = a.split(',').map(Number).map(t => [t, `t_${t.toFixed(2)}.jpg`]); }
else { outdir = path.resolve(proj, 'frames'); const fps = +a, end = await pg.evaluate(() => window.END); const f0 = +(b || 0), f1 = c != null ? +c : Math.round(end * fps) - 1; for (let f = f0; f <= f1; f++) jobs.push([f / fps, `f${String(f).padStart(5, '0')}.jpg`]); fs.writeFileSync(path.join(proj, 'render.json'), JSON.stringify({ fps, end })); }
fs.mkdirSync(outdir, { recursive: true });
const t0 = Date.now();
for (const [t, name] of jobs) { const d = await pg.evaluate(t => { window.seek(t); return document.getElementById('c').toDataURL('image/jpeg', 0.93); }, t); fs.writeFileSync(path.join(outdir, name), Buffer.from(d.split(',')[1], 'base64')); }
console.log(`done ${jobs.length} frames in ${outdir}, ${((Date.now() - t0) / Math.max(1, jobs.length)).toFixed(0)} ms/frame`);
const shots = await pg.evaluate(() => window.SHOTLIST), END = await pg.evaluate(() => window.END); fs.writeFileSync(path.join(proj, 'shots.json'), JSON.stringify({ end: END, shots }));
console.log('shots', JSON.stringify(shots));
await br.close(); srv.close();
