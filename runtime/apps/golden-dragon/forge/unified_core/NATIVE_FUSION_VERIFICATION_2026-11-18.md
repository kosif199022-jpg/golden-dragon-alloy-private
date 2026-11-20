# Native fusion execution registry — 2026-11-18

This is the first explicit, executable core of Golden Dragon that does **not** import or run the White Bird / Golden Bird source generators.

## Actual architecture

The Golden Dragon-owned source in `apps/golden-dragon/app/` remains the application baseline. `forge/unified_core/build_standalone.py` constructs a new application from that baseline by structural Python-AST replacement of only the `fusion` tool declaration and its dispatch function, lazy-loading the Anthropic SDK, and bundling a small set of reviewed native engine modules. It does not merge upstream branches, run shell scripts from the catalog, overwrite user data, or alter the installed EXE.

`native_registry.py` is the actual execution boundary. It allows exactly **7 named operations** implemented by `gd_runtime.GoldenDragonCore`:

| Registered operation | Executable backend | Preconditions / side effects |
|---|---|---|
| `catalog.audit` | Python local catalog validator | Read-only; requires index and recipes |
| `source.audit` | Python source inventory | Read-only |
| `binary.pe_header` | Python native PE parser | Read-only; local PE file |
| `binary.imports` | REA CLI | Read-only; local PE file and REA installed |
| `media.probe` | FFprobe CLI | Read-only; local media and FFprobe installed |
| `media.transcode` | FFmpeg CLI | Writes a **new TEMP file**, does not overwrite source; allowlisted profile, explicit approval flag |
| `audit` | Combined local read-only audit | Requires catalog and recipes |

The app's `fusion` interface exposes `action=native_status` and `action=native_exec`. The registry checks known operation names and typed parameters, rejects remote URLs and arbitrary code, and never confuses a passive readiness check with a successful runtime test.

**Approval caveat:** `approve_new_file=true` is a required programmatic flag for `native_exec` conversions; it is not a cryptographically enforced human approval. Applications should obtain the user's explicit confirmation before passing that flag. The existing legacy `transcode_media` tool route remains supported for compatibility and needs a separate UI/permission review.

## Independent build evidence

GitHub Actions run [44343897464](https://github.com/kosif199022-jpg/black-dragon-skill/actions/runs/44343897464) completed successfully on **both Linux and Windows runners**. Each platform passed **20 targeted source/registry/dispatch tests** (40 platform executions total). The tests included:

- Creating the actual independent Golden Dragon application from repository-owned source without calling the Golden Bird / White Bird generators
- Listing its native operation adapters from the generated `fusion` dispatch
- Executing the real native PE header parser on a synthetic executable
- Rejecting arbitrary operation names and conversions missing the approval flag
- Verifying the Windows build script and structural binary checks still require the native registry

That Linux run also generated and uploaded `golden-dragon-standalone-source` (GitHub Actions artifact ID `14444682438`, **919,967 compressed bytes**). It contains **38 files** and a SHA-256 file manifest; retention is seven days. Download the artifact from the workflow run page.

**Boundary of proof:** this validates independent source construction, not a new GoldenDragon Windows executable or full GUI interaction. The 1,101 entries in the legacy fusion catalog have **not** become 1,101 executable adapters: only the explicit seven native operations are bound by the new registry. The previous isolated Windows EXE was built *before* this registry, so that older binary cannot be claimed to contain it.

**State:** PR #23 remains a draft, `main` is unchanged, and the original installed program has not been replaced. The owner's Windows device was offline for these most recent checks. Next gates: compare inherited source behavior, rebuild the full app on Windows from the independent path, exercise GUI and representative engines, and gradually convert catalog-only items to tested adapters.
