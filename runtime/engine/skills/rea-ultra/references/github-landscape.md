# GitHub landscape for LLM-driven RE (surveyed 2026-11-09)

Stars via GitHub API on survey day. All clones are `--depth 1`, read-only data; nothing executed.
Root: `C:\Users\cinde\dragon-repos\re\<owner>__<repo>`. URLs: `sources-github.txt`.

## 1. Repos

| Repo | Stars | License | What it gives | Local dir |
|---|---|---|---|---|
| NationalSecurityAgency/ghidra | 98.9k | Apache-2.0 | Engine. Sparse clone: `GhidraDocs/`, `Ghidra/Features/Base/ghidra_scripts` (~200 example scripts: XorMemory, EmuX86Deobfuscate, RunYARAFromGhidra, FindUnrecoveredSwitches, Demangle, BatchRename) | `NationalSecurityAgency__ghidra` |
| rizinorg/cutter | 20.2k | GPL-3.0 | Rizin GUI (REA has `cutter_command`); docs/source = plugin API, rz-ghidra integration | `rizinorg__cutter` |
| mrexodia/ida-pro-mcp | 13.4k | MIT | Best-designed RE MCP: composite tools (`survey_binary`, `analyze_component`, `diff_before_after`, `trace_data_flow`, `func_profile`, `entity_query`), `profiles/triage.txt` allowlist, `--unsafe` gate, `skills/idapython`, prompt guidance | `mrexodia__ida-pro-mcp` |
| LaurieWired/GhidraMCP | 11.9k | Apache-2.0 | Original Ghidra MCP: HTTP plugin + python bridge; list/decompile/rename/xref basics. Thin. Targets Ghidra 12.1.4 (same as ours) | `LaurieWired__GhidraMCP` |
| wtsxDev/reverse-engineering | 10.8k | none | Awesome list: books/courses/practice/format tools/disassemblers/dynamic/Yara/Android | `wtsxDev__reverse-engineering` |
| trailofbits/skills | 8.1k | CC-BY-SA-4.0 | ~50 Claude plugins. RE-adjacent: `yara-authoring`, `dwarf-expert`, `fp-check`, `audit-context-building`, `firebase-apk-scanner`, `trailmark`, `static-analysis`, `variant-analysis`; plus skill-authoring conventions (AGENTS.md) | `trailofbits__skills` |
| mandiant/capa | 6.3k | Apache-2.0 | Capability detection (rules -> ATT&CK/MBC); backends vivisect, IDA, Ghidra (`-b ghidra`), BinExport2, dynamic; `doc/limitations.md`; scripts (show-features, capa2yara, capa2sarif, bulk-process) | `mandiant__capa` |
| bethington/ghidra-mcp | 6.2k | Apache-2.0 | 220-tool Ghidra MCP, headless server, BSim, doc workflows in `docs/prompts/*` (function-doc V5, string labeling, orphaned code, data section), plate-comment standards, completeness scorer | `bethington__ghidra-mcp` |
| mandiant/flare-floss | 4.2k | Apache-2.0 | Static + stack + tight + decoded string extraction (emulation), Go/Rust strings, tags (`#common #winapi #capa oss`), `--interesting` filter | `mandiant__flare-floss` |
| zinja-coder/jadx-ai-mcp | 3.0k | Apache-2.0 | JADX plugin + MCP: paginated search/xrefs, rename class/method/var, sample prompts. REA already uses JADX headless MCP | `zinja-coder__jadx-ai-mcp` |
| clearbluejar/ghidriff | 819 | GPL-3.0 | Ghidra patch-diff CLI -> json/md/html (added/deleted/modified funcs), one command | `clearbluejar__ghidriff` |
| mandiant/capa-rules | 751 | Apache-2.0 | ~900 YAML rules, namespace taxonomy, `doc/format.md`, `nursery/` for unreviewed | `mandiant__capa-rules` |
| zinja-coder/apktool-mcp-server | 709 | Apache-2.0 | smali list/get/modify, manifest, resources, build_apk | `zinja-coder__apktool-mcp-server` |
| frida/frida-tools | 536 | NOASSERTION | frida CLI sources (`frida_tools/`: tracer, itracer, discoverer, apk, pm) | `frida__frida-tools` |
| fosdickio/binary_ninja_mcp | 456 | GPL-3.0 | Binja MCP; malware-analysis prompt; multi-binary `selectBinary`; callers/callees summaries; paginated `/strings/filter`; type/field xrefs | `fosdickio__binary_ninja_mcp` |

Not cloned: Frida CodeShare (web snippets only, no repo), NoraCodes tutorials (nothing notable found), HexRaysSA/ida-mcp (official successor to ida-pro-mcp; ida-pro-mcp README recommends it), Binary Ninja itself (commercial). No notable-star "Ghidra-headless agent" besides bethington's headless server.

## 2. Techniques to adopt (mapped to REA tools)

### 2.1 Workflow / prompt patterns
1. **Triage-first, one composite call** (ida-pro-mcp `survey_binary`: "use as FIRST call; do not call list_funcs/imports/find_regex separately"). REA: `binary_overview` + `inspect_pe_imports` (summary) + `list_strings` top + `inspect_byte_entropy` as a fixed opening bundle, then `search_procedures`. Rank functions by xref count and classify thunk/wrapper/leaf/dispatcher/complex (`list_procedures` + `procedure_callers` counts + `analyze_function` summary).
2. **Never let the LLM convert bases/endianness** (ida-pro-mcp and binja READMEs: `int_convert`/`convert_number` mandatory). REA has no converter: use `python -I -c` or `read_bytes` + explicit struct decode and name the producer in the report. Add as a hard rule.
3. **Normalise before asking the LLM** (ida-pro-mcp README): LLMs fail on obfuscation. Remove string encryption, import hashing, CFF, anti-decompile tricks first; resolve library code with signatures (FLIRT/Lumina/BSim). REA: `match_native_functions`, `inspect_byte_entropy` (packed?), `resolve_native_call_targets`, `trace_native_values`; strings see 2.4.
4. **Annotation loop order** (bethington V5): (a) classify (thunk -> fast path), (b) rename + set prototype together, (c) type-audit locals (resolve `undefined*` BEFORE naming; no pointer-prefixed name on int-typed var), (d) re-fetch variables (prototype change re-decompiles, new SSA vars), (e) comments LAST (`set_function_prototype` wipes plate comments), (f) verify. REA: `annotate_native_function`, `set_address_name`/`set_addresses_names`, `set_comment`, `set_inline_comment`, re-read `procedure_pseudo_code` after each step, `verify_reconstruction`.
5. **Batch-first writes** (both servers): one `set_addresses_names` with N pairs, never loops of single renames.
6. **Rename-and-show-diff** (ida-pro-mcp `diff_before_after`): after each rename/type change re-read pseudo code and confirm readability improved. REA: `procedure_pseudo_code` before/after, keep both Evidence IDs.
7. **Hygiene score != truth** (bethington V5 rule 8): a completeness scorer checks docs are present, not correct. Re-check key claims against disassembly (`procedure_assembly`, `read_function_instructions`) before reporting. Matches `verify_reconstruction` / `evaluate_reconstruction_coverage`.
8. **Decompiler language-variant stamp** (bethington gotcha): wrong processor variant (e.g. PowerPC VLE) yields "syntactically perfect and fictional" pseudocode. For non-x86/ARM64 targets record architecture/language (`list_architectures`, `inspect_binary_layout`) in the answer and cross-check one function with `procedure_assembly`.
9. **Orphaned-code discovery** (bethington workflow): scan gaps between functions in exec segments for disassembled-but-unowned instructions, then prologue patterns; classify each candidate before `create_function`; iterate (boundaries shift). REA: `list_unknowns`, `record_unknown`, `update_unknown`, `verify_unknown_resolution`, `search_bytes` for prologues (`55 8B EC`, `48 89 5C 24`).
10. **Global/data labelling** (STRING_LABELING_CONVENTION, GLOBAL_DATA workflow): paginate `list_strings` (<=5000/pass), categorise by use (api/dll/path/fmt/err/ui/src), label 20-30 per batch, re-list to verify, count success/skip/fail. REA: `list_strings`/`search_strings` -> `set_addresses_names`.
11. **Component analysis** (`analyze_component`): related function group with internal call graph and shared data in one call. REA: `analyze_function` per member + `get_call_graph`/`build_call_path`; seed with `trace_feature`.
12. **Data-flow from a constant/string** (`trace_data_flow` fwd/bwd, depth default 5, max 20; "use when you find an interesting string, constant or global"). REA: `xrefs` -> `procedure_callers` chain, `trace_native_values`, `trace_call_path`; cap depth ~5.
13. **Sub-agents for deep dives** (can1357 prompt in ida-pro-mcp README): fan out per function cluster, each returns findings + evidence IDs. Already SKILL.md rule 8.
14. **Report discipline** (binja malware prompt): start at entry point, follow callees, summary comment per function, report elapsed time, write report, verdict "based only on these findings".
15. **Derive, don't brute force** (ida-pro-mcp crackme prompt): no brute forcing; derive from disassembly + simple scripts; present candidate to user.

### 2.2 Large-output handling
- ida-pro-mcp: tool **profiles** (`profiles/triage.txt` = 9 tools "small enough to keep small models on-task"; `readonly.txt`); `detail_level=minimal` for >10k functions; iteration cap + `truncated` flag; field projection (`fields=`); cached strings with invalidation.
- bethington: measured schema cost (251 tools ~12.9k tokens = 6.5% of 200k); the real bottleneck is **discoverability**, solved by tool groups/category filter and consolidation (`get_functions(fields=...)`, `find_functions`, `list_program_items`).
- binja: `/strings?offset&limit`, `/strings/filter?filter=`; jadx-ai-mcp: every search/xref paginated.
- REA map: `detail:"summary"` first, then `inspect_analysis_view` with `parent_evidence_id`; `rea_digest.py` for saved results; for a narrow task declare a "profile": triage = `binary_overview, search_procedures, procedure_pseudo_code, xrefs, procedure_callees, list_strings, procedure_assembly`.

### 2.3 Capability detection (capa)
- Rule = YAML: `meta` (name, namespace, scopes static/dynamic, `mbc`, `att&ck`, references, examples) + `features` boolean tree (`and/or/not/N or more`, `api:`, `string:`, `number:`, `mnemonic:`, `characteristic(loop)`, `match:` other rule). Top namespaces: `anti-analysis, collection, communication, compiler, data-manipulation, executable, exploitation, host-interaction, impact, linking, load-code, persistence, runtime, targeting, malware-family`.
- Scopes: file / function / basic block / instruction (+process/thread/call dynamic). Function-scope rules need ALL features inside the same function.
- Precision choice worth copying: rule `check for debugger via API` deliberately omits `kernel32.IsDebuggerPresent` because CRT/exception-handler code calls it (many FPs). Prefer API/constant combinations over one common API.
- Top-level output hides capabilities implied by a displayed rule (less noise).
- Limitations to quote (`doc/limitations.md`): packed samples, installers/runtimes (AutoIt), wrapper functions (child-function matches are not attributed to the parent; Go layers calls), no loop scope (only `characteristic(loop)`); results may be misleading if packed -> unpack first.
- Ghidra backend: `capa -b ghidra <file>` (PyGhidra), same Ghidra family as ours.
- REA map (no capa inside REA): build a capability table from `inspect_pe_imports` + `search_procedures`/`xrefs` showing which function holds the API set; tag with ATT&CK/MBC names; require the API set in the SAME function (e.g. VirtualAllocEx + WriteProcessMemory + CreateRemoteThread) before claiming "process injection"; imports alone = "capable of" (SKILL rule 6).
- Rule-author checklist (capa-rules): list examples, references, avoid FP-prone single APIs, park WIP in `nursery`.

### 2.4 String deobfuscation (FLOSS)
- Four classes: static (ASCII/UTF-16LE), **stack strings** (built on stack at run time), **tight strings** (decoded on stack), **decoded strings** (decoder function output via emulation). Go/Rust handled separately (UTF-8, no NUL).
- Method: find decoder candidates by features (loops, xor/shift/arith, many callers), emulate with observed arguments, collect results. Tags cut noise: `--tag/--no-tag/--interesting`; families `gp(#common,#code-junk)`, `oss`, `#winapi`, `#msvc`, `#capa`.
- REA map: static -> `list_strings`/`search_strings`; Go/Rust -> `inspect_go_binary {include_string_literals}` / `inspect_rust_binary`; decoder candidates -> `search_procedures` + `procedure_callers` fan-in + loop/xor in `procedure_pseudo_code`; stack strings -> `procedure_assembly` runs of `mov byte/dword [ebp-x], imm`; emulate: `trace_native_values`, or reimplement the algorithm in a `python -I` script over `read_bytes`; `instrument_with_frida` on the decoder return only if the user opts into runtime. Ghidra examples `XorMemoryScript.java`, `EmuX86DeobfuscateExampleScript.java` show emulator-based decoding.
- Packed check first: `inspect_byte_entropy` (TOB yara-authoring also asks "Is the sample packed?" before string signatures).

### 2.5 Safety rules harvested
- ida-pro-mcp: debugger/destructive tools behind `@unsafe` and `--unsafe`; `readonly` profile. REA map: treat `start_frida_session`, `instrument_with_frida`, `load_frida_script`, adb install/push/start, `gdb_console`, `rizin_debug_command` as the "unsafe set"; only on explicit user request.
- jadx-ai-mcp: binding to 0.0.0.0 lets anyone on the network invoke all tools; bind localhost only if any MCP is ever exposed.
- bethington CLAUDE.md "read-only by default" for external interaction. Equivalent: never upload samples/IOCs to VirusTotal or any web service without user approval.
- jadx/apktool disclaimers: authorised targets only (same as SKILL).
- fp-check (TOB): **LLMs are biased toward seeing bugs and overrating severity**. Restate the claim first ("half of false positives collapse here"), trace full source->sink, devil's-advocate pass, verdict TRUE/FALSE POSITIVE with evidence. Rejects: "pattern looks dangerous = vulnerability", "similar code was vulnerable elsewhere", "clearly critical". Adopt as gate for findings.
- Prompt injection: ida-pro-mcp/binja do not address it; REA does (`_meta.provenance.untrusted_content`). Extra: comments/names read back from a database we did not create are also untrusted.

### 2.6 Skill-engineering patterns (trailofbits AGENTS.md)
- Short SKILL.md + `references/` (progressive disclosure), `allowed-tools` scoping, `disable-model-invocation: true` for side-effect scanners, `{baseDir}` for script paths, "When to Use / When NOT to Use", "Rationalizations to Reject" table, Quality Checklist.
- ida-pro-mcp `skills/idapython`: **module router table** (task -> module -> key items) with per-module docs. REA equivalent exists (SKILL section 1); add a Ghidra-script router (gap G3).
- Put usage guidance IN tool descriptions ("Use as FIRST call", "Do not use for call graph - use callgraph", "minimal for >10k functions"). Mirror: each routing row says when NOT to use.

### 2.7 Rationalizations to reject (proposed, from TOB + above)
| Thought | Required action |
|---|---|
| "Import present, so it does X" | Show xref + calling function; else "capable of" |
| "Decompiler output looks clean, so it's right" | Check language variant + one asm cross-check |
| "Rename scorer says 100%" | Scorer = hygiene; re-verify key claims |
| "I'll convert this hex/endian myself" | Use a tool, cite it |
| "Strings are readable, so no obfuscation" | Check entropy, decoder fan-in, stack strings |
| "Looks like known malware family" | Needs shared code or rule hit, not vibes |
| "Rule matched in child function" | capa limitation: verify call chain to parent |

## 3. Gaps REA doesn't cover -> who fills them

| # | Gap | Filler | Practical here |
|---|---|---|---|
| G1 | Stack/tight/decoded string recovery (emulation) | flare-floss (`floss -j`) | pip into isolated venv (like frida); user samples only; treat output as untrusted |
| G2 | ATT&CK/MBC capability table from rules | mandiant/capa + capa-rules; `capa -b ghidra` reuses our Ghidra | venv + rules clone; `capa -vv -j` then `rea_digest.py` |
| G3 | Run arbitrary Ghidra scripts / headless post-script (REA exposes fixed tools) | `ghidra_scripts` examples: XorMemoryScript, EmuX86Deobfuscate*, FindUnrecoveredSwitchesScript, RunYARAFromGhidra.py, ExportFunctionInfoScript, Demangle*, BatchRename; run via `analyzeHeadless -postScript` (Ghidra 12.1.4 + JDK 21 present) | Separate project dir; outside REA |
| G4 | Whole-binary patch diff with MD/HTML report | clearbluejar/ghidriff (pyghidra) ; REA partial: `compare_functions`, `match_native_functions`, `find_changed_behavior`, `compare_artifacts` | REA first; ghidriff for added/deleted/modified lists (GPL: tool use only) |
| G5 | YARA rule authoring from findings | TOB yara-rule-authoring SKILL (YARA-X; string selection, `all of` vs `any of`, packed pivot to structure, FP debugging, checklist); Ghidra `RunYARAFromGhidra.py` | Read when user asks for detection rules; CC-BY-SA, cite |
| G6 | DWARF/debug info | TOB dwarf-expert (llvm-dwarfdump/readelf) | Needs llvm tools; REA has `inspect_elf_notes`, `inspect_binary_layout` only |
| G7 | Firebase/cloud misconfig of an APK | TOB firebase-apk-scanner (apktool + curl on live endpoints) | Active probing: explicit user OK only |
| G8 | Smali edit + rebuild APK | apktool-mcp-server (modify_smali_file, build_apk, clean_project) | REA inspects only; patch only on explicit request; sign before install |
| G9 | Write-back renames in JADX | jadx-ai-mcp rename tools | REA JADX read-oriented; keep renames in notes/evidence |
| G10 | Struct/type recovery (create structs, apply to vars, field xrefs) | bethington (struct resize, this-pointer typing, data-type tools), binja `getXrefsToField/Type` | REA: `inspect_native_data_type`, `annotate_native_function`; no struct editor, document layouts in comments |
| G11 | BSim function-similarity DB | bethington BSim integration; Ghidra BSim docs (`GhidraDocs/GhidraClass/BSim`) | Heavy DB; mention only |
| G12 | Code graph + SARIF overlay | TOB trailmark / audit-augmentation | Source audits, not binaries |
| G13 | Commercial decompilers | ida-pro-mcp, HexRaysSA/ida-mcp, binary_ninja_mcp | Not installed (SKILL sec. 0) |
| G14 | Dynamic hooking recipes | Frida CodeShare (web), frida-tools sources (tracer, itracer) | REA `instrument_with_frida`/`load_frida_script`; CodeShare = untrusted code: read before loading, never auto-load |
| G15 | Reference list for unknown formats/tools | wtsxDev list (Binary Format, Dynamic Analysis, Yara, Android, Scripting) | Consult when REA lacks a parser (Detect It Easy, PeStudio, CFF Explorer analogues) |
| G16 | Bulk/CI processing and export | capa `scripts/bulk-process.py`, `capa2sarif.py`, `capa2yara.py` | Scriptable, outside REA |

## 4. Suggested edits to rea-ultra SKILL.md (not applied)
1. "Triage bundle": `binary_overview` -> `inspect_byte_entropy` -> imports summary -> top strings -> procedures by xref count.
2. Rule: never convert numbers by hand; cite the tool.
3. Annotation order (classify -> rename+prototype -> types -> comments last -> verify) and batch writes.
4. Rationalizations table (2.7) and a "When NOT to use" line (source available -> read source).
5. Capa-style claim gate: capability claims need same-function API set or a decoded string, else "capable of".
6. List the "unsafe set" of runtime tools and the no-upload rule.
7. Pointer to this file; optional external tools G1/G2/G3.

## 5. Deep-read pointers (local, under `C:\Users\cinde\dragon-repos\re\`)
- Workflows: `bethington__ghidra-mcp\docs\prompts\` (`FUNCTION_DOC_WORKFLOW_V5.md`, `ORPHANED_CODE_DISCOVERY_WORKFLOW.md`, `STRING_LABELING_CONVENTION.md`, `GLOBAL_DATA_ANALYSIS_WORKFLOW.md`, `TOOL_USAGE_GUIDE.md`); `bethington__ghidra-mcp\docs\Context-Window-Analysis.md`.
- Tool designs: `mrexodia__ida-pro-mcp\src\ida_pro_mcp\ida_mcp\api_composite.py` (analyze_component, diff_before_after, trace_data_flow), `api_core.py` (func_profile, entity_query), `api_survey.py` (survey_binary), `profiles\triage.txt`.
- Prompts: `mrexodia__ida-pro-mcp\README.md` ("Prompt Engineering"), `fosdickio__binary_ninja_mcp\README.md` ("Malware Analysis").
- capa: `mandiant__capa\doc\{rules,limitations,usage}.md`, `mandiant__capa-rules\doc\format.md`, example `anti-analysis\anti-debugging\debugger-detection\`.
- FLOSS: `mandiant__flare-floss\doc\{theory,usage,tags,language_specific_strings}.md`.
- TOB: `trailofbits__skills\AGENTS.md`, `plugins\fp-check\skills\fp-check\SKILL.md`, `plugins\yara-authoring\skills\yara-rule-authoring\SKILL.md`.
