# Case study — native PE with Ghidra via REA: adb.exe (Android platform-tools r37.0.1)

Target: `C:\Users\cinde\re-tools\platform-tools\platform-tools\adb.exe`, PE32 x86, 8,273,560 bytes,
sha256 `b4a6b455702684652cccf7b46258b29e653538904359a58fd4931cf3ef286b3f`. Static only.
Artifacts: `C:\Users\cinde\re-tools\cases\adb\` (pe_imports/pe_certs/pe_loadcfg/pe_res/entropy/overview/search_devices JSON).
Date: 2026-11-09. Engine: REA 6.8.0 + Ghidra 12.1.4 + JDK 21.0.13, Windows 11.

## 1. Triage without an engine (seconds)
| Step | Tool | Result |
|---|---|---|
| Identity | `diec adb.exe` (companion) | PE32, LLVM/LLD + MinGW, Windows Authenticode, CodeView debug [O] |
| Imports/certs/load-config/resources/entropy | `inspect_pe_*`, `inspect_byte_entropy` | saved in cases\adb\*.json [O] |
| PDB reference | (Ghidra limitation text) | `adb.pdb` GUID c541d287-…, not loaded → names are `FUN_xxxx` [O] |

## 2. String → xref → function (the core loop) — MCP, all [O]
1. `search_strings {pattern:"devices"}` → 28 hits (ev_bfec83a1…). Chosen: `0xa28367` = `"List of devices attached\n"` (the `adb devices` header).
2. `xrefs {address:"0xa28367"}` → single reference `0x4070a8` (ev_4ebc114a…).
3. `resolve_containing_procedure {address:"0x4070a8"}` → `FUN_00406150` @ `0x406150`, body 12,950 bytes in 3 non-contiguous ranges (ev_79c550a3…).
4. `procedure_callers {procedure:"0x406150"}` → one caller `0x41aa60` (relationship coverage complete for resolved direct calls) (ev_09c47507…).
5. Limitations listed ~60 terminal calls from this function to `FUN_00402aa0` (hasNoReturn=true) and one to `FUN_00403110`.

Interpretation [I]: `FUN_00406150` is adb's command-line dispatcher (upstream `adb_commandline`): huge single function, holds the `devices` output header, one caller (likely main path `0x41aa60`), many no-return calls ≈ `error_exit`/usage-style fatal helpers. Confirm by decompiling `0x402aa0` (expect format-string + exit) before naming it.
Unknown [U]: indirect/computed calls; whether `0x41aa60` is `main` (not decompiled in this run).

## 3. Failures and their fixes (the valuable part)
| Symptom | Cause | Fix |
|---|---|---|
| `provider_timeout`: "did not finish importing … within 330000 ms" on first query after `open_binary` | default `ghidra.startup_timeout_ms` = 330 s; 8 MB x86 PE needed longer | `update_analysis_settings {changes:[{setting:"ghidra.startup_timeout_ms",action:"set",value:1200000}]}` → retry the **same query once** → succeeded. No REA restart needed. |
| CLI `rea xrefs … --snapshot adb.snapshot.json` → `evidence_integrity_mismatch / profile_mismatch` | snapshot was saved under a different analysis profile (provider/profile digest differ) | Snapshots only load with identical binary + provider + canonical profile. Save the snapshot from the **same** command family/provider you will reuse, or skip it. |
| `set_address_name` → `capability_unavailable: Windows Ghidra P0 does not admit database mutation` | Windows P0 is read-only | Keep names in your report/ledger (or `record_unknown`), not in the DB. Annotation needs the Linux/macOS provider. |
| `open_binary` returns instantly but the next call blocks minutes | Ghidra import + auto-analysis is lazy (runs on first provider query) | Expect it; budget time on the first query only. Subsequent queries in the same MCP session are seconds. |
| Ghidra stdout full of `Unable to read bytes at ram:cccccccc` | decompiler probing padding/invalid pointers during auto-analysis | Noise; not a failure. |

## 4. Timings (observed)
- where.exe (64 KB x64): CLI analyze ≈140 s cold; MCP decompile `entry` after open ≈ seconds once imported.
- adb.exe (8 MB x86): MCP first query > 330 s (timed out), succeeded after raising the deadline; follow-up xrefs/resolve/callers: seconds each.
- CLI commands each start a fresh Ghidra import → **prefer the MCP session for multi-step native work**; use CLI only for one-shot questions.

## 5. Lessons for the agent
1. For native PE: run engine-free triage first (diec, `inspect_pe_*`, entropy, capa) — it answers most "what is this" questions in seconds.
2. Before opening a >2 MB binary with Ghidra, raise `ghidra.startup_timeout_ms` (e.g. 1,200,000) proactively.
3. Do the whole string→xref→function→callers loop inside **one** MCP session; never reopen between steps (reopening repeats import).
4. Pick distinctive strings (`"List of devices attached\n"`) over generic ones (`"devices"` had 28 hits).
5. Huge function + many no-return calls = dispatcher/CLI parser; decompile the no-return callee to confirm `error_exit`.
6. Windows P0 is read-only: keep a naming ledger in the report instead of renaming.
7. Always `close_binary` at the end (frees the Java process).
