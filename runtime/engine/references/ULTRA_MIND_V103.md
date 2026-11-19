# Ultra Mind → Black Dragon 10.3 integration

## Origin and scope
User upload `ultra-mind.rar` (RAR5) contained eight content files: `SKILL.md`, five reference notes (books / creativity / failure-modes / research / verification), `scripts/scaffold.py`, `evals/evals.json`. They are preserved byte-for-byte under `skills/ultra-mind/`.

The source's seven cognitive steps are: understand (Polya), step back (outside view), diverge (ACH/Tree of Thoughts), execute precisely, falsify (Popper/pre-mortem), independently verify (Chain-of-Verification), and calibrate/deliver (Tetlock). L0–L3 levels reduce unnecessary overhead. Domain cards cover math, debugging, analysis, decision, forecast, creative, writing and general work.

## New executable integration

`python scripts/dragon.py v10 ultra plan "<task>" --domain general|math|code|analysis|decision|forecast|creative|writing --level L0|L1|L2|L3` emits a deterministic selection of prompts and checks, NOT an executed reasoning trace.

`python scripts/dragon.py v10 ultra audit review.json` validates multiple hypotheses and distinguishing evidence, selected alternative, counterexample and outside-view baseline where applicable. Optional `checks` support `file-sha256` with paths relative to the packet directory (no directory escapes / symlinks outside); these perform *actual* local hashing. An `external-reference` is recorded as not fact-checked, never a successful verification. Unsupported and shell-command checks are rejected. A successful structural audit means **format and file-integrity only**, not that conclusions are true.

`python scripts/dragon.py v10 ultra calibrate predictions.json` calculates proper scoring (Brier) on observed binary outcomes, with five fixed 20% bins and a constant-base-rate benchmark. Requires explicit, measured outcomes. Does not invent numbers, call external research or claim future predictive ability.

## Example review packet

```json
{
  "task": "Is a code rewrite warranted?", "domain": "decision", "level": "L2",
  "hypotheses": [
    {"id":"A","approach":"repair existing system","discriminator":"profile bottlenecks first"},
    {"id":"B","approach":"replace one module","discriminator":"compare test coverage and deployment risks"}
  ],
  "selected":"A", "falsifier":"If profiling demonstrates architectural bottlenecks",
  "outside_view":"Document existing failure rates and comparable teams",
  "checks":[{"kind":"external-reference","reference":"source to verify before deciding"}]
}
```

This satisfies structural requirements but the reference is *not* verified; use `file-sha256` receipts for actual local integrity checks. The sourced `evals.json` has seven **manual prompts**, not seven machine-verified AI accuracy wins. The original `scaffold.py` is copied but never executed automatically by the integration.

## Compatibility

The earlier `v10 think` (Kahneman-derived checklist) remains unchanged and can be used alongside this method. The Black Dragon capability catalog includes one additional local tool record; a catalog entry is NOT proof that the underlying 7 methods ran on a user's task. No websites, external programs, agents, private files or paid API calls are invoked.
