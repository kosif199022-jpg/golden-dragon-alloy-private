---
name: connector-setup
description: Plan a safe, least-privilege way to connect the user's real tools (Drive, Slack, a task board, a calendar, etc.) to Claude so it works from live data instead of copy-paste. Use when wiring up connectors/MCP. Works for any stack and any role.
---

# Connector Setup

Most people are the integration layer — copy-pasting between tabs to give Claude what it needs. Connectors (MCP) let Claude read the tools you already use and work from live context. This skill plans that safely, one source at a time.

It does **not** assume a stack. Ask what the user actually uses.

## Step 1 — Interview

1. **What's your stack?** The tools where your work and information actually live.
2. **Where's the friction worst?** Where do you copy-paste the most? That's the first source to connect — usually a document store or a task board.
3. **What does one real task need to read?** Be specific. "This week's activity in the marketing folder", not "all of Drive".

## Step 2 — Connect with least privilege

For the chosen source, produce a connection plan:

- **Scope:** the minimum access a task needs — read-only where possible, a single folder/channel/project rather than the whole account.
- **What it can and can't see**, stated plainly so the user can sanity-check it.
- **How to connect it** in their agent (the connector/MCP server for that tool, or the native integration).

Grant access to exactly what a task needs, nothing more. Intent over convenience.

## Step 3 — Run one real task on live data

Have the user ask Claude to do one genuine task that pulls from the connected source — no pasting, no exporting. Confirm it's reading **current** data (check a fact that changed recently).

## Step 4 — Fold it in

Once it's trusted, update the user's everyday prompts to assume the live source is available. Then repeat from Step 1 for the next-highest-friction source — one at a time, never all at once.

## Rules

- Least privilege, always. Read-only and narrowly scoped unless a task truly needs more.
- One source at a time; prove it works on live data before adding the next.
- This is the shift from assistant to orchestrator — Claude stops waiting to be fed.
