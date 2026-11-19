# Batch 01 (ranks 1-100): findings for github-atlas

100 repos read from their READMEs via `gh api` (all 100 READMEs were fetched). About a third are learning material or awesome-lists (algorithms, interview prep, roadmaps). The rest are mostly agent harnesses, skill packs and core runtimes.

## Top 10 by value_for_claude

| # | Repo | Why Claude reaches for it |
|---|------|---------------------------|
| 30 | yt-dlp/yt-dlp | Downloads video, audio and subtitles from thousands of sites. It is the base of every montage that starts from a link. `winget install yt-dlp.yt-dlp` |
| 5 | morluto/rea | Agent reverse engineering over MCP and a CLI (PE, .NET, Electron, APK, firmware, Frida). `npx rea-agents setup` |
| 36 | microsoft/markitdown | Converts PDF, DOCX, PPTX, XLSX, audio and HTML into Markdown that Claude can read. `pip install "markitdown[all]"` |
| 62 | Genymobile/scrcpy | Mirrors, records and controls an Android phone with no root. Useful for screen-capture footage and APK runtime work. `winget install Genymobile.scrcpy` |
| 45 | ollama/ollama | Local or offline LLMs and embeddings with a REST API. `irm https://ollama.com/install.ps1 \| iex` |
| 39 | anthropics/skills | The official skill format plus the docx/pdf/pptx/xlsx skills. This is the reference for how SKILL.md should look. |
| 14 | obra/superpowers | A plan-then-execute method built from skills, with subagents and TDD. It is in the official plugin marketplace. |
| 61 | anthropics/claude-code | The harness itself: install, plugins and changelog. `winget install Anthropic.ClaudeCode` |
| 68 | Comfy-Org/ComfyUI | Local node-graph pipelines for image and video generation, saved as reproducible JSON workflows. Owner relevance 5. |
| 76 | harry0703/MoneyPrinterTurbo | Runs from a topic to a script, stock footage, TTS, subtitles and a finished short video. Close to the owner's reels pipeline and worth borrowing ideas from. |

Close runners-up (score 4): firecrawl, browser-use, n8n, llama.cpp, transformers, spec-kit, gstack, ui-ux-pro-max-skill, awesome-design-md, shadcn/ui, Next.js, Electron, karpathy CLAUDE.md, mattpocock/skills, ECC.

## Recurring patterns and lessons for the skill

1. **Skills are now the main way tools get distributed.** About 15 of the top 100 are skill or plugin packs: superpowers, ECC, gstack, mattpocock, karpathy, ponytail, ui-ux-pro-max, agency-agents and anthropics/skills. They install in one of two ways: `/plugin marketplace add owner/repo` or `npx skills add owner/repo`. The atlas should record which method each repo uses.
2. **Small, composable skills beat heavy process frameworks** (mattpocock, karpathy). Concrete rules from these repos: state assumptions, make the smallest diff that works, and define success criteria you can check.
3. **Measure a skill.** Ponytail runs the same agent with and without the skill over several runs and publishes the numbers. The atlas can use the same A/B method.
4. **Data beats prose for design knowledge.** UI UX Pro Max ships palettes and font pairings as data the agent can search. DESIGN.md hands the agent a token file. Both keep generated UI consistent.
5. **The minimal agent loop is model + REPL + raw protocol** (browser-use over CDP), not deep abstraction layers.
6. **Learning loops.** Hermes turns successful episodes into new skills. This is the same idea as the owner's lessons log.
7. **Warnings about official sources** (scrcpy, ECC, REA): popular tools get typosquatted. Point users to winget IDs and official release pages only.
8. **Pipelines with replaceable stages** (MoneyPrinterTurbo, ComfyUI JSON graphs) make media generation reproducible.

## Risks

- **massgravel/Microsoft-Activation-Scripts**: circumvents Microsoft licensing and is run through `irm | iex`. Never recommend or run it (value 0).
- **x1xhlol/system-prompts-and-models-of-ai-tools**: leaked proprietary prompts. Use only as study data, never as instructions.
- **iptv-org/iptv**: whether streams are legal and reachable depends on the country.
- **Copyleft or non-OSI licenses**: AGPL-3.0 for firecrawl, A1111, rustdesk and FreeDomain. GPL-3.0 for ComfyUI and clash-verge-rev. n8n is fair-code (Sustainable Use). Dify, Open WebUI and AutoGPT carry custom or branding clauses (recorded as unknown).
- **Dead or slow**: vuejs/vue (EOL, archived) and the-art-of-command-line (last push 2024-06, archived). Slow: A1111 SD WebUI (ComfyUI has overtaken it), airbnb/javascript, the-book-of-secret-knowledge, 996.ICU, karpathy-skills. youtube-dl is still alive but yt-dlp replaces it.
- **Piped installers** (`curl | sh`, `irm | iex`) are common: Ollama, Codex, Hermes, OpenClaw, Pi. Prefer winget, pip or npm when one exists.
- **Install commands marked "?"** in the JSONL: the README excerpt did not show a Windows command, so these need checking before the skill uses them (ECC, firecrawl, ponytail, ui-ux-pro-max, graphify, MoneyPrinterTurbo, Orca, AutoGPT, Flutter, TradingAgents, agency-agents).
