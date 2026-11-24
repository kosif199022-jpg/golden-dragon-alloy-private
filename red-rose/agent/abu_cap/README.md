# Abu Cap cartoon engine (Cap & Nadara)

Flat stickman look measured on the owner's @elkosif1 reels (Df70OqepDTH, the Abu Cap lions reel):
sky gradient, rotating sun, clouds, lavender mountains with snow caps, green hill, lollipop trees, red barn,
wooden fence, grass with tufts and flowers, «© Mahmoud Elkosif» bottom right, and the end card
«مونتاج وإخراج Mahmoud Elkosif» + «تابعني على فيسبوك» (yellow) with both characters on a cloud.

- **Cap** (أبو كاب): red capsule body, red baseball cap with brim to the facing side, rosy cheeks.
- **Nadara** (نضارة): blue capsule body, black spiky hair, round glasses.
- `stick(ctx, pose)` draws either one: walk phase, arm targets, eyes (dot/wide/happy/closed), mouth
  (smile/grin/o/shout/flat/worry), lean, rotation, fright (hair spikes), cap pop, sweat drop.
- `puma(ctx, q)`: mountain lion (crouch, growl, scared, run). Props: bush, thought bubble, light bulb,
  speed lines, dust, roar and shout arcs, sparkle, pop-up «!!» and «؟».

`web/main.js` holds the 27 s story «كبّر نفسك» (2026-11-24): a mountain lion appears, Nadara tries to run,
Cap stops him, climbs on his shoulders and spreads his jacket, the lion runs away, high five, tip card.
Render: `node ../fast_reel/render.mjs web frames 0-809 4` (about 60 s on Higgsfield XL), then mix the
music (Happy Ukulele, Jason Shaw, CC BY 3.0, credit in the caption) and sox-synthesised effects, -14 LUFS.
For a new story keep the drawing functions and rewrite `scene(t)`, `lion(t)` and the on-screen words.
