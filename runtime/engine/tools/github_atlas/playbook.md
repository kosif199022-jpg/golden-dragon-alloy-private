# Playbook: what the top-1000 repos teach about doing the work

Distilled from 10 batch reports (one per 100 repos) plus 400 per-repo `lesson` fields.
Run `python scripts/atlas.py lessons --grep WORD` to see the raw lessons with their source repo.
Each rule names repos that show it, so you can open the README when you need the detail.

## A. Picking a tool

1. **Prefer what is already installed.** `atlas.py have` lists the atlas tools found on PATH. A working local
   tool beats a better one that needs a 2 GB install.
2. **Shortest path to a visible result wins.** Single binary, one-line package, or portable zip
   (ripgrep, typst, copyparty, Umi-OCR, Real-ESRGAN-ncnn, trivy). Prefer these over Python stacks pinned to a torch build.
3. **Reach for the headless surface.** Many top tools ship one engine with several faces: GUI + CLI + HTTP/RPC + MCP
   + agent skill (Playwright, mitmproxy, aria2, jadx, Umi-OCR, pdf2zh, LocalAI, mpv IPC). Claude should drive the CLI or
   the machine-readable output (JSON, accessibility tree), not the GUI.
4. **Check for an official skill or MCP first.** In the 2026-11 snapshot, 55 of the top 1000 sit in the
   prompts-and-skills category and 46 repos document a skill/plugin install line, and
   libraries now ship their own (tabler, video.js, polars, tiptap, CopilotKit). Two install grammars recur:
   `npx skills add OWNER/REPO` (cross-agent) and `/plugin marketplace add OWNER/REPO` then `/plugin install NAME@MARKET`.
5. **Popularity is not maintenance.** 82 of the 1000 are archived or idle for 2+ years (create-react-app, atom,
   thefuck, Real-ESRGAN, GFPGAN, coqui-ai/TTS). Read the first screen of the README: moved projects put the new home
   there (GSD, PocketBase, LocalStack, base/node, ziglang to Codeberg, coqui to the `coqui-tts` fork). Recommend the successor.
6. **Check the licence before commercial work.** AGPL (OpenMontage, grafana, RSSHub, siyuan), BUSL (terraform),
   paid-for-companies (Remotion), non-commercial (GitNexus, some datasets). Say it when it matters.

## B. Working like the best repos

7. **Write the plan to disk before acting** (OpenSpec proposal/spec/tasks, OpenMontage staged pipelines with review
   gates). For anything multi-step, a plan file is cheaper than a redo.
8. **Proof before report.** "No exploit, no report" (shannon); strix reports only with a working PoC; Cloudflare's
   security skill hands each finding to a fresh agent whose job is to disprove it and keeps
   `confirmed / needs_validation / rejected` apart. For media: measure the file before saying it is done.
9. **Deterministic first, model second** (Open Code Review): rules and scripts decide what they can, the LLM only
   decides the rest.
10. **Dry-run before anything destructive** (Mole `--dry-run`, Ventoy confirm, cleanyourtv back-up then disable
    rather than uninstall). Reversible beats clever.
11. **Agent-shaped context.** Feed the model compact structure, not raw dumps: accessibility trees (Playwright MCP,
    agent-browser: snapshot, act, re-read), code graphs (codebase-memory-mcp, GitNexus), section trees (PageIndex).
    Filter command output before it reaches the model (rtk, caveman measure the token savings).
12. **Ground every extraction** (langextract maps each item to a source span; dspy: signature + metric; langfuse:
    versioned prompts with evals). An answer you can trace is an answer you can check.
13. **Measure a skill, do not assume it** (Ponytail runs with and without the skill and publishes the numbers).
14. **Taste as checkable rules** (emilkowalski: "ease-out for enter animations"; hallmark: floor checks that never
    ship, defaults overridable with a recorded reason, a fresh-context reviewer last; taste-skill and impeccable need
    a reference and a real browser check). "Make it look good" is not a spec.
15. **Data beats prose for design knowledge** (UI UX Pro Max ships palettes and font pairs as searchable data;
    DESIGN.md token files). Same for this atlas: query it, do not memorise it.
16. **Code as the source of truth for visuals** (Manim, Diagrams, Remotion, HyperFrames, mermaid): reproducible,
    diffable; cheap preview first, final quality last.
17. **Prompts are small Markdown files** (Fabric patterns: IDENTITY / STEPS / OUTPUT; Claude plugin layout with
    `commands/`, `agents/`, `skills/`). Keep them composable and versioned.
18. **Answer first** (i-have-adhd, humanizer): lead with the action, number the steps, cut filler, name
    anti-patterns with before/after examples.
19. **Leave receipts** (Codewhale `/receipts`): files changed, commands run, network calls. Ends every report.
20. **Learning loop** (Hermes turns successful runs into new skills). Log the lesson when something fails.

## C. README patterns worth copying when Claude writes docs

- Open with a real terminal transcript (mkcert).
- Give the install line for bash, CMD and PowerShell (appwrite, private-gpt).
- State prerequisites before the first command.
- Put deprecation notices and successors at the very top.
- One "hello" command that proves the install worked (`streamlit hello`).
