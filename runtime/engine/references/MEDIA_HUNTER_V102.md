# Media Hunter integration and scope — Black Dragon v10.2.0

## Supplied input

The user provided `SKILL(2).md`, a 47-line *Media Hunter* skill describing a **different** Windows installation (`C:\Users\cinde\OneDrive\Desktop\تحليل\media_hunter\mh.py`) whose original engine and 615-site catalog are not part of the upload. Its stated 19 API sources, cache timing, Poly Haven resolution selection and download behavior are **claims about that external installation**, not validated features in Black Dragon.

The full uploaded skill text is preserved in `MEDIA_HUNTER_UPLOADED_SOURCE.md` as reference. Black Dragon v10.2 implements a locally portable integration around bundled source-aware stock clients (video and photo) and makes limited offline discovery suggestions for other families.

## Added features

| Feature | Real implementation | Scope |
|---|---|---|
| `tool hunter sites` | Reads original Black Dragon video/photo source registries, plus 12 supplementary link templates | Offline index of 31 unique providers; no external API calls |
| `tool hunter keys` | Checks environment variable **presence** only | No credentials printed or saved |
| `tool hunter hunt/search` | Runs available video/photo source adapters in a bounded pool, normalizes results and saves provenance | Actual network may be blocked or keys absent; 8s per-request network timeout, not promised total latency |
| `tool hunter links` | Generates a static HTML list with escaping and no scripts | Discoverability only, not provider licensing |
| `tool hunter get` | Routes stored numeric search results back through source-aware downloaders with attribution | Download is explicit, subject to rights checks, destination and max size |
| `tool hunter build` | Exports actual registry to JSON | No automatic replacement or fabrication of 615 sites |

## Architecture

- Entrypoint: `scripts/dragon.py tool hunter ...`
- Implementation: `tools/media_hunter/mh.py`
- Original source text: `references/MEDIA_HUNTER_UPLOADED_SOURCE.md`
- Subskill entry: `skills/media-hunter/SKILL.md`
- Source adapters: `tools/stock/free_footage.py` and `free_photos.py`
- Results: `out/media-hunter/last_hunt.json` and matching `last_video.json`, `last_photo.json`.

## Risk controls and missing features

Media Hunter v10.2 does *not* contain the uploader's `mh.py` executable, the 615-site original catalog or 19 original provider connectors. No actual external provider search is proven by running offline tests. The linked providers Europeana, Smithsonian, Wellcome, Cleveland, Art Institute, V&A, SMK, Poly Haven, ambientCG, Iconify, Wallhaven and GIPHY are discovery-only until independently implemented and tested.

The licensing status is per asset, not per provider; `--free` is a **site-filter hint**, not a licence grant. The downloader writes source records, never bypasses paywalls, rate limiting, DRM or site access restrictions. Search results are metadata, not confirmation of actual files or commercial rights. For full original behavior, the source developer must supply the original Python engine, source catalog and license details for comparison; do not fabricate them.
