// Font matcher: render the same text with every candidate font, fit it into the reference text box and
// score the overlap with the reference ink mask. usage: node match.mjs job.json > scores.json
// job: {mask: "mask.png" (white ink on black, cropped to the ink box), text, ltr, fonts: [paths], weights: [400,700]}
import { chromium } from 'playwright'; import http from 'http'; import fs from 'fs'; import path from 'path';
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const files = new Map(); job.fonts.forEach((f, i) => files.set(`/f${i}${path.extname(f).toLowerCase()}`, f));
files.set('/mask.png', job.mask);
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  if (u === '/') { s.writeHead(200, { 'Content-Type': 'text/html' }); return s.end('<meta charset=utf-8><canvas id=c></canvas>'); }
  const f = files.get(u); if (!f || !fs.existsSync(f)) { s.writeHead(404); return s.end(); }
  s.writeHead(200, { 'Content-Type': 'application/octet-stream' }); fs.createReadStream(f).pipe(s);
}).listen(0);
await new Promise(r => srv.on('listening', r));
const b = await chromium.launch(); const pg = await b.newPage();
await pg.goto(`http://localhost:${srv.address().port}/`);
const out = await pg.evaluate(async ({ n, exts, text, ltr, weights }) => {
  const im = new Image(); im.src = '/mask.png'; await im.decode();
  const MH = 96, MW = Math.max(8, Math.round(im.width * MH / im.height));
  const mc = new OffscreenCanvas(MW, MH), mx = mc.getContext('2d'); mx.drawImage(im, 0, 0, MW, MH);
  const md = mx.getImageData(0, 0, MW, MH).data, ref = new Uint8Array(MW * MH);
  for (let i = 0; i < ref.length; i++) ref[i] = md[i * 4] > 127 ? 1 : 0;
  const dil = (a) => { const o = new Uint8Array(a.length); for (let y = 0; y < MH; y++) for (let x = 0; x < MW; x++) { let v = 0; for (let dy = -1; dy <= 1 && !v; dy++) for (let dx = -1; dx <= 1; dx++) { const yy = y + dy, xx = x + dx; if (yy >= 0 && yy < MH && xx >= 0 && xx < MW && a[yy * MW + xx]) { v = 1; break; } } o[y * MW + x] = v; } return o; };
  const refD = dil(ref);
  const cv = new OffscreenCanvas(2400, 400), c = cv.getContext('2d', { willReadFrequently: true });
  const res = [];
  for (let i = 0; i < n; i++) {
    let ff; try { ff = new FontFace('F' + i, `url(/f${i}${exts[i]})`); await ff.load(); document.fonts.add(ff); } catch (e) { res.push({ i, err: 'load' }); continue; }
    for (const w of weights) {
      c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, 2400, 400); c.fillStyle = '#fff';
      c.font = `${w} 200px F${i}`; c.direction = ltr ? 'ltr' : 'rtl'; c.textAlign = 'center'; c.fillText(text, 1200, 280);
      const d = c.getImageData(0, 0, 2400, 400).data; let x0 = 2400, y0 = 400, x1 = -1, y1 = -1;
      for (let y = 0; y < 400; y++) for (let x = 0; x < 2400; x++) if (d[(y * 2400 + x) * 4 + 3] > 100) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      if (x1 < 0) { res.push({ i, w, err: 'empty' }); continue; }
      const iw = x1 - x0 + 1, ih = y1 - y0 + 1;
      const t = new OffscreenCanvas(MW, MH), tx = t.getContext('2d'); tx.drawImage(cv, x0, y0, iw, ih, 0, 0, MW, MH);
      const td = tx.getImageData(0, 0, MW, MH).data, got = new Uint8Array(MW * MH);
      for (let k = 0; k < got.length; k++) got[k] = td[k * 4 + 3] > 127 ? 1 : 0;
      const gotD = dil(got); let inter = 0, uni = 0, a = 0, bb = 0, hitA = 0, hitB = 0;
      for (let k = 0; k < got.length; k++) { if (ref[k] && got[k]) inter++; if (ref[k] || got[k]) uni++; if (ref[k]) { a++; if (gotD[k]) hitA++; } if (got[k]) { bb++; if (refD[k]) hitB++; } }
      const iou = uni ? inter / uni : 0, soft = (a && bb) ? 2 / (1 / (hitA / a) + 1 / (hitB / bb)) : 0;
      const natural = iw / ih, wanted = MW / MH, sx = wanted / natural;          // horizontal stretch needed
      const score = (0.5 * iou + 0.5 * soft) * Math.max(0, 1 - Math.abs(Math.log(sx)) * 0.8);
      res.push({ i, w, iou: +iou.toFixed(3), soft: +soft.toFixed(3), sx: +sx.toFixed(3), score: +score.toFixed(3) });
    }
    document.fonts.delete(ff);
  }
  return res;
}, { n: job.fonts.length, exts: job.fonts.map(f => path.extname(f).toLowerCase()), text: job.text, ltr: !!job.ltr, weights: job.weights || [400, 700] });
for (const r of out) r.font = job.fonts[r.i];
console.log(JSON.stringify(out));
await b.close(); srv.close();
