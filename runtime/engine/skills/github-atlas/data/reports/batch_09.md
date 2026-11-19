# Batch 09 (ranks 801-900) — report

All 100 READMEs were fetched via `gh api` (first 6000 chars each). Install commands ending in `?` are not confirmed from the README excerpt and need checking before the skill presents them as fact.

## Top 10 by value_for_claude

1. **xinntao/Real-ESRGAN** (5) — portable `realesrgan-ncnn-vulkan.exe`, no Python needed; direct image/video upscaling for montage work.
2. **google-ai-edge/mediapipe** (5) — face/pose/hand landmarks and segmentation from Python; the base for auto-reframing 16:9 to 9:16 and masks.
3. **vercel-labs/skills** (5) — `npx skills add owner/repo -a claude-code`; the standard installer for SKILL.md skills.
4. **PDFMathTranslate/PDFMathTranslate** (5) — `pip install pdf2zh`; layout-preserving PDF translation with CLI and MCP.
5. **AlexsJones/llmfit** (5) — `winget install --exact --id AlexsJones.llmfit`; answers "which local model runs on this PC" from measured hardware.
6. **aquasecurity/trivy** (5) — one binary to scan a repo/folder/image for CVEs, secrets and licenses; useful before trusting any downloaded repo.
7. **mpv-player/mpv** (4) — scriptable FFmpeg-based player with JSON IPC; frame-accurate preview and screenshots.
8. **TencentARC/GFPGAN** (4) — face restoration, pairs with Real-ESRGAN.
9. **naptha/tesseract.js** (4) — OCR in Node/browser including Arabic (`ara`), no native install.
10. **virgiliojr94/book-to-skill** / **alchaincyf/nuwa-skill** / **VoltAgent/awesome-agent-skills** (4) — skill-building material: book-to-skill conversion, persona distillation, and a 1000+ skill index.


## Patterns and lessons for the skill

- **Portable binary first.** The tools Claude can use most directly ship a single executable or one-line package install (Real-ESRGAN ncnn, trivy, llmfit, restic, mpv). Prefer these on Windows over Python stacks with torch pins.
- **One engine, many surfaces.** pdf2zh (CLI/GUI/Docker/MCP), llmfit (TUI/CLI/JSON) and mpv (flags/config/IPC) expose the same core everywhere. Machine-readable output is what makes a tool agent-usable.
- **Skills are now an ecosystem.** Six repos in this batch are skills or skill tooling. Common conventions: SKILL.md with name + description frontmatter, `npx skills add`, a shared `~/.agents/skills/` directory, short index plus on-demand reference files. Libraries (tiptap, CopilotKit) now ship their own agent skills.
- **Ground outputs.** langextract maps each extraction to a source span; dspy replaces hand-tuned prompts with a signature plus a metric; langfuse versions prompts and attaches evals. All three point the same way: make LLM output checkable.
- **Lockfile decides the package manager** (pnpm); a compose file is the install instruction (docker/compose).
- **Many self-hosted apps are Linux/Docker only** (Dokploy, CasaOS, 1Panel, Firecracker, Frigate). The atlas should answer "not on Windows directly" rather than offer a curl-pipe-bash line.

## Risks

- **Unmaintained but still widely used:** Real-ESRGAN, GFPGAN, bark (last pushes mid-2024), OpenVoice (2025-04). They work, but expect dependency pinning (old torch/basicsr/numpy). openai/gym is archived; use gymnasium. LLM101n, Open-Assistant, deeplearningbook-chinese, freecodecamp.cn, engineering-blogs and Clone-Wars are dead or frozen.
- **Licenses:** AGPL-3.0 on PDFMathTranslate, Folo, Trilium, khoj, glance, nextcloud, LinkSwift (fine to run, restrictive to embed in a product). GPL on sqlmap, mpv, rufus, AdGuardHome, RevokeMsgPatcher. GitHub reports NOASSERTION for directus, Dokploy, langfuse, medusa, marked, taro, WeKnora, GFPGAN, gym, mpv, sqlmap; the licenses I wrote for these are from memory and marked `?` where unsure. directus in particular is source-available with commercial conditions.
- **Consent and legality:** RVC, OpenVoice and bark can clone voices; use only with the voice owner's consent. sqlmap is for authorized testing only. RevokeMsgPatcher and LinkSwift modify or work around third-party services and may break their terms. awesome-english-ebooks redistributes copyrighted magazines. ai-website-cloner-template raises copyright/trademark questions when cloning someone else's site. one-api key redistribution can violate provider terms.
- **Supply chain:** bitchat's README warns about unverifiable mirrors. Third-party skills (awesome-agent-skills, nuwa-skill, book-to-skill, Game-Studios) carry instructions and scripts that run with the agent's permissions; read them before installing. claude-code-router redirects agent traffic to other providers and should be set up only on explicit user request.
