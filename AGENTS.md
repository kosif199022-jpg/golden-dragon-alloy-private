# Agent entrypoint for this multi-project repository

This repository contains historic Golden Dragon Alloy data/runtime **and** the independent new `red-rose/` project.

**If asked to develop or finish «الوردة الحمراء / Red Rose»:**
1. Read [red-rose/AGENTS.md](red-rose/AGENTS.md) first, then [red-rose/NEXT_AGENT_HANDOFF.md](red-rose/NEXT_AGENT_HANDOFF.md).
2. Consult [red-rose/QUESTIONS_AND_ANSWERS.md](red-rose/QUESTIONS_AND_ANSWERS.md) and [red-rose/QUESTION_COVERAGE.json](red-rose/QUESTION_COVERAGE.json) for confirmed decisions and missing original question texts.
3. Use `red-rose/rose.py` and native `red-rose/capability_runtime.py` as the entrypoints. Never invoke or import legacy Dragon code into Red Rose runtime.
4. Verify the current `main` commit, run the tests and inspect real artifacts before reporting success.

**Scope:** The Red Rose instructions apply to work under `red-rose/`. They do NOT authorize destructive changes to legacy code, accessing/uploading private memory, running paid services, or rewriting unrelated agents' directives.

Never misrepresent approved design requirements, indexed descriptions or plan entries as executed/tested capabilities.
