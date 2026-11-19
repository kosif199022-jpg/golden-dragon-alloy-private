// shot.js URL|FILE OUT [--w 1440] [--h 900] [--full] [--scale 1] [--wait 1500] [--mobile] [--dark] [--selector CSS]
// OUT ending .png/.jpg -> screenshot; .pdf -> printed PDF (A4 unless --w/--h given in px).
// Headless Chromium from the sandbox's Playwright (NODE_PATH=/usr/local/lib/node_modules, set by hfc).
const { chromium, devices } = require('playwright');
const fs = require('fs'), path = require('path');
const argv = process.argv.slice(2);
if (argv.length < 2) { console.error('usage: hfc shot URL|FILE OUT [--w --h --full --scale --wait --mobile --dark --selector]'); process.exit(2); }
const [src, out] = argv;
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i > 0 ? argv[i + 1] : d; };
const flag = k => argv.includes('--' + k);
const url = /^[a-z]+:\/\//i.test(src) ? src : 'file://' + path.resolve(src);
(async () => {
  const t = Date.now();
  const b = await chromium.launch();
  const ctxOpt = flag('mobile') ? { ...devices['iPhone 13'] } : { viewport: { width: +opt('w', 1440), height: +opt('h', 900) }, deviceScaleFactor: +opt('scale', 1) };
  if (flag('dark')) ctxOpt.colorScheme = 'dark';
  const ctx = await b.newContext(ctxOpt);
  const page = await ctx.newPage();
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => { console.error('shot: goto', e.message); return null; });
  await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
  await page.waitForTimeout(+opt('wait', 800));
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  if (out.toLowerCase().endsWith('.pdf')) {
    const po = { path: out, printBackground: true };
    if (argv.includes('--w')) { po.width = opt('w') + 'px'; po.height = opt('h', 900) + 'px'; } else po.format = 'A4';
    await page.pdf(po);
  } else {
    const so = { path: out, fullPage: flag('full') };
    if (/\.jpe?g$/i.test(out)) { so.type = 'jpeg'; so.quality = 90; }
    if (opt('selector')) await page.locator(opt('selector')).first().screenshot(so); else await page.screenshot(so);
  }
  console.log(`shot: ${out} http=${resp ? resp.status() : '-'} title=${JSON.stringify((await page.title()).slice(0, 80))} bytes=${fs.statSync(out).size} ms=${Date.now() - t}`);
  await b.close();
})().catch(e => { console.error('shot: ERROR', e.message); process.exit(1); });
