# Red Rose V29 frozen interface (W01)

Every V29 work item reads this file first and builds against it. Changing a name,
key, flag or exit code here needs the orchestrator. Implemented in `rose_ext.py`,
`rose_io.py`, `rose_run.py`; tested by `test_run_v29.py` and `test_crossshell_v29.py`.

## 1. Plugin contract (`rose_ext.py`)

```
EXT_MODULES = ['rose_run','rose_catalog','rose_env','rose_selfcheck','rose_fixtures',
               'rose_agent','rose_recipes','rose_check','rose_pack']
rose_ext.load(subparsers) -> {loaded:[names], failed:[{module, error}], skipped:[names]}
rose_ext.LAST_LOAD          # same dict, kept for `rose.py start`
rose_ext.status()           # copy of LAST_LOAD
```

- Each import and each `register()` runs inside try/except. A missing module, an
  import error or a failing `register()` goes to `failed` (a failing register is
  rolled back: the subcommands it added are removed). Importable modules without
  `register()` (helper modules such as `rose_fixtures`) go to `skipped`.
- Every extension module exposes `register(subparsers)` and gives each parser it
  adds `parser.set_defaults(ext_func=handler)`.
- `handler(args) -> int` returns the exit code and prints exactly ONE JSON
  document on stdout (or text when the command offers `--text`). Use
  `rose_io.emit()` / `rose_io.fail()`; never `print()` a traceback.
- Extension commands never use the global `--db` unless they execute an op;
  they must not open or create any database before their handler decides to.
- Optional: call `rose_io.json_usage_errors(parser)` so argparse usage errors
  become one JSON line with exit 2.

Orchestrator wiring in `rose.py` (the only change W01 needs):

```python
# after the last existing sub.add_parser(...) line:
try:
    import rose_ext; rose_ext.load(sub)
except Exception: pass
# right after args = a.parse_args(argv), before the existing if/elif chain:
if hasattr(args, 'ext_func'): raise SystemExit(args.ext_func(args))
```

## 2. Exit codes (`rose_io`)

| code | constant | outcome |
|---|---|---|
| 0 | `EXIT_OK` | `ok` (also `example_only` with `--example-ok`) |
| 1 | `EXIT_ERROR` | `error` |
| 2 | `EXIT_USAGE` | argparse usage error |
| 3 | `EXIT_APPROVAL` | `approval_required` (nothing was written) |
| 4 | `EXIT_UNAVAILABLE` | `unavailable_here` (missing program/module/DB/pc_only) |
| 5 | `EXIT_EXAMPLE_ONLY` | `example_only` (built-in sample data, NOT the owner's data) |

`rose_io.OUTCOME_EXIT = {'ok':0,'error':1,'approval_required':3,'unavailable_here':4,'example_only':5}`

## 3. `rose_io` functions

```
read_params(args, schema=None, warnings=None, stdin=None) -> dict
    merges, later wins: --params-file FILE (JSON object), --stdin (JSON object),
    positional key=value tokens (args.params), --file-param key=FILE (value = text of FILE).
    key=value typing from schema {param:{type,...}}: declared string/path stays a
    string even for 123/true; integer/number/bool/list/object are parsed; type
    'auto' (unknown) parses numbers, true/false/null, {..}/[..]; no schema -> string.
    key:=RAW always parses RAW as JSON. Inline JSON tokens are refused with a hint.
parse_pairs(tokens, schema=None) -> dict
coerce(key, value, ptype) -> typed value
add_param_arguments(parser)      # adds key=value positional, --params-file, --stdin, --file-param
read_text_bytes(path, warnings=None) -> str   # UTF-8, UTF-8 BOM, UTF-16/32 BOM, cp1256 fallback (+warning)
decode_bytes(data) -> (text, warning|None)
write_json(path, obj, overwrite=True) -> abs path   # UTF-8, no BOM, indent 2, newline at end;
                                                    # overwrite=False refuses an existing file
parse_save_pairs(items) -> [(field, path)]          # 'FIELD=FILE'; comma lists refused
save_fields(result, pairs, overwrite=False) -> {field: abs_path}
    finds FIELD anywhere in the nested result (breadth-first); FIELD absent but
    FIELD_base64 present -> decoded bytes (png -> png_base64); *_base64 fields are
    decoded; str -> UTF-8; dict/list -> JSON. Refuses existing files. Resolves all
    fields before writing, so a bad field writes nothing.
find_field(obj, field), available_fields(obj)
emit(obj, pretty=False, stream=None)     # one JSON document, UTF-8 bytes to stdout
error_doc(error, allowed=None, hint=None, next=None, **extra) -> dict
fail(error, allowed=None, hint=None, next=None, code=1, **extra) -> int
    prints {"ok":false,"outcome":"error","error":..,"allowed":[..]|null,"hint":..,"next":[..]}
json_usage_errors(parser)                # argparse errors -> one JSON line, exit 2
class ParamError(ValueError): .allowed, .hint
```

## 4. Id resolution (`rose_run.resolve_id(text) -> (adapter, op|None, call_shape)`)

- The longest `capability_runtime.REGISTRY` adapter id that is a prefix of
  `text` followed by `.` or end of string wins; the remainder is the op.
- Branch (if/elif) adapters (`video.recut`, `qa.trace`, `fusion.render`, ...): op
  `None`, call_shape `'flat'`; parameters are passed flat to `execute()`.
- Module adapters (`IO_ADAPTERS` and `PURE_MODULES`): an op is required,
  call_shape `'module'`; `run` builds `{"op":..,"params":..}` itself.
- Unknown id / unknown op / missing op -> `rose_run.IdError` (a ParamError) with
  the 5 nearest ids in `allowed` (`rose_catalog.nearest_ids` when importable,
  else difflib). The only agent-facing id syntax is `ADAPTER.OP`.

Other helpers: `all_ids()`, `nearest_ids(text, n=5)`, `schema_for(adapter, op) ->
(schema|None, complete, source)` (catalogue, else signature/AST introspection),
`effect_of(adapter, op, entry=None)`, `needs_of(adapter, op, entry=None)`,
`missing_needs(needs)`, `example_when_absent(op_id, entry=None)`,
`check_params(adapter, op, params)`, `command_line(op_id, tokens)`.

## 5. CLI

```
python -X utf8 rose.py run ADAPTER.OP [key=value ...] [--params-file FILE] [--stdin]
    [--file-param key=FILE ...] [--save FIELD=FILE ...] [--out FILE]
    [--approve-write] [--example-ok] [--pretty]
```

- Parameters and flags may come in any order after the id.
- `--save` is repeated, never comma-separated.
- `--save` and `--out` are writes. Without `--approve-write` the op still runs if
  it is a read op, nothing is written, exit 3, `would_write` lists the files and
  `rerun_with` is the same command plus `--approve-write`. Existing files are
  never overwritten (exit 1 before anything runs).
- With `--approve-write`, `--save` writes only when the outcome is `ok` (or
  `example_only` with `--example-ok`); `--out` always writes the final envelope
  (evidence, also for errors) as UTF-8 JSON.
- Errors always print one JSON line (no traceback). `--pretty` indents successes.
- Database: opened only just before execution. Ops whose catalogue `needs.db` is
  true (fallback: REGISTRY dependency `database`) use `--db`/`$RED_ROSE_DB` when
  given, else the private default only if it already exists, else
  `unavailable_here`. All other ops use an in-memory database (`audit_id` null)
  unless `--db` differs from the default or `$RED_ROSE_DB` is set (then the audit
  row goes there). `run --help`, usage and id/param errors never create a file.
- Cross-shell safe forms (tested in PowerShell 5.1, cmd and Git Bash by
  `test_crossshell_v29.py`): `key="Arabic words"` tokens, `--params-file FILE`,
  `--save field=FILE` with forward-slash paths. Never inline JSON, never `>`.

Python API: `rose_run.run_op(op_id, params, approve_write=False, db_path=None,
example_ok=False) -> envelope dict` (no printing, never raises; no --save/--out).
`rose_run.execute_cli(args)` is the CLI path; `rose_run.exit_code(env, example_ok)`.

## 6. Envelope

```
{"ok":bool, "outcome":"ok|example_only|approval_required|unavailable_here|error",
 "id":"ADAPTER.OP", "adapter":str, "op":str|null, "effect":"read|write",
 "audit_id":int|null, "example_data":bool, "warnings":[str], "saved":{field:path},
 "would_write":[path]|null, "rerun_with":str|null, "result":{...raw execute() result...}|null,
 "error":str|null, "allowed":[str]|null, "hint":str|null, "next":[str]}
```

`ok` is true only for outcome `ok`. Read only `outcome` and the exit code.

## 7. Outcome rule (`rose_run.normalise(raw)`, fail-closed)

`raw` is the execute() dict or the exception it raised.
Returns `{outcome, ok, warnings, example_data, error, hint, allowed, signals}`.

1. Exceptions: `PermissionError` or `ValueError` whose text contains
   `approve_write` -> `approval_required`; `ValueError` starting `pc_only:` ->
   `unavailable_here`; `ImportError` -> `unavailable_here`; `FileNotFoundError`
   for a known program (ffmpeg, ffprobe, blender, ...) or a message naming such a
   program as not found/missing -> `unavailable_here`; anything else -> `error`
   (allowed values parsed from 'allowed: a, b' / 'must be one of [..]').
2. `approval_required` as the value of status / verdict / decision / outcome at
   ANY nesting level -> `approval_required` (covers the five styles: execute()
   top-level status [studio, all write ops], PermissionError [audio, studio],
   ValueError 'requires approve_write' [automation], nested
   result.result.status [database], op-level status + nested [knowledge]).
3. Failure on the result spine (execute dict -> result -> result ...):
   status/verdict/decision/outcome in {blocked, fail, failed, error}, `ok:false`,
   `passed:false`, non-empty `error`; or `qa.passed:false` at any level -> `error`.
4. Warnings are collected from every level; any warning starting
   `arabic_unshaped` -> `error` (do not deliver the raster).
5. `input == 'built_in_example'` or `example_data: true` at any level, or the
   catalogue entry's `example_when_absent` names params none of which was given
   (fallback table in `rose_run.FALLBACK_EXAMPLE_WHEN_ABSENT` for the accounting
   ops) -> `example_only`, exit 5; with `--example-ok` exit 0, `ok` stays false
   and warnings gain `NOT REAL DATA: ...`.
6. Missing program/module from the catalogue `needs` (fallback: REGISTRY
   dependency of branch adapters) is checked before execution ->
   `unavailable_here` (exit 4; hint names what is missing and that other ops work).

Without `rose_catalog`, `run` still works: live REGISTRY names, schemas from
function signatures (module ops) or from execute()'s `_guard_keys` calls
(branch adapters), and unknown-parameter errors list the real parameter names.

## 8. Shared ids for other items

Recipe ids (W08, fixed): `title-frame-ar`, `title-clip-mp4`, `shot-report-recut`,
`captions-from-words`, `loudness-fix`, `bank-reconcile`, `iphone-export`,
`beat-synced-cut`. Recipe run: `rose.py recipe run ID key=value ... --work DIR [--approve-write]`.

Catalogue entry (W02) keys read by `run`: `effect`, `needs{files, db, work_dir,
network, programs, python, pc_only}`, `example_when_absent`, and
`rose_catalog.schema(op_id) -> {param:{type, required, default, choices}}`
(types: string|number|integer|bool|path|list|object), `get(op_id)`, `nearest_ids(text, n)`.

Brief JSON (W07, `rose.py brief "REQUEST" [--prev ..] [--files ..] [--json] [--depth auto|0|1|2|3]`):

```
{understood:{text, fixes}, kind, depth:'L0|L1|L2|L3',
 approvals:[write|network|paid|install|publish],
 first_reply_ar:{understood, will_do:[3-5], estimate_min},
 route:{type:'recipe|op|none', id, matched:[words], alternative:{id}|null,
        candidates:[{id,type,score}], confidence:'unmeasured'|tier},
 slots:{known:[{param,value,from}], assumed:[{param,value}], missing:[{param,risk}]},
 must_ask:[<=3 {param, question_ar, suggest_ar}],
 decision:'go|go_with_assumptions|ask|confirm|none',
 steps:[{n, do_ar, command, params_file_content|null, effect, gate_ar, rerun_with_approval|null}],
 verify:[commands], done_when_ar, rules:[owner rule ids+text], lessons:[<=3],
 readiness:[{id,label}], here:{usable:bool, reason}, chars}
```

Readiness labels (W03): `verified|runs_with_defaults|needs_input|needs_owner_approval|pc_only|coded_untested|known_broken|unavailable_here`.
