#!/usr/bin/env node
/* Maven Reels renderer. (c) 2026 Maven, @maven.iqq / maveniqq. See rights/MAVEN-RIGHTS.txt
   node scripts/render.mjs reel.html out.mp4 [--res 1080|720|1440|4k] [--voice vo.mp3] [--music bed.mp3] [--music-db -18]
        [--from s] [--to s] [--workers n] [--raw]
   node scripts/render.mjs reel.html sheet.jpg --sheet [--every 1]   one frame every N seconds, tiled
   node scripts/render.mjs reel.html still.png --still 3.4            one frame
   Always writes <out>.cues.json: the sound cues the reel asked for (pop, land, tick, notify ...). */
import { createRequire } from "node:module";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = argv.indexOf("--" + name);
  if (i < 0) return fallback;
  const next = argv[i + 1];
  return next !== undefined && !next.startsWith("--") ? next : true;
};
const [pagePath, outPath] = argv;
if (!pagePath || !outPath || pagePath.startsWith("--")) {
  console.error("usage: render.mjs reel.html out.mp4|sheet.jpg [--res 1080] [--voice f] [--music f] [--sheet] [--still t]");
  process.exit(1);
}
function playwright() {
  const req = createRequire(import.meta.url);
  const npmGlobal = spawnSync("npm root -g", { encoding: "utf8", shell: true }).stdout?.trim();
  const roots = [path.join(here, ".."), process.cwd(), ...(process.env.NODE_PATH || "").split(path.delimiter), npmGlobal].filter(Boolean);
  return req(req.resolve("playwright", { paths: roots }));
}
function ff(args, feed) {
  return new Promise((resolve, reject) => {
    const p = spawn("ffmpeg", ["-y", "-v", "error", ...args], { stdio: [feed ? "pipe" : "ignore", "inherit", "inherit"] });
    p.on("close", code => (code ? reject(new Error("ffmpeg exited with " + code)) : resolve()));
    if (feed) feed(p.stdin);
  });
}
function encoder() {
  for (const [name, flags] of [
    ["h264_nvenc", ["-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0"]],
    ["h264_videotoolbox", ["-q:v", "72"]],
  ]) {
    const test = spawnSync("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "color=black:s=640x360:d=0.1", "-c:v", name, "-f", "null", "-"]);
    if (test.status === 0) return { name, flags };
  }
  return { name: "libx264", flags: ["-preset", "veryfast", "-crf", "16"] };
}

const RES = { 720: 720, 1080: 1080, 1440: 1440, "2k": 1440, 2160: 2160, "4k": 2160 };
const res = RES[String(opt("res", "1080")).toLowerCase()];
if (!res) { console.error("--res must be 720, 1080, 1440 or 4k"); process.exit(1); }
const url = pathToFileURL(path.resolve(pagePath)).href;
const chromium = playwright().chromium;
const started = Date.now();

async function openPage(scale) {
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files", "--disable-web-security", "--font-render-hinting=none"] });
  const probe = await browser.newPage();
  const errors = [];
  probe.on("pageerror", e => errors.push(e.message));
  await probe.goto(url);
  const size = await probe.evaluate(() => window.reel ? { w: reel.W, h: reel.H, d: reel.duration, fps: reel.fps } : null);
  if (!size) { console.error("the page did not create a reel (R.reel). Errors:", errors.join(" | ") || "none"); process.exit(1); }
  await probe.close();
  const page = await browser.newPage({ viewport: { width: size.w, height: size.h }, deviceScaleFactor: scale ?? res / Math.min(size.w, size.h) });
  page.on("pageerror", e => console.error("page error:", e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) console.error("console:", m.text()); });   // a missing words.js is normal
  await page.goto(url);
  await page.evaluate(() => reel.ready());
  await page.evaluate(() => reel.seek(0));
  await page.waitForTimeout(150);
  return { browser, page, size };
}
const shot = async (page, t, type = "jpeg") => {
  await page.evaluate(t => reel.seek(t), t);
  return page.screenshot({ type, quality: type === "jpeg" ? 92 : undefined, animations: "disabled", caret: "hide" });
};
const writeCues = async page => {
  const cues = await page.evaluate(() => reel.cues.slice().sort((a, b) => a.t - b.t));
  const file = outPath.replace(/\.[a-z0-9]+$/i, "") + ".cues.json";
  fs.writeFileSync(file, JSON.stringify(cues, null, 1));
  return cues.length;
};

if (opt("sheet", false)) {
  const { browser, page, size } = await openPage(360 / Math.min(1080, 1080));
  const every = +opt("every", 1);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "mreel-"));
  let n = 0;
  for (let t = 0; t <= size.d + 1e-6; t += every) fs.writeFileSync(path.join(dir, `s${String(n++).padStart(3, "0")}.jpg`), await shot(page, Math.min(t, size.d - .01)));
  await writeCues(page);
  await browser.close();
  const cols = Math.min(10, n), rows = Math.ceil(n / cols);
  await ff(["-i", path.join(dir, "s%03d.jpg"), "-vf", `scale=216:-2,tile=${cols}x${rows}:padding=4`, "-frames:v", "1", outPath]);
  fs.rmSync(dir, { recursive: true });
  console.log(`wrote ${outPath} (${n} frames, every ${every} s)`);
  process.exit(0);
}
if (opt("still", false) !== false) {
  const { browser, page } = await openPage();
  fs.writeFileSync(outPath, await shot(page, +opt("still"), outPath.endsWith(".png") ? "png" : "jpeg"));
  await browser.close();
  console.log("wrote", outPath);
  process.exit(0);
}

const first = await openPage();
const { w, h, d, fps } = first.size;
const from = +opt("from", 0), to = Math.min(+opt("to", d), d);
const frames = Math.round((to - from) * fps);
const workers = Math.max(1, +opt("workers", Math.min(8, os.cpus().length - 2)));
const enc = encoder();
const picture = outPath.replace(/\.mp4$/i, "") + ".picture.mp4";
const ow = Math.round(w * res / Math.min(w, h) / 2) * 2, oh = Math.round(h * res / Math.min(w, h) / 2) * 2;
console.log(`${frames} frames, ${ow}x${oh}, ${workers} workers, ${enc.name}`);
const cueCount = await writeCues(first.page);
const slots = [first, ...(await Promise.all(Array.from({ length: workers - 1 }, () => openPage())))];
const done = new Map();
let claimed = 0, written = 0, wake = () => {};
const nudge = () => { const f = wake; wake = () => {}; f(); };
const wait = () => new Promise(r => { const prior = wake; wake = () => { prior(); r(); }; });
const encoding = ff(["-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-", "-vf", `scale=${ow}:${oh}:flags=lanczos`, "-c:v", enc.name, ...enc.flags, "-pix_fmt", "yuv420p", "-r", String(fps), picture], stdin => {
  (async () => {
    while (written < frames) {
      if (!done.has(written)) { await wait(); continue; }
      const buf = done.get(written);
      done.delete(written);
      if (!stdin.write(buf)) await new Promise(r => stdin.once("drain", r));
      written++;
      if (written % fps === 0) process.stdout.write(`\rframe ${written}/${frames}`);
      nudge();
    }
    stdin.end();
  })();
});
await Promise.all(slots.map(async ({ page }) => {
  while (claimed < frames) {
    const f = claimed++;
    while (f - written > workers * 4) await wait();
    done.set(f, await shot(page, from + f / fps));
    nudge();
  }
}));
await encoding;
await Promise.all(slots.map(s => s.browser.close()));
process.stdout.write("\n");
console.log(`picture done in ${((Date.now() - started) / 1000).toFixed(1)} s, ${cueCount} sound cues in ${outPath.replace(/\.mp4$/i, "")}.cues.json`);

const voice = opt("voice", null), music = opt("music", null);
if (!voice && !music) {
  fs.renameSync(picture, outPath);
} else {
  const inputs = [], parts = [], names = [];
  let n = 0;
  const seconds = (to - from).toFixed(3);
  if (voice) { inputs.push("-ss", String(from), "-i", voice); parts.push(`[${n}:a]aresample=48000,apad,atrim=0:${seconds},asetpts=N/SR/TB[a${n}]`); names.push(`[a${n}]`); n++; }
  if (music) {
    inputs.push("-stream_loop", "-1", "-i", music);
    parts.push(`[${n}:a]aresample=48000,atrim=0:${seconds},asetpts=N/SR/TB,volume=${opt("music-db", -18)}dB,afade=t=out:st=${Math.max(0, to - from - .8)}:d=.8[a${n}]`);
    names.push(`[a${n}]`); n++;
  }
  const join = names.length > 1 ? `${parts.join(";")};${names.join("")}amix=inputs=${names.length}:duration=first:normalize=0,aformat=channel_layouts=stereo[mix]` : `${parts[0]};${names[0]}aformat=channel_layouts=stereo[mix]`;
  const mixWav = outPath.replace(/\.mp4$/i, "") + ".mix.wav";
  await ff([...inputs, "-filter_complex", join, "-map", "[mix]", "-c:a", "pcm_s16le", mixWav]);
  let filter = "anull";
  if (!opt("raw", false)) {           // two-pass: -14 LUFS, about -1.5 dBTP after AAC
    const log = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", mixWav, "-af", "loudnorm=I=-14:TP=-2:LRA=20:print_format=json", "-f", "null", "-"], { encoding: "utf8" }).stderr;
    const m = JSON.parse(log.slice(log.lastIndexOf("{"), log.lastIndexOf("}") + 1));
    filter = `loudnorm=I=-14:TP=-2:LRA=20:linear=true:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:print_format=none,aresample=48000`;
  }
  await ff(["-i", picture, "-i", mixWav, "-map", "0:v:0", "-map", "1:a:0", "-af", filter, "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", outPath]);
  fs.rmSync(mixWav);
  fs.rmSync(picture);
}
console.log(`wrote ${outPath} in ${((Date.now() - started) / 1000).toFixed(1)} s`);
