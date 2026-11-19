# Installing atlas tools on Windows 11

Field `windows_ok` in the atlas: `yes` 599, `docker` 101, `wsl` 39, `no` 30, `n/a` 231 (lists, courses, libraries).

## Routing order (first that works)

1. **Already on PATH?** `python scripts/atlas.py have`, or `where.exe NAME`. Use it.
2. **winget** for CLI apps: `winget install --id Publisher.App -e` (gh, pandoc, typst, rclone, jq, ripgrep, fd, mpv,
   ShareX, PowerToys). Check the id first: `winget search NAME`.
3. **Python tools: `uv tool install X` or `uvx X`**, else `pip install X` into a venv. Never `pip install` into the
   system Python for a one-off.
4. **Node tools: `npx X`** for one runs, `npm i -g X` only when it will be reused.
5. **scoop** (extras bucket) for portable GUI tools not on winget (Umi-OCR, Bruno).
6. **Release asset** (portable zip or exe) from the repo's Releases page. Get the URL with
   `gh release view -R OWNER/REPO --json assets`, download with aria2c, verify the hash if one is published.
7. **Docker Desktop** for server apps (about a quarter of self-hosted repos: immich, supabase, outline, appsmith,
   searxng, Stirling-PDF, ragflow, uptime-kuma, home-assistant). Say Docker is required; do not fake a native install.
8. **WSL** for Linux-only tools (tmux, Homebrew, acme.sh, Airflow, vllm, Elasticsearch, hackingtool).
9. **No Windows path** (`windows_ok: no`, e.g. Hyprland, iina, apple/container): say so plainly.

## Windows gotchas seen in the READMEs

- In Windows PowerShell 5.1 `curl` is an alias for Invoke-WebRequest. Call `curl.exe`.
- `pyenv` needs the `pyenv-win` fork; `nvm` on Windows is `nvm-windows` (a different project).
- Many READMEs give `curl ... | sh`. A PowerShell twin `irm URL | iex` often exists. Both run remote code unread:
  fetch the script to a file, read it, then run it, and only with the user's go-ahead.
- Torch-based tools: pick the CPU wheel on this PC unless a GPU is confirmed. Model downloads can be gigabytes;
  state the size and ask before pulling.
- Paths with Arabic or spaces: quote them; run Python with `-X utf8`.

## Before running any install line from the atlas

- If `install_windows` contains `?`, the command was not confirmed in the README. Open the README first:
  `gh api repos/OWNER/REPO/readme -H "Accept: application/vnd.github.raw"`.
- Only install from the official repo, its release page, winget, PyPI or npm under the official name.
  Popular tools get typosquatted (scrcpy, ECC and REA warn about fakes).
- Installs change the user's machine: say what will be installed and how big it is, then do it.
