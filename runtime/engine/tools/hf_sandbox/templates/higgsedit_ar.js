// Black Dragon v1990 — higgsedit starter with Arabic. Ran as-is on 2026-11-11 at 1080x1920 / 30 fps: 90 frames, 24.4 ms/frame, no credit debit.
//   higgsedit new ~/job/p1 --size 1080x1920 --fps 30 ; replace p1/edit.js with this ; higgsedit build p1/edit.js
// MEASURED: Arabic text renders NOTHING with the default font. Always set fontFamily to a face that has Arabic
// (DejaVu Sans ships in the sandbox; better: fetch Cairo/Amiri with bootstrap.sh) and direction "rtl".
// API types: /opt/fable/types/fable.d.ts (copied into the project as fable.d.ts).
/** @type {import("./fable").BuildScript} */
export default async function edit({ project, text, rect }) {
  const AR = "DejaVu Sans";            // swap for Cairo once the font is installed and visible in fc-list
  const p = await project({ size: "1080x1920", fps: 30, background: "#0b0b10" });
  p.compose([
    text("التنين الأسود", { x: 80, y: 660, width: 920, fontSize: 144, fontFamily: AR, direction: "rtl", color: "#f4f4f5",
      animate: [{ property: "opacity", from: 0, to: 1, duration: 0.9, easing: "house" }] }),
    text("KOSIF", { x: 80, y: 920, width: 920, fontSize: 192, color: "#ff2b2b" }),
    rect({ x: 80, y: 1200, width: 400, height: 12, fill: "#ff6a2b",
      animate: [{ property: "scaleX", from: 0, to: 1, at: 0.5, duration: 0.7, easing: "house" }] }),
  ], { dur: 3 });
  await p.frame(1.5, "renders/check.png");   // LOOK at this still before the full render
  await p.render("renders/out.mp4");
}
