# 🌹 V18 — attributed QA-to-code traceability ledger

## Measured scope (to be reverified at current HEAD)

- `QUESTIONS_AND_ANSWERS.md`: 35 **paraphrased** user decisions / repo facts / agent guidance, each with evidence class; NOT the original 1,400 numbered questions.
- `QUESTION_COVERAGE.json`: historical ranges 1–400, 401–450, 451–1400. Complete verbatim question/answer archives are **not recovered**.
- `QA_TRACEABILITY.json`: all 35 summary IDs linked (where applicable) to native `capability_runtime.REGISTRY` IDs; any unregistered/legacy ID fails validation.
- New `qa.trace`: read-only trace of A01–A35 and a no-DB summary command. This makes **16 registered adapters** on V18, not 16 independent AI agents.
- `test_qa_trace_v18.py`: 8 new tests for source attribution, missing-original disclosure, mapped-ID validation, rejection of injected fake/legacy adapters, runtime dispatch with local audit, and CLI not creating a personal DB.

## Evidence categories

- `related_partial`: implemented native adapter(s) have **some relevance**; entire goal is not achieved.
- `original_not_recovered`: exact historical Q&A source missing; never invent its content.
- `design_only` and `historical_status`: no execution claim.
- `policy_verified`: safety contract whose enforcement still needs code/test evidence on current HEAD.
- `agent_guidance`: continuation instructions, not verbatim user answers.

## Validation commands

```bash
cd red-rose
python rose.py question-audit
python rose.py question-trace A17
python rose.py capabilities
python -W error::ResourceWarning -m unittest discover -v
```

The 35 summary IDs are not a 35/1400 completion fraction. The V10 local summary migration count of 25,675 does not imply that these reference texts are executable. Video-quality features and 1,400 original requirements still have major outstanding work. This release is about **reproducible requirements provenance**, not a completed AI video engine or universal source fusion.

## CI / review

Do not merge before the Red Rose test workflow and private-memory guard pass on the same feature HEAD. Always verify the exact merged `main` ref and update next-agent handoff with its SHA.
