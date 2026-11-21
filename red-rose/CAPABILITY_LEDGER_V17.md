# 🌹 Capability ledger — V17

| Adapter | Effect | Local implementation | Test evidence |
|---|---|---|---|
| `video.timeline_analyze` | read | FFmpeg silencedetect + sampled RGB visual scene boundaries | `test_audio_scene_v17.py` |
| `video.edit_suggest` | read | Bounded and explainable EDL, ranking shots by acoustic activity and duration | `test_audio_scene_v17.py` |
| `video.recut` (V16) | approved write | FFmpeg trim+concat original footage and preserve audio | `test_scene_edit_v16.py`, V17 end-to-end |

Total: **15 registered native adapters**, not 15 fully autonomous agents. User's imported knowledge summaries are not executable capabilities.

Local evidence: 154/154 tests passed with resource warnings promoted to errors. A three-color footage+audio synthetic fixture had two cuts, quiet sections at either end, a proposed EDL selecting the center 1s, and an explicitly approved H264/AAC recut verified with FFprobe and full decode.

No semantic understanding, transcription, speaker detection, phoneme alignment or professional automatic editing is claimed. The full 1,400 requirements are not implemented.
