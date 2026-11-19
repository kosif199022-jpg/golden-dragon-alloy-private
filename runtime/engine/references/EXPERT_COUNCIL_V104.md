# Expert Council v10.4 — bridge integration

## Source
User-uploaded `expert-council.rar`, 10 source files (SKILL.md, council protocol, persona deck, four specialized domain guides, learning loop, lessons script, eval prompts). Files preserved under `skills/expert-council/`. The `evals.json` is a set of sample language-model prompts, not proof of model answers.

## New native CLI

From the extracted release root:

```bash
python scripts/dragon.py v10 council plan "راجع ريل 30 ثانية" --domain editing --size 5
python scripts/dragon.py v10 council audit examples/council-sample.json
python scripts/dragon.py v10 council lessons add --domain editing --trigger "voice below music" --mistake "voice was inaudible" --lesson "measure speech intelligibility and duck music"
python scripts/dragon.py v10 council lessons search "voice music" --domain editing
```

`--size` accepts 3, 5, 7. A plan declares distinct lenses and blank evidence fields. For every seat: position, observation(s) with a precise locator and corrective action, and confidence. In full/expanded councils add a substantive debate with both steelmanned positions, a discriminating test, a red-team pre-mortem, an explicit practical verdict and strongest dissent. Audit validates structural fields and optional SHA-256 of local files in the review packet directory. It **does not** run separate LLM agents, independently inspect timecodes, fact-check cited facts, adjudicate artistic quality, or prove independence.

## Private learning and permissions
Correction records are stored at `~/.black-dragon/expert-council/lessons.jsonl` by default, or an explicit `--store FILE` for an isolated project. Not included in release bundles. The original script is preserved for reference, while the native command avoids invoking it implicitly. No paid calls, network upload or other side effects during `plan`/`audit`. `lessons add` only writes the requested private ledger.

## Honest usage
- Source dossier: perspectives, not actual famous people speaking; never fabricate quotations.
- A role-simulated round is not multiple independent model calls.
- A SHA-256 match proves byte integrity only.
- A bare timecode/line locator is user-supplied and must be inspected separately.
- Source-origin claims about photographic or audio standards still need direct technical checks.
