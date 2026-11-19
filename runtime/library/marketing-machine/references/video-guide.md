# Video — the scene contract and three scene sources

Video runs through the same pipeline as a card: HTML → headless Chromium → output. The only
difference is that a scene declares a timeline, so instead of one frame the recorder takes N.

## The contract

Four globals, nothing else:

| Global | What it is |
|---|---|
| `window.__duration` | Total seconds |
| `window.__seek(t)` | Paint the scene at `t`. **Must be a pure function of `t`.** |
| `window.__ready` | `true` once fonts and layout have settled |
| `window.__provenance` | `real-recording` \| `driven-app` \| `simulation` — enforced by the linter |

Starting point: `templates/scene.html`.

## Why a pure function

The recorder does not play the page and capture the screen. For every frame it calls
`__seek(frame/fps)` and takes a screenshot. Therefore:

- **Banned:** CSS `transition` / `animation` / `@keyframes`
- **Banned:** `setTimeout` / `setInterval` / `requestAnimationFrame` driving any visual
- **Banned:** state that accumulates between `__seek` calls

The cost is more code than a CSS animation. What it buys is two things:

1. **Frames are reproducible.** The wall-clock speed of the capture is irrelevant; the same scene
   yields the same bytes.
2. **You can verify a frame instead of reviewing a video.** The output of `--shot 6.5` is byte-for-byte
   frame 195 at 30fps. Confirming a moment is correct does not require watching anything.

The second one is the real prize. An audience noticing that a number on screen is wrong is the most
expensive kind of mistake, and a frame-verifiable pipeline catches it before the recording exists.

## Measure, do not guess

Two things break when the language changes, and neither should be a hardcoded number:

- **Typing:** use a fixed **rate** (characters per second), not a fixed duration. A German question
  runs roughly 40% longer than its English equivalent; squeezed into the same window it stops
  looking typed and starts looking pasted. Every timestamp after the question shifts as a result,
  so per-language durations differ. That is correct, not a bug.
- **Scroll targets:** paragraphs wrap differently in every language. Measure the target from the DOM
  (`getBoundingClientRect`) rather than writing a pixel offset.

## Camera (optional layer)

In a social feed a video plays around 400px wide. On 1920px output that is a 0.21x reduction: 13px
text becomes 2.7px, which is to say invisible. Legibility bottoms out around 9px.

The answer is not a fixed zoom but **framing by CSS selector**: say which element each beat is
about, and **derive** the zoom from that element's box. A forced zoom crops the subject whenever the
box is large. Re-measure the frame every tick so the camera follows the element as the page scrolls.
When a selector matches nothing, that beat should do nothing (hold the previous framing) and the run
should report the unmatched selectors at the end.

For long text, prefer a slow reading scroll over one fixed shot.

## Provenance — the mandatory honesty record

Every scene declares how its footage came to exist:

```js
window.__provenance = 'simulation';
```

| Value | Meaning |
|---|---|
| `real-recording` | An actual screen capture |
| `driven-app` | The real application, automated and captured |
| `simulation` | The interface reconstructed in code |

**A simulation is not a screen recording and must never be shared as one.** Record it in the post
file as well.

The declaration lives in the scene rather than in a side-car file on purpose: a rule that only reads
copy files is bypassed by not writing one, and this is the one rule where bypassing it means
misrepresenting reality to an audience.

If you keep scene copy in a `<name>.copy.json` — worth doing, because the linter can read a JSON
file but not text buried in markup — declare `provenance` there too.

## Three scene sources

The scene is what the recorder plays. There are three ways to get one, and none of them fits every
case.

| Route | Cost | Control | Suits |
|---|---|---|---|
| **1 · Real screen recording** | Lowest | Lowest — framing, language and timing are fixed at capture | A product whose UI changes fast and can show live data |
| **2 · Drive the app with automation** | Medium | High — but needs a running app, data and a licence | A web app that runs headless |
| **3 · Reconstruct by hand** | Highest | Total — frame by frame, language by language | A desktop app, or a flow that needs real data or a licence |

Default: **2** for a web app that runs headless, **1** for desktop, **3** only when neither works.

For route 1, embed the capture as a `<video>` element and set `video.currentTime = t` inside
`__seek`. The element hands you time control, so purity is preserved.

Route 3's cost should be stated plainly: it means redrawing the product's interface. What you get
back is total control and no dependency on a running application. Copy the colors and fonts from the
product's own source rather than eyeballing them, and re-copy when the theme changes.

## The verification tier — actually execute what is on screen

If a scene shows an artifact (a query, a calculation, code, a figure) and claims it is correct, then
prove it. In order:

1. **EXTRACT** — read the artifact out of the **rendered page**, not out of the source. What is
   actually visible in the video is what gets tested.
2. **FORMAT** — run it back through the product's own formatter. If the formatter is idempotent the
   result must be identical. A diff means the scene is showing a hand-written artifact that the
   product itself would have reformatted.
3. **EXECUTE** — run it against a real engine inside a transaction, then roll back. Nothing
   persists.
4. **DERIVE** — recompute every figure on screen from the artifact's own formula. A rounding drift is
   only ever caught this way.

Also check that no unresolved i18n key (`⟨query.generate⟩` and friends) survived to the screen: if
one language's dictionary failed to load, this catches it before the video does.

These steps are product-specific, so `marketing-machine` does not run them. Write them as a
`verify/` script next to the scene and run it alongside `lint` in CI.

## Maintenance

When the product UI changes: open the corresponding component, update the matching block in the
scene, and check that frame with `--shot <sec>`. If you added anything that changes height,
**re-measure** the scroll targets instead of nudging them.

If you touched artifacts or figures, run **all** the verification scripts.
