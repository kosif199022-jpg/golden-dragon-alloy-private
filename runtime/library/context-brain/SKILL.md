---
name: context-brain
description: Build a reusable context pack (a "brain") so Claude reasons from the user's role, audience, voice, and standards every time, instead of generic output. Use when setting up a Project/workspace, or when output is on-topic but off-voice. Works for any role or domain.
---

# Context Brain

Out of the box, Claude writes well but generically. A **context brain** is a small, curated set of documents that make every future prompt start from *your* world. The skill is to **curate, not dump** — Claude reasons better from five sharp documents than fifty noisy ones.

Role-agnostic: an HR team's brain holds policy and tone; a designer's holds principles and references; a sales team's holds positioning and objection handling. Ask what theirs is.

## Step 1 — Interview

Ask the user:

1. **What do you do, and for whom?** Their role, their org/team, and who their work is *for* (the audience or stakeholder).
2. **What does "on-voice / correct" mean to you?** How good output sounds or is judged in their world.
3. **What few references define it?** Their best past work, a style/policy doc, positioning — whatever a new hire would need to be trusted. Aim for ~3–5 sources, not a folder of fifty.
4. **What should it never do?** Words, claims, tones, or moves to avoid.

## Step 2 — Build the four core docs

Produce these as clean, short markdown files the user can drop into a Project:

- **`positioning.md`** — who they are, what they do, why it matters. A few sentences.
- **`voice-and-standards.md`** — how their work should sound/look/read, with do-and-don't pairs. Concrete, not adjectives.
- **`reference-examples.md`** — 1–3 short samples of "good", lightly annotated with *why* they're good.
- **`never-do.md`** — the short list of hard nos.

Draft from the interview; mark anything you inferred so the user can correct it.

## Step 3 — Custom instructions

Write a 2–3 line standing brief that loads on every chat: who we are, who we talk to, and the voice. This is the always-on summary; the four docs are the depth behind it.

## Step 4 — Test, then prune

Run one real task the user would actually ship, using the brain. If it's off, the *knowledge* is wrong, not the prompt — fix the docs. Then prune: remove anything that didn't change the output. Tighter context, sharper results.

## Hand-off

Tell the user where to put these (a Claude Project, or a `context/` folder they paste in). Once it exists, the `prompt-architect` skill can reference it instead of re-stating context every time.

## Rules

- Curate, don't dump. Five sharp docs beat fifty.
- Never assume the domain — build from the interview.
- Show, don't tell: examples and do/don't pairs over adjectives.
