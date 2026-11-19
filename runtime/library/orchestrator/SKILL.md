---
name: orchestrator
description: Assemble the user's context brain, skills, connectors, and pipelines into one system they actually run end-to-end — and document it so a teammate could run it too. The capstone meta-skill. Works for any role.
---

# Orchestrator

The payoff of the other skills is a **system**, not a pile of parts. This skill wires a user's context brain, skills, connectors, and pipelines into one workflow they run for real — and writes it down so it survives them being on holiday.

Role-agnostic. The orchestrator is whatever recurring, high-value workflow matters most in the user's world.

## Step 1 — Inventory

Ask what the user already has (and help them build any gaps with the matching skill):

- A **context brain**? (`context-brain`)
- Any **skills** for recurring tasks? (`skill-author`)
- **Connectors** to their live tools? (`connector-setup`)
- A **pipeline** for their multi-step work? (`pipeline-builder`)

Then ask the key question: **what's the one workflow worth orchestrating first?** Pick a real, recurring, high-value one — not a toy.

## Step 2 — Assemble the flow

Map that workflow as a single flow that connects the parts:

```
TRIGGER  → which brief/event starts it
CONTEXT  → the brain it reasons from
SOURCES  → the connectors it reads live
STEPS    → the pipeline/skills that do the work
OUTPUT   → the deliverables + the report
LEARN    → what folds back into the brain
```

The goal is no manual glue — the user drops in a brief and the system runs.

## Step 3 — Run it end-to-end

Push one real instance through, brief to output, with no copy-paste in the middle. Where it breaks is where a part is missing or a hand-off is unclear — fix that part, not the symptom.

## Step 4 — Document it (the real test)

Write a short **runbook**: how to trigger it, what each part does, and how to recover when something's off. The test of an orchestrator is that a teammate could run it without the person who built it.

## Rules

- Orchestrate one real workflow well before adding a second.
- The best system is boring in the best way — one you'll still be running in three months.
- If you can't document it, it isn't finished.
