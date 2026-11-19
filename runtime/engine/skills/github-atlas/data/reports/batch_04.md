# Batch 04 (ranks 301-400) — report

All 100 READMEs fetched. `?` marks install commands not confirmed in the README.

## Top 10 by value_for_claude

1. **FFmpeg/FFmpeg** (5) — the base of every montage task: cut, concat, transcode, audio extraction, subtitles, loudness. `winget install Gyan.FFmpeg`.
2. **rclone/rclone** (5) — one CLI to move large media between local disk and Drive/S3/Dropbox/OneDrive; scriptable, has `--dry-run`.
3. **upstash/context7** (5) — MCP server that gives the agent current, version-specific library docs instead of stale training memory.
4. **mvanhorn/last30days-skill** (5) — agent skill for "what are people saying this month" research across Reddit, X, YouTube, HN, TikTok; works with zero config. Has an Arabic README.
5. **cathrynlavery/diagram-design** (5) — skill that outputs one self-contained HTML+SVG diagram in the user's brand; 45 types, imports drawio/Mermaid.
6. **blader/humanizer** (5) — skill that strips the 26 known "AI writing" tells from text; directly useful for captions and posts.
7. **cloudflare/security-audit-skill** (5) — six-phase audit skill with independent verifiers and schema-validated findings.
8. **git/git** (5) — already the backbone of all repo work.
9. **shanraisshan/claude-code-best-practice** (4) — working reference for subagents, skills, hooks, MCP and settings.
10. **jamiepine/voicebox** (4) — local voice cloning / TTS / dictation studio with an API (CUDA on Windows).
## Recurring patterns worth putting in the skill

- **Skills are now top-1000 material.** Seven repos in this batch are agent skills/plugins. The common install grammar is `npx skills add OWNER/REPO` (cross-agent) or `/plugin marketplace add OWNER/REPO` + `/plugin install NAME@MARKETPLACE` (Claude Code). The atlas should treat "is there a skill for this?" as a first-class lookup.
- **Independent verification.** The Cloudflare skill gives each candidate finding to a fresh agent whose job is to disprove it, and keeps `confirmed / needs_validation / rejected` as separate verdicts validated by a script. Same idea applies to media delivery gates.
- **Zero-config first run, keys later.** last30days, gods-eye-view and MemPalace all work immediately and unlock more with optional keys.
- **One self-contained output.** diagram-design (one HTML file), PocketBase (one executable), Pake (one command) — the shortest path to a visible result wins.
- **Answer first.** i-have-adhd and humanizer both encode output style: lead with the action, number steps, no filler, name concrete anti-patterns with before/after examples.
- **Redirect READMEs.** Moved projects (GSD, base/node, PocketBase, LocalStack) put the new home at the very top — the atlas should follow these redirects rather than recommend the old repo.

## Risks

- **Dead or moved:** base/node (→ base/base), localstack (archived, unified image), gsd-build/get-shit-done (→ open-gsd/gsd-core), pocketbase (archived on GitHub, moved to the author's host), minio (unmaintained, source-only, no community binaries), atom, and microsoft/autogen (not flagged archived by GitHub, but its README says archived and unmaintained). Stale by date (>2 years): nocode, javascript-questions, resume.github.com, architect-awesome, github-cheat-sheet.
- **Free-model routers — handle carefully:** Ebony-Vinyl/dsh-our-free-model, Alishahryar1/free-claude-code and xtekky/gpt4free route agents through third-party or unofficial gateways. Prompts and code go to those upstreams, and provider terms may be violated. The dsh plugin additionally describes maintainer-pushed HTML announcements (including full-screen popups) and in-app self-update, which is a remote-content channel into the user's agent; do not recommend it without an audit. Scored low on purpose.
- **Pipe-to-shell installers that run as admin:** winutil and Win11Debloat (`irm ... | iex`) change system settings and remove apps; openinterpreter and free-claude-code also install via `irm | iex`. Never run these without the user's explicit request.
- **Copyleft / non-OSS licenses:** AGPL-3.0 (ultralytics — commercial use needs an enterprise license, warp, plane, minio, free-claude-code); GPL-3.0 (uBlock, gpt4free, Pake, drawio-desktop, TrendRadar, FlClash, Magisk, v2rayNG); BSL (pathway); unclear/mixed (nocodb, twenty, litellm, gods-eye-view, Real-Time-Voice-Cloning).
- **Voice cloning** (GPT-SoVITS, voicebox): only with the speaker's consent.
- **Impostor sites:** MemPalace and Pake warn about fake download sites.
- **Not on Windows:** ghostty, ladybird (WSL2), coolify, Android-only apps.
