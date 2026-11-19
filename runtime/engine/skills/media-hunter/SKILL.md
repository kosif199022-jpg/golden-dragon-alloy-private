---
name: media-hunter
description: Media Hunter within Black Dragon: search currently integrated open/free media APIs for footage and photos, discover complementary site-search links for museums, art, HDRIs, textures, icons, GIFs, wallpapers, record asset-source and license metadata. Use on Arabic or English requests for "هاتلي لقطات", "فوتيج", "فيديوهات مجانية", stock footage, b-roll, free photos, media archives, open art, 3D textures, HDRIs or montage references. Only claim live results for actually queried and answered providers; always check per-asset rights.
---

# Media Hunter — Black Dragon v10.2.0 integration

Load this as a subskill inside `black-dragon/` (it uses that bundle's script, not a hard-coded Windows desktop path).

The owner's uploaded `SKILL(2).md` describes an external Windows installation at `C:\Users\cinde\OneDrive\Desktop\تحليل\media_hunter\mh.py`, plus a proprietary/local 615-site index and 19-API engine. **That program and the 615-site index were not included in the attachment**, so they are **not** claimed to be bundled or tested. See `../../references/MEDIA_HUNTER_UPLOADED_SOURCE.md`.

From the `black-dragon/` folder:

```bash
python scripts/dragon.py tool hunter sites "camel desert sunset" --type video --free
python scripts/dragon.py tool hunter hunt "camel desert sunset" --type video --orientation portrait --limit 20
python scripts/dragon.py tool hunter search "old city" --type image --sources openverse,wikimedia,nasa
python scripts/dragon.py tool hunter sites "museum art" --type art
python scripts/dragon.py tool hunter links "sunset studio" --type hdri --out out/media-hunter/hdri.html
python scripts/dragon.py tool hunter get 1 3 --out out/project/footage --dry-run
python scripts/dragon.py tool hunter get 1 3 --out out/project/footage
python scripts/dragon.py tool hunter keys
python scripts/dragon.py tool hunter build --out out/media-hunter/catalog.json
```

- `hunt` uses the existing, tested stock provider adapters; it makes network requests only when invoked. It stores `out/media-hunter/last_hunt.json` and two provider-native result files for numbered `get` downloads. Provider failures are reported in `searched_sources` rather than hidden.
- `sites`, `links`, `keys`, and `build` are offline. `more_sites` is a list of URLs for **manual discovery**, not online search results. The local merged list has 31 unique entries (not 615); some are discovery-only.
- `--type`: `any`, `video`, `image`, `art`, `hdri`, `texture`, `3d`, `icon`, `gif`, `wallpaper`. Types without a bundled API only show search links; avoid reporting them as fetched results. For clip-specific licensing, `license` / `license_url` / `page_url` are recorded, but never amount to a grant of rights. `--free` filters catalog sources tagged paid; it does **not** verify each clip's rights.
- Search in concise English for better results; the bundled Arabic dictionary handles several common keywords but is not a full translator. `--min-width 3840`, `--orientation portrait`, `--per-source 15` narrow results; sources lacking proven dimensions are excluded if a minimum width is requested.
- Pexels/Pixabay/Unsplash require appropriate API keys in the environment; GIPHY is discovery-only, even with a key. `keys` never prints secret values. No automatic setup, download, generation, credit spend or private file upload.
- `get` requires an explicit command, reuses the vetted video/photo stock downloaders, and writes attribution/sidecars. It blocks unknown or restricted licences unless `--acknowledge-rights` is given **after checking the original asset page**. For commercial production use `--commercial` and review the actual licensing text before publishing.
- Do not claim any downloaded file without verifying it exists and passes the relevant `verify` / `ffprobe` media QA, and do not equate site links, API availability or indexed methods with executed tools.
