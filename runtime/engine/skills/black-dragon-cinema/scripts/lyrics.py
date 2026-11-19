"""Transcribe each song (Arabic) with word timings so sections and cuts can follow the lyrics."""
import json, sys
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding="utf-8")

model = WhisperModel("small", device="cpu", compute_type="int8")
for path in sys.argv[1:]:
    # faster-whisper's own decoder breaks with the installed PyAV, so hand it 16 kHz mono samples
    import librosa
    audio, _ = librosa.load(path, sr=16000, mono=True)
    segs, info = model.transcribe(audio, language="ar", word_timestamps=True, vad_filter=True)
    out = []
    print(f"\n== {path.split(chr(92))[-1]}")
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in (s.words or [])]})
        print(f"{s.start:7.2f}-{s.end:7.2f}  {s.text.strip()}", flush=True)
    json.dump(out, open(path.rsplit(".", 1)[0] + ".lyrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
