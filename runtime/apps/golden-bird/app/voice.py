# -*- coding: utf-8 -*-
"""Voice message helper for the Black Dragon app (runs in the system Python, not inside the frozen app).

  python voice.py record OUT.wav [LANG]     records the default microphone until the line "stop" arrives on stdin
                                            ("cancel" or EOF = throw the recording away), then transcribes it with
                                            faster-whisper and prints one JSON line: {"ok", "text", "secs", "lang", "path"}
  python voice.py file AUDIO [LANG]         transcribes an existing audio file the same way
  python voice.py devices                   lists microphones

The Whisper model loads while you are still talking, so the text is ready soon after you stop.
"""
import json, os, sys, threading, time, wave

MODELS = ["mobiuslabsgmbh/faster-whisper-large-v3-turbo", "Systran/faster-whisper-small"]   # first one found in the local cache wins
MAX_SECS = 300


def out(d):
    sys.stdout.write(json.dumps(d, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def load_model(box):
    try:
        from faster_whisper import WhisperModel
        last = None
        for name in MODELS:
            try:
                box["model"] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(2, (os.cpu_count() or 4) - 2),
                                            local_files_only=True)
                box["name"] = name
                return
            except Exception as e:   # not in the cache: try the next one
                last = e
        box["error"] = f"مفيش موديل Whisper متحمّل على الجهاز ({last})"
    except Exception as e:
        box["error"] = f"faster-whisper مش متثبت: {e}"


def transcribe(box, audio, lang):
    """audio: float32 mono 16 kHz numpy array, or a file path."""
    if "error" in box:
        return {"ok": False, "error": box["error"]}
    if isinstance(audio, str):          # decode with ffmpeg (16 kHz mono) instead of PyAV
        import subprocess, numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
        if not raw:
            return {"ok": False, "error": "مقدرتش أقرا ملف الصوت."}
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    # "auto" = detect the language (slower); default Arabic. beam 1 keeps a CPU-only machine responsive.
    segs, info = box["model"].transcribe(audio, language=None if lang == "auto" else (lang or "ar"), vad_filter=True, beam_size=1,
                                         condition_on_previous_text=False)
    text = " ".join(s.text.strip() for s in segs).strip()
    if not text:
        return {"ok": False, "error": "ماسمعتش كلام واضح في التسجيل. قرّب من الميكروفون وجرّب تاني."}
    return {"ok": True, "text": text, "lang": info.language, "model": box.get("name", "").split("/")[-1]}


def record(path, lang):
    import numpy as np
    import sounddevice as sd
    box, chunks = {}, []
    th = threading.Thread(target=load_model, args=(box,), daemon=True)
    th.start()
    try:
        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", callback=lambda d, f, t, s: chunks.append(d.copy()))
        stream.start()
    except Exception as e:
        return out({"ok": False, "error": f"مقدرتش أفتح الميكروفون: {e}"})
    out({"event": "recording"})
    cmd = {"v": ""}

    def reader():
        cmd["v"] = sys.stdin.readline().strip()
    rt = threading.Thread(target=reader, daemon=True)
    rt.start()
    rt.join(MAX_SECS)
    stream.stop(); stream.close()
    if cmd["v"] != "stop" and rt.is_alive() is False:
        return out({"ok": False, "cancelled": True})
    if not chunks:
        return out({"ok": False, "error": "الميكروفون ما بعتش صوت. اتأكد إنه متوصّل ومسموح بيه في إعدادات ويندوز."})
    pcm = np.concatenate(chunks)[:, 0]
    secs = len(pcm) / 16000
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(pcm.tobytes())
    if secs < 0.5:
        return out({"ok": False, "error": "التسجيل قصير أوي."})
    peak = int(np.abs(pcm.astype(np.int32)).max())
    if peak < 300:
        return out({"ok": False, "error": "التسجيل طلع صامت. اتأكد من الميكروفون المختار في ويندوز ومن علو الصوت.", "secs": round(secs, 1), "path": path})
    out({"event": "transcribing", "secs": round(secs, 1)})
    th.join()
    t0 = time.time()
    r = transcribe(box, pcm.astype(np.float32) / 32768.0, lang)
    out({**r, "secs": round(secs, 1), "took": round(time.time() - t0, 1), "path": path})


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    a = sys.argv[1:]
    if a[:1] == ["record"] and len(a) >= 2:
        record(a[1], a[2] if len(a) > 2 else "")
    elif a[:1] == ["file"] and len(a) >= 2:
        box = {}
        load_model(box)
        t0 = time.time()
        out({**transcribe(box, a[1], a[2] if len(a) > 2 else ""), "took": round(time.time() - t0, 1), "path": a[1]})
    elif a[:1] == ["devices"]:
        import sounddevice as sd
        d = sd.query_devices()
        out({"default_input": sd.default.device[0], "inputs": [{"i": i, "name": x["name"]} for i, x in enumerate(d) if x["max_input_channels"] > 0]})
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
