## v10.10 Guardian

```bash
python scripts/dragon.py play-check video.mp4 --fix
python scripts/dragon.py status --json
python scripts/dragon.py tool hunter615 sites "sea" --type video --json
python scripts/dragon.py tool physics doctor
```

## 10.9 Physics & Math
```bash
python scripts/dragon.py tool physics doctor
python scripts/dragon.py tool physics calc "sqrt(2*20/g)"
python scripts/dragon.py tool physics camera fov --focal 35 --sensor s35
python scripts/dragon.py tool physics beats --bpm 128 --duration 12 --fps 30
```
See `references/PHYSICS_MATH_V109.md`; no paid services and no frame/video rendering in this calculator.


## 10.8 Visual Forge
```bash
python scripts/dragon.py tool visual-forge doctor
python scripts/dragon.py tool visual-forge plan --brief "إعلان على البحر" --kind video --shots 3 --out out/film
# املأ out/film/plan.json ثم شغّل:
python scripts/dragon.py tool visual-forge prompts out/film/plan.json
python scripts/dragon.py tool visual-forge verify-prompts out/film/prompts/prompt_receipt.json
```
### REA Ultra (v10.7) — تحليل ساكن آمن

```bash
python scripts/dragon.py tool rea-ultra doctor
python scripts/dragon.py tool rea-ultra triage your-authorized-file.exe --out out/rea.json
python scripts/dragon.py tool rea-ultra plan your-authorized-file.exe
python scripts/dragon.py tool rea-ultra verify out/rea.json
```

الفحص لا يشغّل العينة ولا Ghidra/REA ولا يثبت برامج. راجع `README_UPGRADE.md`.

## Absolute Creativity (v10.6)

```bash
python scripts/dragon.py tool creativity font-doctor
python scripts/dragon.py tool creativity spin "فيلم تكريم 30 ثانية" --n 12 --seed 42 --json
python scripts/dragon.py tool creativity brief --task "فيلم تكريم 30 ثانية" --out creative-brief.json
python scripts/dragon.py tool creativity audit creative-brief.json
python scripts/dragon.py tool creativity style-check examples/v106-style-bible.json
```

`brief` returns an unfilled template: `audit` must fail until a human or editor fills and scores it. No generation or installation occurs. See `references/ABSOLUTE_CREATIVITY_V106.md`.

## Blender Pro (v10.5)

`python scripts/dragon.py tool blender-pro doctor` for environment; `plan arabic_gold_logo` to inspect a JSON recipe. Rendering needs Blender and explicit `--execute`. See `references/BLENDER_PRO_V105.md`.

# Black Dragon v10.2.0 — quick start

Use Python 3.10+ and unzip in a directory you control. No automatic pip install is needed just to browse the catalog.

```bash
cd black-dragon
python scripts/dragon.py where
python scripts/dragon.py setup --dry-run
python scripts/dragon.py probe-tools --json
python scripts/dragon.py v10 catalog-audit --limit 0
python scripts/dragon.py tool stock sources
python scripts/dragon.py tool stock check
python scripts/dragon.py tool hunter sites "camel desert sunset" --type video
python scripts/dragon.py tool hunter keys
python scripts/dragon.py tool hunter links "museum art" --type art
# tool hunter hunt runs actual network search; get requires an explicit numbered download
python scripts/dragon.py tool stock search "Alexandria sea" --sources nasa --limit 3
python scripts/dragon.py v10 think "30-second advertisement" --domain video
python scripts/dragon.py verify --help
python scripts/dragon.py v10 gate --help
```

On Windows, substitute `python` for `python3` as appropriate. A real network search may require access and per-provider credentials. A search result is not permission to download or distribute it. For the full workflow see `SKILL.md`, `README_UPGRADE.md` and `references/V10_MANUAL.md`.

### Ultra Mind — v10.3
```bash
python scripts/dragon.py v10 ultra plan "حل عطل محاسبي" --domain code --level L2
python scripts/dragon.py v10 ultra audit examples/ultra-review-sample.json
python scripts/dragon.py v10 ultra calibrate examples/ultra-calibration-sample.json
```
A plan is not proof that a task was completed; a matching local SHA-256 is file integrity, not truth.

### Expert Council 10.4
`python scripts/dragon.py v10 council plan "راجع فيديو" --domain editing --size 5`
`python scripts/dragon.py v10 council audit council.json`
`python scripts/dragon.py v10 council lessons search "الإيقاع" --domain editing`

### v1990.2 — montage and Windows command review

`python3 scripts/dragon.py tool montage-arena --help` (decision arena, separate from `tool arena`); `python3 scripts/dragon.py tool windows-lint --shell powershell "COMMAND"` (text only, never executes command). See `references/V19902_MONTAGE_WINDOWS.md`.
