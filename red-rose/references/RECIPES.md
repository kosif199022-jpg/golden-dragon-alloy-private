# Red Rose recipes (V29, W08)

Eight recipes are fixed by id. Each one is a JSON file in `recipes/` that calls catalogue ops in order and checks a gate after every step. Run one with a single command.

```
python -X utf8 rose.py recipes
python -X utf8 rose.py recipe show ID
python -X utf8 rose.py recipe validate
python -X utf8 rose.py recipe run ID key=value ... --work DIR
python -X utf8 rose.py recipe run ID key=value ... --work DIR --approve-write
python -X utf8 rose.py recipe selftest ID
```

## Approval and outcomes

- A step that writes (`effect: write`, or a `save` into a file) does nothing without `--approve-write`. Read steps still run, so the owner sees the measured result first. The run then lists `would_write` and exits **3**.
- Exit codes follow `references/INTERFACE.md`: 0 ok, 1 error (includes a failed gate and a missing required input), 3 approval_required, 4 unavailable_here, 5 example_only.
- A failing gate stops the run at that step and names it in `failed_gate`.
- With `--approve-write`, each step's envelope is written as `evidence-stepN.json` in the work folder. Outputs are never overwritten: rerun with a new work folder.
- Missing required input: exit 1 with `missing[]` carrying the Arabic question and suggestion. Nothing is invented or transcribed.

## The eight recipes

| id | Arabic | Steps (writes) | Gates | Deliverable |
|---|---|---|---|---|
| `title-frame-ar` | إطار عنوان متحرك بالعربي (PNG) | 1 (1) | Arabic shaping ok, PNG written | PNG 1080x1920 + SVG |
| `title-clip-mp4` | كليب عنوان متحرك MP4 | 1 (1) | verify_video (h264, yuv420p, frames = round(duration × fps), even size, first frame not black, no audio) | MP4 |
| `shot-report-recut` | تقرير اللقطات وإعادة القص | 2 (1) | shots and suggested cut present; verify_video (AAC, no black first frame) | shot report (shown) + recut MP4 |
| `captions-from-words` | كابشن من الكلام بالحرف | 1 (1) | caption strings equal the supplied words byte for byte (tashkeel included) | caption PNG + SVG |
| `loudness-fix` | ضبط مستوى الصوت (LUFS) | 3 (1) | measured before; after the write, integrated LUFS within 1.0 of target | m4a (AAC) |
| `bank-reconcile` | مطابقة كشف البنك مع الدفتر | 1 (0) | not example data; counts present | report (shown) |
| `iphone-export` | تصدير فيديو للآيفون (رأسي) | 1 (1) | verify_video (AAC if present, frames, first frame, even size) | MP4 |
| `beat-synced-cut` | قص على إيقاع الموسيقى | 2 (1) | beats measured; verify_video | MP4 cut on beats |

The "when" examples in each JSON are the Arabic and English requests the router uses (at least two Arabic, one English).

## Recipe JSON

```
{id, title_ar, title_en, status: ready|draft, when: [...], tags, deliver_ar, place: any|needs_ffmpeg|pc_only,
 inputs: [{key, type: string|path|number|integer|bool|json_file, required, default, impact, redo,
           question_ar, suggest_ar}],
 steps: [{n, do_ar, op: "ADAPTER.OP", args, effect: read|write, approval, save?, deliver?,
          gate: [{text_ar, check, expect}]}],
 approvals: [{step, text_ar}], rules: [...], selftest: {inputs: {key: value | "@FIXTURE"}, approve}}
```

- `args` values: `"${input}"` (typed by the input's `type`), `"${work}/file"`, `"${sN.field}"` (a field from step N's result), with transforms `|keep:a,b`, `|first:N`, `|consecutive:N` (points into `{start,end}` segments).
- `save`: `{FIELD: "${work}/file"}`, written with `rose_io.save_fields` (png_base64 becomes a PNG).
- Gate checks: `verify_video`, `file_exists`, `json_path` (`field` or `path` with `equals`, `min_len`, `not_empty` or `near`+`tol`), `equals_input`, `not_example`.
- Rules are documentation names: aac_in_mp4, no_black_first_frame, no_fade_from_black, no_overlays_unless_named, captions_exact_words, arabic_shaped, frames_match_duration, even_dimensions.

## Limits (measured, not promised)

- No recipe adds an overlay, fade, bloom or filter that the owner did not name. Title styles such as `fade_up` are text animations inside the op, not ffmpeg filters.
- `title-clip-mp4`, `iphone-export` and `shot-report-recut` outputs have no audio track unless the source has one (the gate allows none or AAC).
- `loudness-fix` writes the normalised audio (m4a). It does not re-mux the video: no catalogue op does that.
- `captions-from-words` writes a caption frame, not a burned-in video. It needs the speaker's own timed words; it never transcribes or invents them.
- `beat-synced-cut` cuts between the first 8 detected beats only.
- Arabic caption tashkeel placement is the renderer's; the text itself is verified byte-equal.
