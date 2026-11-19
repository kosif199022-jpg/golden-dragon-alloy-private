---
name: prompt-architect
description: Turn a vague request into a reliable, reusable prompt with role, context, task, constraints, and examples. Use when the user keeps re-rolling outputs to get something usable, or wants a repeatable prompt for a task they do often — in any field.
---

# Prompt Architect

Most weak output isn't a weak model — it's a missing part. A reliable prompt has five: a **role**, **context**, one **task**, **constraints**, and an **example** of good. This skill builds that prompt with the user, then hands them a reusable version.

It is **role-agnostic**. Do not assume the user is a marketer, engineer, or anything else. Ask.

## Step 1 — Interview (always do this first)

Ask the user, briefly and conversationally (don't dump all five at once — ask, then react):

1. **Who should the assistant act as?** Their job/role and the kind of judgement it implies. ("HR business partner", "brand designer", "support lead".)
2. **What's the one task?** A single deliverable. If they name several, pick one and note the rest for later.
3. **What's the context?** Audience, goal, and any house style or rules. Offer to use an existing context pack if they have one (see the `context-brain` skill).
4. **What does "good" look like?** Ask for one or two real examples, or describe the bar.
5. **Constraints?** Length, format, tone, and what to avoid.

If the user is unsure on any answer, propose a sensible default for their stated role and confirm.

## Step 2 — Assemble

Write the prompt in five labelled parts, in this order:

```
ROLE:        You are a <role> who <relevant judgement>.
CONTEXT:     <audience, goal, house rules / link to their context pack>
TASK:        <one deliverable, stated precisely>
CONSTRAINTS: <length · format · tone · what to avoid>
EXAMPLES:    <1–2 samples of "good", or a tight description of the bar>
```

Keep CONSTRAINTS specific — most quality lives there. Prefer showing an example over describing one ("examples beat adjectives").

## Step 3 — Test and tighten

Run the prompt once on the user's real input. Look at the output *with them* and fix the prompt, not the output: a miss almost always traces to a missing constraint or a weak example. Iterate until one run is shippable.

## Step 4 — Hand it back

Give the user the final prompt as a clean block they can save and reuse, plus a one-line note on what to swap each time they run it (the variable input). If they run this task weekly, suggest packaging it with the `skill-author` skill.

## Rules

- Five parts, always. If you're tempted to skip one, that's usually the part that was missing.
- One task per prompt. Multi-part asks become a pipeline (`pipeline-builder`).
- Never invent the user's domain — the interview is not optional.
