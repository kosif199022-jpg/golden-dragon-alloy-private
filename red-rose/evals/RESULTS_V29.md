# Red Rose V29: measured results (W11, revised)

Plain summary of what was measured. Every number here comes from a run in this folder or from the holdout listed below. Anything not run is marked "not measured".

**Caveat first.** The routing requests are synthetic. An assistant wrote them in the owner's voice, and a second labeller agreed on each one. They are not real owner messages.

## Routing

Test split (80 requests, odd ids). It has been measured twice with record runs (`FREEZE.json` runs = 2). The first run was W11 (before this revision); the second is the record in this revision.

| | Before (W11, run 1) | After (this revision, run 2) |
|---|---|---|
| Top-1 | 13.75% (11 of 80) | **16.25%** (13 of 80) |
| Top-3 | 32.5% (26 of 80) | **38.75%** (31 of 80) |
| Acceptable | 13.75% | 18.75% |
| Abstention recall (6 rows should abstain) | 83.3% (5 of 6) | **66.7%** (4 of 6) |
| Abstention precision | 11.1% (5 of 45) | 11.4% (4 of 35) |

Dev split (80 requests, even ids, tuning split): top-1 21.25% before, **22.5%** after; top-3 38.75% before, **43.75%** after; abstention recall 60%, precision 12.5-13%.

- Top-1 on the test split is still poor. Even after the change the router is right on about one request in six. The earlier 26 of 30 figure was leave-one-out on the router's own paraphrases and is not an estimate of this.
- Abstention got worse on the test split (recall 83.3% to 66.7%) and is still far too eager (precision about 11%). The decode-first change is the likely cause: gibberish rows that used to abstain now decode and sometimes match a route. This was not fixed. The floor for abstention recall (0.833) is not lowered, so the floor test fails on this number.

By style (test split, top-1, after): English-only 33%; Arabic typed on the English layout 25% (was 8%, now decoded first); Egyptian with typos 5%; Egyptian 15%; mixed 33%.

Latency: p95 of one route call about 0.9 ms (test split).

### What changed in the router

- `route()` now decodes a layout-typed message (`understand`) before scoring. This is the only change that lifted the layout style (dev 0% to 25%).
- Tried and not kept: a fallback that answers with the best candidate when no candidate passes the acceptance rule. Dev top-1 rose by 2.5 points but abstention recall fell to 20%. It is off (`FALLBACK_MIN_SCORE = None`).
- Tried and not kept: changing the example-vote weight (0, 2, 4, 8). No change on dev.
- Tuning used only the dev split. Test-split labels were not inspected during tuning. One caveat, below.

### Caveat on the test split

`test_routing_floor_v29.py` calls `measure("test")` directly, so the floor test computed test-split numbers on intermediate code during development. Those numbers were not used to choose any change. The only official measurement is the `--record` run above.

## Abstention tier rule (fixed)

The W11 tier rule called the report "measured" when abstention recall was at least 0.8. That ignored precision. The rule now requires **both** abstention recall at least 0.8 **and** abstention precision at least 0.8 (`run_eval.py`, `ABSTAIN_PRECISION_MIN`). Under the new rule the router's tier is **unmeasured** (recall 66.7%, precision 11.4%). The previous "measured" tag overstated how reliable the abstentions are.

## Decoder (120 frozen cases, plus a fresh holdout)

Frozen file (`evals/decoder/cases.jsonl`):

| Kind | Before | After |
|---|---|---|
| Arabic typed on the English layout (16) | 0 of 16 | **12 of 16** |
| English-only, must stay identical (16) | 16 of 16 | 16 of 16 (no false positives) |
| Egyptian Arabic, must stay unchanged (88) | 86 of 88 | **84 of 88** |
| Total exact | 102 of 120 | 112 of 120 |

Two Egyptian inputs regressed: `clips` and `skills` (English words inside an Arabic message) are now decoded. Two others (dictation of `للايفون`) were already changed before this revision. The regression is a known trade-off, explained below. The 16 layout failures that remain are: 4 inputs with a converter ligature or shift-key ambiguity, and inputs with bigram collisions (`he`, `ed`).

Fresh holdout (60 new Arabic requests, written in the owner's domains before the final rule was frozen, stored at `scratchpad/holdout_ar.json`, not in the skill):

- First run (rule as written): **48 of 60** (80%). The failures included a leading-slash guard bug I had introduced (fixed).
- Second run, after the slash fix: **49 of 60** (81.7%).
- Third run, after the caps-lock split and the lexicon check: **49 of 60**.

The holdout has been run three times, and the rule changed between run 1 and run 2. The number is reported as a validation only, not as a tuned score. Failures are bigram collisions and converter ligatures.

### What changed in the decoder rule

The rule decodes a Latin token when the **whole message reads as Arabic**, not when the decoded word is in the small lexicon.

- Pass 1 weighs the message. Native Arabic words and layout-typed Latin tokens (at least 3 letters, English-bigram share 0.15 or less) count as Arabic evidence. English-lexicon words and tokens whose English-bigram share is 0.4 or more count as English evidence.
- Pass 2 decodes every candidate when Arabic evidence is greater than English evidence. With no English evidence at all, a token decodes only if its decoded form is a known Arabic word (the old rule, kept for short messages).
- Guards kept: URLs, flags, file names with an extension, numbers, paths (two or more `/`, a backslash, or a colon), tokens after a command word, and the English lexicon.
- Tokens that contain a Shift key typing a diacritic (Q W E R A S X) or Z stay as typed.
- Shift keys on the Arabic-101 table are now mapped (H=أ, K=،, G=لأ, J=ـ, and so on). An all-caps token uses the lowercase keys (Caps Lock). This is the table the frozen file was generated with.
- Lexicon additions: tech tokens (`obj`, `lufs`, `srt`, `svg`, `csv`, `json`, `aac`, `mp3`, `wav`, `fps`, `pdf`, `png`, `jpg`, `gif`, `api`, `url`, `mp4`), added so acronyms stay as typed.
- Fixture change: `upper-mixed` expects `أعمل ريل` for `Hulg vdg` (was `اعمل ريل`). That follows the Shift+H key on the Arabic-101 table, which is what the frozen file uses. The old expectation came from the caps rule, which I changed.

### What did not improve, and why

- The English-word-in-Arabic case (`clips`, `skills`). Bigrams alone cannot separate a layout token (score 0 to 0.33) from an English word (0.2 to 0.25). A threshold strict enough to keep `clips` costs about 6 of the frozen layout tokens. I chose to keep the layout recall and report the two regressions.
- Layout tokens with bigram collisions (`he`, `ed`) are kept as English. This is inherent to the bigram test.

## Floor and freeze

- Floor (`floor.json`, raised only): top-1 0.162, top-3 0.387, abstention recall **0.833** (not lowered, so the test fails at 0.667), decoder layout exact 12.
- `FREEZE.json`: runs = 2, hash `fd7e64f42c76...`. The record run is the second test measurement.
- `test_routing_floor_v29`: 6 of 7 pass. The one failure is the abstention-recall floor, as above.

## Journey (four fresh sub-agents, new skill, PowerShell 5.1)

- Result (W11, not re-run here): **0 of 4 jobs succeeded**. All four stopped before a deliverable.
- J1 stopped at the write gate with no approval, with a PowerShell quoting problem on Arabic arguments. J2 stopped because the CSV files were not in the test folder. J3 stopped with the one question the skill would ask. J4 stopped because `words.json` was missing.
- Counts are sub-agent self-reports. No transcripts were captured.

## Frozen set does not meet the spec (unchanged, from W11)

- The frozen set has 160 rows (acceptance: at least 120, passed).
- It has **11 abstention rows** (acceptance: at least 20, **failed**).
- Labeller agreement is 160 of 160, recorded in the set's own workflow stats. Not re-measured here.

## Not measured

- Labeller agreement as an independent check (only the recorded stats).
- Old-snapshot baseline (c5ec644) and the capability-plan top-3 baseline.
- Brief length by depth and brief timing.
- Journey CLI errors and source reads (no transcripts).
- Real owner traffic.
