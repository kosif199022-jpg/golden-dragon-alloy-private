// usage: node render.mjs <webdir> <outdir> <frames "a-b" or "1,2,3"> [workers]
import { chromium } from 'playwright'; import http from 'http'; import fs from 'fs'; import path from 'path';
const [,, web, outdir, spec, nw = '1'] = process.argv;
fs.mkdirSync(outdir, { recursive: true });
let frames = []; for (const part of spec.split(',')) { if (part.includes('-')) { const [a, b] = part.split('-').map(Number); for (let f = a; f <= b; f++) frames.push(f); } else frames.push(+part); }
frames = frames.filter(f => !fs.existsSync(path.join(outdir, `f${String(f).padStart(4, '0')}.jpg`)));
const types = { '.js': 'text/javascript', '.html': 'text/html', '.ttf': 'font/ttf', '.jpg': 'image/jpeg' };
const srv = http.createServer((q, s) => { const p = path.join(web, decodeURIComponent(q.url.split('?')[0])); if (!fs.existsSync(p)) { s.writeHead(404); return s.end(); } s.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(s); }).listen(0);
await new Promise(r => srv.on('listening', r));
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const t0 = Date.now(); let done = 0;
async function worker(list) {
  const pg = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  pg.on('pageerror', e => console.log('ERR', e.message));
  await pg.goto(`http://localhost:${srv.address().port}/index.html`);
  await pg.waitForFunction(() => window.ready, null, { timeout: 60000 });
  for (const f of list) {
    const d = await pg.evaluate(async f => { await window.renderFrame(f); return document.getElementById('c').toDataURL('image/jpeg', .93); }, f);
    fs.writeFileSync(path.join(outdir, `f${String(f).padStart(4, '0')}.jpg`), Buffer.from(d.split(',')[1], 'base64'));
    if (++done % 50 === 0) console.log(done, '/', frames.length, ((Date.now() - t0) / done / 1000).toFixed(2), 's/frame');
  }
}
const n = +nw, lists = Array.from({ length: n }, (_, i) => frames.filter((_, j) => j % n === i));
await Promise.all(lists.map(worker));
console.log(`done ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
await b.close(); srv.close();
