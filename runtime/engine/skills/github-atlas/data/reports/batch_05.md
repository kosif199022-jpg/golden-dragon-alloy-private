# Batch 05 (ranks 401-500) — report

100 repos, all READMEs fetched via `gh api` (first 6000 chars each). 81 active, 7 slow, 12 archived by the brief's rule (flagged or last push more than 2 years ago).

## Top 10 by value_for_claude

1. **ggml-org/whisper.cpp** — offline speech-to-text Claude can call directly; the core of any Arabic subtitle/caption workflow.
2. **skylot/jadx** — APK/DEX to Java from the command line (`jadx -d out app.apk`); first reach for Android reverse engineering.
3. **ChromeDevTools/chrome-devtools-mcp** — MCP server plus CLI that gives an agent a live Chrome: network, console, traces, screenshots.
4. **HKUDS/CLI-Anything** — wraps GUI software in agent-friendly CLIs and ships a hub (`pip install cli-anything-hub`); directly addresses "drive this desktop program".
5. **Nutlope/hallmark** — design skill with fifty themes and browser lint gates against AI-looking pages.
6. **emilkowalski/skills** — animation and UI-polish rules from a practitioner (`npx skills@latest add emilkowalski/skills`).
7. **DavidHDev/react-bits** — 215+ animated React components installed one at a time via shadcn; also offers an MCP server.
8. **typst/typst** — one binary (`winget install --id Typst.Typst`) that turns markup into typeset PDF.
9. **Textualize/rich** and **psf/requests** — the two Python libraries a pipeline script needs most: readable progress/tables, and HTTP.
10. **anthropics/claude-cookbooks** — vetted recipes for Claude API patterns; plus **prettier/prettier** and **PowerShell/PowerShell** as everyday utilities.

Strong runners-up (score 4): segment-anything (cut-outs), upscayl (image upscaling), you-get (downloader fallback), mkcert (local HTTPS), meilisearch, pdf.js, material-design-icons, yolov5, awesome-claude-code, and four skill packs (marketingskills, scientific-agent-skills, academic-research-skills, BMAD-METHOD).

## Patterns and lessons worth carrying into the skill

- **Skills are now a top-1000 category.** Nine repos in this batch are Agent Skill packs or skill lists. Two install routes recur: `npx skills add owner/repo` and Claude Code's `/plugin marketplace add` + `/plugin install`. The atlas should record which route each pack documents.
- **Tiered quality gates** (hallmark): a floor that never ships, defaults that can be overruled with a recorded reason, finish checks that never block, and a fresh-context reviewer last.
- **Encode taste as checkable rules** (emilkowalski): "ease-out for enter animations" beats "make it feel good".
- **CLI plus GUI on one engine** (jadx, face_recognition, chrome-devtools-mcp, Motrix over aria2): the CLI is what an agent uses; prefer it and name it in the atlas.
- **Reversible automation** (cleanyourtv): back up, disable instead of uninstall, one-line restore.
- **README practice**: open with a real terminal transcript (mkcert); give the install line in bash, CMD and PowerShell (appwrite, private-gpt); state prerequisites before the first command (serviette's licence key and pip version); put deprecation notices and successors at the top (meta-llama/llama, maybe, Flowise).
- **Copy-in components** (react-bits, html5-boilerplate) age better than monolithic dependencies.
- **Machine-readable data files with mirrors** (trackerslist) are directly consumable by scripts.

## Risks and cautions

- **Dead or superseded**: angular.js, gpt-engineer, Flowise, maybe (archived flag); lencx/ChatGPT, grok-1, element (Vue 2), meta-llama/llama (deprecated), 100-Days-Of-ML-Code. mkcert, normalize.css and segment-anything are marked archived by the 2-year rule but are finished, still-usable tools.
- **Licences**: AGPL-3.0 for yolov5, cherry-studio, upscayl, new-api, maybe, CL4R1T4S; GPL for jellyfin, ImHex, Fooocus, faceswap, freqtrade, AnyPS5, Docker-OSX. 20 repos report NOASSERTION or no licence (recorded as `unknown`), including meilisearch, joplin, odoo, Flowise, BMAD-METHOD, react-bits, multica ("source-available") and awesome-claude-code — check before reusing code.
- **Terms-of-service / legal**: router-for-me/CLIProxyAPI re-exposes subscription CLI accounts as APIs; bannedbook/fanqiang and shadowsocks-windows are censorship-circumvention tools; AnyPS5 and Docker-OSX touch console/macOS licensing; CL4R1T4S is unverified leaked prompts. Scored low on purpose.
- **Misuse potential**: deepfakes/faceswap; microsoft/VibeVoice notes its tool was used in ways inconsistent with its intent. Consent-only use.
- **Commercial steering inside READMEs**: nature-skills advertises account top-up/resale services; marketingskills lists paid partners (disclosed). Treat as ads, not advice.
- **Unvetted registries**: awesome-openclaw-skills indexes 5,000+ community skills — read before installing.
- **Star counts that look out of proportion to the project** (FuelLabs/fuel-core, a blockchain node at 56k) — stars are not a quality signal here.
- **Windows caveats**: serviette (Pathway), face_recognition (dlib build), Rails/Jekyll, powerlevel10k, dockur/windows and Docker-OSX need WSL/KVM. Install commands I could not confirm inside the fetched README excerpt are marked with `?` in the JSONL.
