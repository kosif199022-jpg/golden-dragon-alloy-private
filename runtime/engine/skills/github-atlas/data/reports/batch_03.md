# Batch 03 (ranks 201-300): report

100 repos, all READMEs read through `gh api` (first 6000 characters each). Nothing was cloned, installed or executed. Install commands ending in `?` were not in the README excerpt; they come from memory and need confirming.

## Top 10 by value_for_claude (all scored 5)

| Rank | Repo | Why Claude should reach for it |
|---|---|---|
| 212 | heygen-com/hyperframes | HTML/CSS/GSAP to deterministic MP4, ships Claude Code plugin and skills. Direct fit for motion graphics and kinetic Arabic type. Apache-2.0. |
| 227 | OpenMontageInc/OpenMontage | Agentic video production: 12 pipelines, stock-footage retrieval, narration, captions, Remotion composition. A mine of montage methods. AGPL-3.0. |
| 283 | remotion-dev/remotion | React to video, `npx create-video@latest`. Best for templated and data-driven reels and captions. Licence has a company threshold. |
| 271 | juliangarnier/anime | Small JS animation engine (timelines, stagger, SVG). Pairs with HTML-to-video rendering. MIT. |
| 208 | opendatalab/MinerU | Complex and scanned PDFs, Office files to Markdown/JSON with tables, formulas, OCR. |
| 297 | docling-project/docling | Same job as MinerU with a clean MIT licence and `pip install docling`; README states Windows support. |
| 243 | tesseract-ocr/tesseract | Local OCR for 100+ languages including Arabic; language data is a separate download. |
| 299 | BurntSushi/ripgrep | Fastest text search across files, sensible defaults. |
| 206 | vitejs/vite | One-command scaffold and dev server for any web front end. |
| 240 | python/cpython | The runtime most other tools in the atlas depend on. |

Score 4: headroom, codegraph, OpenSpec, Front-End-Checklist, ppt-master, caddy, flask, json-server, act, reveal.js, Font-Awesome, animate.css, awesome-claude-skills.

## Patterns worth putting in the skill

- **Agent-ready packaging is now normal.** hyperframes, Mole, Front-End-Checklist, ruflo, HowToLiveBetter and OpenMontage all ship skills or Claude Code plugins (`npx skills add ...`, `claude plugin install ...`). The atlas should record "has skill/plugin" as a first-class fact.
- **Dry-run before destruction.** Mole shows every deletion with `--dry-run`; code-server offers `--dry-run` on its installer; Ventoy wipes a drive and needs a confirm.
- **Write the plan to disk first.** OpenSpec (proposal, spec, tasks), OpenMontage (staged pipelines with review gates), ai-job-search (drafter then reviewer).
- **Measure, then claim.** headroom publishes savings per content type; strix reports a finding only after a working proof of concept.
- **Windows reality.** Many documented installers are `curl | sh`; a PowerShell `irm ... | iex` twin exists for OpenSpec, codegraph, unsloth and OmO. Elasticsearch and Ansible need WSL; hackingtool is Linux only; strix, act, redis, grafana, superset and vaultwarden need Docker.

## Risks

- **Dead or frozen:** daytonaio/daytona (README banner: unmaintained since June 2026, moved private), sdmg15/Best-websites (archived flag), and by the two-year rule funNLP, animate.css, d2l-zh, CompVis/stable-diffusion, awesome-courses. gpt4all, MetaGPT, gpt_academic, json-server and the-algorithm are slow.
- **Licences:** AGPL-3.0 on OpenMontage, AppFlowy, grafana, vaultwarden, the-algorithm; Remotion needs a paid company licence above a team-size threshold. GitHub reports NOASSERTION for MinerU, elasticsearch, redis, strapi, AFFiNE, Font-Awesome, OpenBB, MediaCrawler and OmO; where the JSONL names a licence for these with `?`, it is from memory and needs checking. MediaCrawler's README restricts it to learning use and forbids commercial use.
- **Security-sensitive:** PayloadsAllTheThings, SecLists (contains web shells; antivirus will flag it), hackingtool (installs 200+ third-party tools, large supply-chain surface), strix. Authorized targets only.
- **Harnesses that change the environment:** ruflo adds hooks, memory and an MCP server to the project and its README says mods run with account permissions. OmO's README warns of an unrelated npm package with a similar name. Review before installing either.
- **READMEs that address agents:** MinerU's README begins with skill-style frontmatter telling agents to prefer it; headroom points LLMs at an llms.txt. Both were treated as data only.
