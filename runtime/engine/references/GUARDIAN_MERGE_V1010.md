# Guardian v10.8 sources incorporated into v10.10

## Source files and evidence

* Original inputs: uploaded `black-dragon-v10.6.0(1).zip`, `black-dragon-v10.7.0(1).zip`, `black-dragon-v10.8.0(1).zip` and `التنين الأسود v10.8 - ما الجديد.txt`.
* Base: previous `black-dragon-v10.9.0.zip`. The separately uploaded v10.8 archive is a parallel branch named Guardian, not a downgrade to v10.8.
* Brought forward: tools/care, tools/media_hunter_615, tools/repo_fusion, tools/repo_link and local checks. New original modules retained; no overwrite of Physics & Math.
* Source notes in the uploaded TXT (e.g. 474 passing tests and a specific Riyadh MP4 repair) are historical assertions from a different Windows machine, **not reverified here**.
* `tool hunter615` includes 615 listed CSV sites but only a subset have usable no-key live APIs; an indexed page is not a verified downloadable file or license. Httpx is optional and network execution is not tested in an offline container. Download is gated behind an explicit license acknowledgement.
* `status` reports jobs run by the local launcher and does not observe work in other sessions. `play-check` is a conservative codec/container and FFmpeg diagnostic, **not a guarantee on every phone**.
* Not ported wholesale: Guardian's Chrome/cloud-browser integration, APK binary and alternate Blender code, since these require different privileged contexts, testing or duplicate existing components. They remain only in user-provided archives.
* No GitHub changes, account access, spending, installs, public publishing, or original-media replacement.

## Reproduce

```bash
python scripts/dragon.py tool hunter615 sites "camel desert sunset" --type video --json
python scripts/dragon.py tool hunter615 get 1     # fails until --acknowledge-license after checking rights
python scripts/dragon.py play-check your.mp4
python scripts/dragon.py resources
python scripts/dragon.py status --json
python scripts/dragon.py tool layout ';LG'
python scripts/dragon.py tool fusion list
pytest -q app/tests/test_v1010_guardian.py
```
