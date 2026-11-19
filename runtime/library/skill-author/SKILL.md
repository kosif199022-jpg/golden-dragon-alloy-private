---
name: skill-author
description: Package a task the user repeats into a reusable SKILL.md skill folder, so it runs the same every time instead of depending on memory. Use when someone re-explains the same task to an AI assistant on a schedule. Meta-skill — works for any recurring task in any field.
---

# Skill Author

If you re-explain the same task every week, you're paying for it in time and in quality that swings with your memory. A **skill** packages the task once: when to run it, how the output gets made, what "done" looks like, and a couple of examples. This skill helps the user write one.

Role-agnostic: a recurring task is a recurring task, whether it's a weekly report, a candidate-screening summary, a design QA pass, or a release note.

## Step 1 — Interview

Ask the user:

1. **What task do you repeat?** Something they make on a cadence. If they name several, pick the highest-friction one.
2. **When should it run, and what does it need?** The trigger and the inputs.
3. **How is it made?** The steps, in order. Pull these out of them — they usually know but have never written it down.
4. **What does "done" look like?** Sections, length, format, structure.
5. **Got examples?** One or two of their best past versions to anchor quality.

## Step 2 — Write the SKILL.md

Produce a standard Agent Skill folder: `<skill-name>/SKILL.md` with this shape:

```markdown
---
name: <kebab-case-name>
description: <what it does + when to use it — this is how the agent decides to load it>
---

# <Title>

<one-line purpose>

## Trigger
<when to run · required inputs>

## Steps
1. <step>
2. <step>
...

## Output format
<what "done" is: sections, length, structure>

## Examples
<1–2 references, or links to example files>
```

Write the `description` carefully — it's what an agent reads to decide *when* to use the skill, so name the task and the trigger plainly.

## Step 3 — Dry-run

Run the new skill against a real brief. If the output drifts, the fix is usually a sharper step or a clearer "done" definition. Tighten, then save.

## Step 4 — Hand-off

Tell the user where it lives (`~/.claude/skills/<name>/` for Claude Code, or their agent's skills dir), and how to share it — a public GitHub repo is installable by others with `npx skills add <owner>/<repo>`.

## Rules

- The `description` field earns its keep — vague descriptions never get loaded.
- Number the steps so output is identical whether the user is calm or rushed.
- Anchor on real examples, not adjectives.
