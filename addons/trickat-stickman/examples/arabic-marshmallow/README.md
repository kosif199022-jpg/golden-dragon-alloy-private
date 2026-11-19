# مثال: اختبار المارشميلو وفلوسك (Arabic example)

A tested 1:16 Arabic video, built the way the skill works: a voiceover + its SRT → `srt` → `story.json` → render.

- `subs.srt`: the subtitles of the voiceover (16 cues; cues 3-4 and 10-11 are one sentence split in two, like CapCut does).
- `story.json`: 16 shots covering units 0-15, using wide, closeup (with a thought bubble), skyline, title (silent chapter card and a spoken punchline), icon, versus, crowd, chart, counter, list, table (phone + receipt, newspaper with a ring), walk and a polaroid ending. All on-screen text is Arabic, and every `at` cue is a word copied from the SRT.

The voiceover itself is not included. To try the pipeline, record or generate an Arabic voice that reads the SRT text, export its own SRT, put both in a project folder, and run:

```
python3 -m engine srt <P>        # SRT + voice -> timing.json (prints the numbered units)
python3 -m engine plan <P>       # after copying story.json into <P>
python3 -m engine stills <P>
python3 -m engine all <P>
```

The `map` shot isn't in this example; see `references/story-format.md` for its fields.
