# Desktop and machine-control audit — v1990.3.1 (candidate)

Scope: inspected the user-uploaded `1990.zip` locally, compared it against `v1990.2`. No app executable was installed, started, built, connected to a browser, or allowed to control a user's computer.

## Confirmed improvements
- `Session.auto` defaults to `False` when no stored preference exists.
- Any `TOOLS` item with `_approval=True` is always presented in the app's approval dialog even when the user turned auto mode on: run_engine, run_command, rea, retool, rebuild_app, deployment_status.
- Writing/editing outside the working directory still invokes approval; the previous auto-mode bypass is removed.
- `system` destructive actions in `control.System.DANGER` continue to trigger a separate app confirmation.
- Computer/browser control defaults off, is exposed to the model only when the user enables it, and supports an emergency stop gesture.

## Open risks (not validated in Windows deployment)
- The desktop app, browser extension and local bridge have broad powers and require an installation-specific security review on Windows.
- `machine_map.json` and `MACHINE_MAP.md` include user-specific Windows filesystem paths; keep the ZIP private or redact before sharing.
- Confirmation in the CLI `tool machine pc ... --yes` is only an assertion by the caller, not a separate human authorization mechanism. Use the interactive app confirmation and never let an unattended agent pass `--yes`.
- Query-string local bridge tokens and Chrome extension permissions must be reviewed before broad deployment or external network exposure. The service binds to 127.0.0.1, not to a public interface.
- Older tests reported by the user-uploaded package: 822 passed, 51 failed, 5 skipped on their Windows computer. Root causes of the failures are unresolved. Selective tests here are not a complete certification.

## Operational rules
1. Treat Windows paths in the package as a historical inventory, not paths known to exist in the current execution environment.
2. No setup/build/install, arbitrary command execution, account action, money spent or cloud GPU use without explicit approval.
3. Keep original recordings, assets and projects immutable by default.
4. Inspect executable dependencies and their licenses before installation.
