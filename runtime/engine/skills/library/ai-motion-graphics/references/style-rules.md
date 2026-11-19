# Style rules (learned from creator feedback)

Each rule came from a real revision request. Follow them by default; the user's current request wins if it conflicts.

## Look & feel
- Clean, contemporary, cinematic YouTuber vibe. Avoid neon purple/blue "futuristic AI" styling, flat 2D vector/cartoony UI, and cheap-looking stick figures or clip-art doodles.
- Prefer real textures: e.g. AI-generated chalk illustrations (white chalk on black, alpha from luminance) over hand-coded line art; felt/paper feel when the footage is crafty.
- Modern UI components: thin crisp lines with soft glow, frosted-glass capsules/pills (blurred background + light tint + thin white border), generous corner radii.
- Accent colour: one saturated accent pulled from the footage or the style's palette; avoid pastels.

## Text & readability (most frequent feedback)
- Text over footage: white, bold, strong soft shadow, plus a dark gradient behind the lower part of the frame. Black text over busy/dark video is unreadable.
- On light backgrounds (white grid, bright rooms) use charcoal or white-with-shadow + a subtle dark top/bottom scrim.
- Size up: captions ~56px, key phrase ~96px, pipeline labels ~32px bold, callout labels ~40px. "Too small" is a recurring note.
- Position near eye level / lower-middle. Nothing important at the very top of frame ("no one will see it"). Keep consecutive captions at the same height.
- Word-synced reveals: each word rises in on its SRT time (start ~0.04–0.1s early). Key words in clay or on a clay pill whose box is centred on the *ink bbox* of the text (measure glyph bounds, not layout box).
- Don't let text sit on top of the PiP or the face; put titles behind the person (matte) when depth is wanted, making sure hair/head overlap looks clean.

## Timing & edits
- Never cut between shots while a caption is on screen; hold the shot, fade the caption, then cut.
- Keep shots real-time. No frame-blended slow motion (blurry). For "analysis" moments, hold one sharp frame instead.
- Pick footage windows that show the interesting part (e.g. lock-on + rockets, pyramids popping up, mammoth era) — scan the clip with a contact sheet first.
- Make sure the final seconds land on a clean, settled moment, not mid-transition.

## Density
- Callouts: 2–3 maximum, dotted white boxes + dotted white arrows + white text (no coloured pills), shown one at a time, cleared before action beats. If asked, remove them entirely.
- Tracking/analysis visuals: fewer, bolder elements beat many thin ones. Dim/desaturate the video ~30% during analysis so white overlays pop.
- Tethers/leader lines only if they truly connect to something tracked; otherwise drop them.

## Motion
- Before/after slider: glide in fast and ease down near the middle, crawl slowly (not stopped) for ~1.5–2s so both sides can be compared, then accelerate out to full reveal.
- Screens around a speaker: form a gently curved wall behind the head/neck and drift slowly left→right; don't orbit. Materialise with particles + noise-dissolve; captions warped onto the same curve.
- Titles: rise per letter/word with eased overshoot; big word behind the head, then shrink into a top band.

## Sound
- Voice always dominant. SFX subtle and relevant. **No whooshes at all** (user: "that whoosh sound isn't the best") - use `Mixer.pop` for text/cards appearing, `Mixer.swell` (soft tonal chord) for big words/scene changes, `Mixer.glass` for UI panels, ticks for snaps/typing, a chime when a generation finishes. Prefer the shots' own audio as quiet beds (≈-16 dB) aligned to where each shot plays; add only a few UI cues (ticks, soft chime on a check, a sweep under a slider).
- Always re-time SFX when visual timing changes, and export an SFX-only stem.

## Branding
- Use the official logo file the user provides; never draw a brand logo. Resize in premultiplied alpha to avoid dirty corners; soft small shadow only.
