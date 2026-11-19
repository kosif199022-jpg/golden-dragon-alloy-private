# Batch 08 report (ranks 701-800)

100 repos, all READMEs fetched via `gh api` (first 6000 bytes; nothing cloned or run). Install commands ending in `?` were not in the excerpt read: verify before use.

## Top 10 by value_for_claude

1. **microsoft/playwright-mcp** (5) - `claude mcp add playwright npx @playwright/mcp@latest`. Drives a real browser through accessibility snapshots instead of screenshots; the direct answer to "open/click/fill/read this site".
2. **datalab-to/marker** (5) - `pip install marker-pdf`. PDF, DOCX, PPTX, XLSX, EPUB and images to Markdown/JSON with tables, equations and extracted images. First choice for "read this PDF properly".
3. **pola-rs/polars** (5) - `pip install polars`. Fast DataFrame engine for CSV/Parquet work.
4. **koalaman/shellcheck** (5) - static analysis for bash/sh. Run it on every shell script Claude writes.
5. **psf/black** (5) - `pip install black`. Deterministic Python formatting with no decisions to make.
6. **evanw/esbuild** (5) - one-command JS/TS/CSS bundling and minifying for web artifacts.
7. **OpenBMB/VoxCPM** (4) - VoxCPM2 TTS: 30 languages, voice design from a text description, cloning, 48kHz. Strong fit for voice-over; test Arabic quality first.
8. **lightpanda-io/browser** (4) - headless browser for agents, CDP-compatible; README claims about 16x less memory than Chrome. Docker or WSL on Windows.
9. **ShareX/ShareX** (4) - Windows screenshot, region recording and GIF capture; fits tutorial and demo footage.
10. **videojs/video.js** (4) - v10 player framework for HTML and React, ships an agent skill (`npx @videojs/cli agents init`).

Also 4: croc, nushell, faiss, PageIndex, searxng, tabler (RTL dashboards), swiper, cheat.sh, maigret. High owner relevance, lower direct value: postiz-app (social scheduling API), artcraft (3D staging for AI video), openscreen (archived).


## Recurring patterns and lessons

- **Agent entry points in the README.** tabler (`npx skills add tabler/tabler`), video.js ("AI Quickstart"), polars (Skill + MCP links), playwright-mcp (says when a CLI plus skills fits a coding agent better than MCP), ToolJet and PostHog (MCP servers), github/awesome-copilot (machine-readable entry for agents). The atlas should record, per tool, whether an official skill or MCP exists and prefer it.
- **Structure over pixels or text.** Playwright MCP feeds accessibility trees; nushell passes tables between commands; PageIndex navigates a section tree instead of chunks; OpenViking stores agent memory as a readable file tree.
- **Auditability.** Codewhale's `/receipts` lists files changed, commands run and network/MCP calls. A good habit for any agent report.
- **One source, several surfaces**: anthropics/financial-services ships the same skills as a Cowork plugin and through the Managed Agents API; Postiz exposes API, SDK, n8n node and agent connectors.
- **Windows reality**: about a quarter of the batch is Docker-only self-hosted server software (outline, appsmith, tooljet, erpnext, umami, chatwoot, mattermost, photoprism, postiz, searxng). The skill should say Docker Desktop is required.

## Risks

- **Copyleft / restrictive licences**: AGPL-3.0 on OpenViking, lightpanda, postiz, ToolJet, drawdb, heretic, ChatTTS, searxng; GPL on ShareX, shellcheck, it-tools, erpnext, halo, Kazumi, NewPipe. Fine to run, not to embed. GitHub reports no clear licence (NOASSERTION) for outline, posthog, novu, chatwoot, mattermost, photoprism, prompt-optimizer, video.js, vuetify, qBittorrent, yarn, llvm, sing-box, metasploit; several are open-core. Aseprite binaries are paid.
- **Dual-use**: rapid7/metasploit-framework (antivirus will flag it), soxoj/maigret (dossier on a person from a username), p-e-w/heretic (strips model safety behaviour), SagerNet/sing-box (proxy), Kazumi and qBittorrent (copyright depends on content). Recommend only for authorised or own-asset use.
- **Dead or superseded**: pure-bash-bible, google-research/bert, openscreen and UI-TARS-desktop are archived; Awesome-Design-Tools, ChatGLM-6B, wrk and Deep-Learning-Papers-Reading-Roadmap have had no push for over two years; yarn 1.x is frozen; ChatTTS, FastChat and leveldb are slow.
- **No Windows path**: Hyprland (Linux only), NewPipe (Android only); wrk, tidb, ColossalAI and quivr need WSL.
- **Verify**: airllm's under-4GB claims mean feasibility at very low speed.
