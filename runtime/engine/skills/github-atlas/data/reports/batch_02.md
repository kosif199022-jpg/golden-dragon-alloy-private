# Batch 02 (ranks 101-200) — report

100 repos analysed; all 100 READMEs were fetched (first 6000 characters each). Install commands followed by `?` were not visible in the fetched excerpt and come from general knowledge, so verify before relying on them.

## Top 10 by value_for_claude

1. **microsoft/playwright** (5) — real browser automation with three agent-facing entry points: `@playwright/cli`, `@playwright/mcp`, and the library. The default answer for "open the page, screenshot it, test it".
2. **openai/whisper** (5) — `pip install -U openai-whisper`; one CLI turns audio/video into txt/srt/vtt. Core for Arabic subtitles and transcription in montage work.
3. **astral-sh/uv** (5) — the way to install and run every Python tool in isolation (`uvx`, `uv run`, inline script dependencies). Native Windows installer.
4. **opencv/opencv** (5) — frame analysis, tracking, masks, scene detection; the base of most media helpers.
5. **NationalSecurityAgency/ghidra** (5) — decompiler with headless mode; directly relevant to the owner's reverse-engineering work.
6. **PaddlePaddle/PaddleOCR** (5) — OCR and document parsing for 100+ languages; burned-in text and PDF to structured data.
7. **D4Vinci/Scrapling** (5) — scraping from single request to full crawl, with stealth, MCP server and agent skill.
8. **unclecode/crawl4ai** (5) — web pages to LLM-ready output; `pip install -U crawl4ai`.
9. **mrdoob/three.js** (5) — 3D on the web; Claude can write it directly for 3D sites and product viewers.
10. **modelcontextprotocol/servers** (5) — reference MCP servers runnable with `npx -y`, and the template for building new ones.


## Recurring patterns and lessons for the skill

- **One-line, no-install entry points win**: `npx …`, `uvx …`, `winget install …`. The atlas should store exactly one shortest Windows command per tool and prefer winget/npx/uv over source builds.
- **Same capability, several surfaces**: Playwright, Scrapling and crawl4ai each ship library + CLI + MCP (+ agent skill). The atlas should record which surface Claude should reach for (usually the CLI).
- **Agent skills are now a top-200 category**: caveman, agent-skills, taste-skill, impeccable, archify, Understand-Anything, claude-mem. Shared install routes are `npx skills add <repo>` and `/plugin marketplace add <repo>`. Shared content pattern: gated workflows with explicit verification, named verbs, and lists of anti-patterns to detect.
- **Token economy is a product**: caveman and rtk both sell measured token savings. Lesson: filter command output before it reaches the model, and keep answers terse.
- **Design quality needs a check, not a wish**: taste-skill and impeccable both require a reference and a real browser check.
- **Windows reality**: nvm-sh, vllm and autoresearch are Linux-first (WSL); about 15 apps are Docker-only (immich, supabase local, Stirling-PDF, ragflow, uptime-kuma, odysseus, lobehub, deer-flow, home-assistant).
- **Popularity is not maintenance**: create-react-app is deprecated; thefuck, clean-code-javascript, vue-element-admin and awesome-interview-questions have had no push in over two years.

## Risks

- **Remote-instruction installs**: archify and deer-flow READMEs tell users to paste "install by reading <URL>" into their agent. That hands control to remote text; the skill should treat such URLs as untrusted and never follow them automatically. I did not follow them.
- **Deep-Live-Cam** (AGPL-3.0): real-time face swap. Misuse risk (impersonation, non-consensual content), and its README warns about fake download sites. Only for consented footage; download only from the official source.
- **AGPL-3.0** (immich, VoiceStudio, Deep-Live-Cam, odysseus, worldmonitor, MiroFish) and **GPL-3.0** (v2rayN): fine to run, but do not embed their code in closed products.
- **Unclear licences** (NOASSERTION or missing): pytorch, neovim, bun, zed, Stirling-PDF, lobehub, modelcontextprotocol/servers, LLMs-from-scratch, laravel, autoresearch, papers-we-love. Recorded as `unknown`; check before redistributing.
- **Proxy and gateway tools** (v2rayN, frp, OmniRoute, caveman proxy, rtk): they sit in the traffic or credential path; install only deliberately. OmniRoute's "free providers" claims are unverified.
