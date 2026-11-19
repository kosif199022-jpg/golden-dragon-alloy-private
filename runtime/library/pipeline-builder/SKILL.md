---
name: pipeline-builder
description: Break a big, multi-part task into a clean pipeline where each step's output feeds the next, with context carried forward. Use when one prompt is trying to do too much and the result drowns. Works for any multi-stage task in any field.
---

# Pipeline Builder

Big asks fail when research, making, and adapting get crammed into one prompt. The fix is a **pipeline**: each step does one job, and its output becomes the next step's input. This skill designs that pipeline with the user.

Role-agnostic. "Research → draft → repurpose" is one example shape; a hiring loop, a design review, or a financial close are others. Ask.

## Step 1 — Interview

1. **What's the big task?** The whole thing they're trying to do in one go.
2. **What are the natural stages?** Help them name 2–4 steps where each produces something the next one needs. If they can't, propose stages from the task and confirm.
3. **What context must carry forward?** The facts, brief, or source-of-truth that every stage has to respect so nothing drifts.

## Step 2 — Design the pipeline

Write it out as ordered stages. For each stage:

```
STAGE n — <name>
  Input:  <what it receives (incl. carried context)>
  Does:   <the one job>
  Output: <the artifact it hands to the next stage>
```

Keep stages single-purpose. The first stage's output is usually *not* a draft — it's the brief/analysis the making stage needs. Carry the original brief into every stage so the work stays on-message.

## Step 3 — Run it as steps, not one prompt

Have the user run each stage as its own prompt (or sub-agent), passing the prior output + carried context forward. Check the hand-off between stages — that's where drift hides.

## Step 4 — Save the shape

Once it works, the stage list *is* a reusable template. Suggest packaging it with `skill-author` so the whole pipeline runs from one trigger next time, and feeding any per-stage prompts through `prompt-architect`.

## Rules

- One job per stage. If a stage does two things, split it.
- Always carry the brief/context forward — drift between stages is the main failure mode.
- Wall-clock and quality both improve when stages are clean; don't collapse them back into one prompt.
