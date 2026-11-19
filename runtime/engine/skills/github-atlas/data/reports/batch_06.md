# Batch 06 (ranks 501-600) — report

100 repos, all READMEs fetched through `gh api` (first 6000 bytes each). Nothing was cloned, installed or executed.

## Top 10 by value_for_claude

1. **cli/cli** (5) — `gh` is how Claude reads READMEs, PRs, issues and releases; `gh api` covers everything else. `winget install --id GitHub.cli`.
2. **vercel-labs/agent-browser** (5) — browser automation CLI built for agents: `snapshot` returns a compact accessibility tree with `@e1` refs, then act on a ref. `npm install -g agent-browser`.
3. **jgm/pandoc** (5) — universal document conversion (md, docx, pdf, epub, html). `winget install --id JohnMacFarlane.Pandoc`.
4. **astral-sh/ruff** (5) — lint and format any Python script before delivery. `pip install ruff`.
5. **pandas-dev/pandas** (5) — default for CSV/Excel/JSON cleaning and aggregation.
6. **nvm-windows/nvm** (5) — the way to switch Node versions on Windows 11.
7. **kepano/obsidian-skills** (5) — ready Agent Skills in the agentskills.io format; installable as a Claude Code plugin.
8. **hiroi-sora/Umi-OCR** (4) — offline OCR on Windows with CLI and local HTTP API; `scoop install extras/umi-ocr`. Useful for burned-in text and scanned PDFs.
9. **DIYgod/RSSHub** (4) — turns sites and social accounts with no feed into RSS; good for content monitoring (Docker).
10. **9001/copyparty** (4) — single-file file server with resumable uploads; fast way to move footage between phone and PC.

Runners-up (4): supervision, pretext (DOM-free text layout incl. bidi, for Arabic kinetic type), pixijs, tldraw, htmx, slidev, LocalAI, shannon, open-code-review, codebase-memory-mcp, GitNexus, agentic-awesome-skills, claude-howto. For RE, x64dbg has owner_relevance 5.

## Recurring patterns worth carrying into the skill

- **Agent-shaped output.** agent-browser, codebase-memory-mcp and GitNexus all give the model a compact, queryable structure (accessibility tree, code graph) instead of raw pages or files. Rule: snapshot, act, re-read.
- **Proof before report.** Shannon: "No exploit, no report". Open Code Review: deterministic rules first, LLM only for what rules cannot decide. Both are verification-first.
- **One file, zero setup.** copyparty (single .py), htmx (one script tag), nlohmann/json (single header), textgen and Umi-OCR (portable zip). The lower the install friction, the more often the tool is the right pick.
- **GUI + CLI + HTTP from one app** (Umi-OCR, Bruno, LocalAI): prefer tools Claude can drive headlessly.
- **Skills as small units** (obsidian-skills, agentic-awesome-skills): one skill per format/task, searchable catalog, preview before install.
- **Windows routing:** winget for CLIs (gh, pandoc, terraform, nvm), scoop extras for Umi-OCR/Bruno, Docker for server apps, WSL for tmux, acme.sh, Homebrew, Airflow.

## Risks and caveats

- **Licenses.** AGPL-3.0: shannon, spotube, mastodon, alist, textgen, siyuan, RSSHub. Not plain OSS: terraform (BUSL-1.1), tldraw (custom license), serverless v4 (custom), GitNexus (noncommercial, to verify), metabase (AGPL + commercial), system-design (CC NC-ND, to verify). No license at all: hacker-scripts, legado, awesome-remote-job, awesome-design-patterns, frontend-dev-bookmarks, GitHubDaily, 30-Days-Of-JavaScript, Summer2027-Internships.
- **Dead or stale (last push over 2 years):** hacker-scripts, PythonDataScienceHandbook, awesome-design-patterns, algorithm-visualizer, karan/Projects, frontend-dev-bookmarks, big-list-of-naughty-strings (data still useful). Semantic-UI is just under the line and effectively frozen; moment is in maintenance mode (use dayjs). aider has had no push for about 6 months.
- **Use only on what you own.** shannon runs real exploits; x64dbg, 3x-ui and v2ray-core are dual-use. v2ray-core is largely superseded by Xray-core.
- **Pipe-to-shell installers** (herdr `irm | iex`, CowAgent `irm | iex` from a third-party CDN, acme.sh, 3x-ui): review the script before running; never run unattended.
- **Third-party keys.** freellmapi stores many provider API keys and relies on free tiers whose terms may forbid pooling; treat as unstable.
- **Not for Windows:** apple/container, iina, exo (macOS), legado (Android), Homebrew (WSL only).
- **Check ownership:** `lysine-dev/okhttp` (OkHttp is normally under Square); `prisma/orm`, `calcom/cal.diy`, `oobabooga/textgen` are renamed repos.
- **Unverified install commands** are marked with `?` in the JSONL (mostly winget ids and newer agent tools).
- **README aimed at agents:** shannon's README has a note telling AI agents to start from its llms.txt; treated as data and not followed.
