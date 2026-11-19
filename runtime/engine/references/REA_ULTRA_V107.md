# REA Ultra integration — 10.7

**Source:** user-uploaded `rea-ultra.zip`; SHA-256: `bc5a75acaf9387c79f3725873f63f61263a43a7e8d5b4bb1844661c365b316b3`.

## Source inventory

Copied the REA Ultra `SKILL.md`, source tool helper `scripts/rea_digest.py`, the Windows-only `rea_env_check.ps1`, 18 Markdown references and 4 text/source/license artifacts. The upstream MIT notice is preserved in `skills/rea-ultra/references/upstream/LICENSE-REA.txt`. Methodology includes artifact triage, PE/managed/JS/Electron, APK, mobile firmware, web networks, Ghidra/JADX guidance, companion-tool descriptions and evidence limits. This is a documented skill, not an included installation of the `rea-agents` engine.

## New executable offline Python interface

`tools/rea_ultra/bridge.py` is independently implemented, stdlib-only. It **never launches sample files**, executes REA, uses the network, extracts ZIP, installs software or creates outputs except an explicitly named new JSON report. File SHA-256 digests stream in chunks. A structured record distinguishes observed, inferred, and unknown, includes entropy of sampled bytes, and states its limitations. A separate `verify` command detects changes after capture; this is **integrity only**, not factual truth.

Potential tools are offered as recommendations for an authorized future environment; no executable adapter for decompilation or runtime tracing is bundled. Doctor checks PATH and states that even a found program has not been launched.

## Evidence semantics

- observed = bytes and metadata read from the supplied file (format heuristic, entropy sample, SHA-256)
- inferred = interpretations marked as hypotheses (e.g. APK-like ZIP)
- unknown = behavior, intent, actual runtime API use, whether user has rights to inspect target
- failure = nonzero exit on invalid data, existing target output, changed evidence

## Security and privacy

Remote uploads, live instrumentation, app installation and dynamic debugger runs require independent consent and a verified legal scope. No prompt-like text from files is executed. No server connections. `doctor` is passive and platform-dependent. Scripts in `skills/rea-ultra` are bundled as source references and should be reviewed before any user chooses to invoke them.

## Testing

The `app/tests/test_v107_rea_ultra.py` suite uses synthetic fixtures for PE/ELF/Mach-O/WASM/SQLite/APK/ZIP and tampering, so it verifies the local bridge contract **not** full Ghidra or REA decompilation. Older engine regression suites run separately. See `TEST_REPORT.md` for exact counts.
