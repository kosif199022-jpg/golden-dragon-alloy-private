#!/usr/bin/env python3
"""whisper.py IN [--model large-v3] [--lang ar|auto] [--out DIR] [--name BASE] [--threads N]
                 [--compute int8] [--beam 5] [--no-vad] [--prompt "names, terms"] [--max-chars 42]
faster-whisper on CPU (the sandbox has no GPU). Writes BASE.srt, BASE.vtt, BASE.txt, BASE.words.json.
Video or audio input; audio is extracted to 16 kHz mono first. large-v3 is pre-cached on the sandbox.
Progress goes to $HFC_JOB_DIR (so `hfc job status` shows % and ETA) and to stdout every ~10 s.
"""
import argparse, json, os, subprocess, sys, tempfile, time


def ts(t, sep=","):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)) % 1000:03d}"


def split_long(seg_words, text, start, end, max_chars):
    """Split a long segment into caption lines on word boundaries using word timings."""
    if len(text) <= max_chars or not seg_words:
        return [(start, end, text)]
    out, cur, c0 = [], [], None
    for w in seg_words:
        if c0 is None:
            c0 = w["start"]
        cand = ("".join(x["word"] for x in cur + [w])).strip()
        if cur and len(cand) > max_chars:
            out.append((c0, cur[-1]["end"], "".join(x["word"] for x in cur).strip()))
            cur, c0 = [w], w["start"]
        else:
            cur.append(w)
    if cur:
        out.append((c0, cur[-1]["end"], "".join(x["word"] for x in cur).strip()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp")
    ap.add_argument("--model", default="large-v3", help="tiny|base|small|medium|large-v3|distil-large-v3 or HF id")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--out", default=".")
    ap.add_argument("--name")
    ap.add_argument("--threads", type=int, default=len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 4))
    ap.add_argument("--compute", default="int8")
    ap.add_argument("--beam", type=int, default=5)
    ap.add_argument("--no-vad", action="store_true")
    ap.add_argument("--prompt", default=None, help="initial prompt: names/terms to spell right")
    ap.add_argument("--max-chars", type=int, default=42, help="max characters per caption line in SRT/VTT")
    a = ap.parse_args()
    if not os.path.isfile(a.inp):
        sys.exit(f"whisper: no input {a.inp}")
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, a.name or os.path.splitext(os.path.basename(a.inp))[0])
    jd = os.environ.get("HFC_JOB_DIR")

    t0 = time.time()
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", a.inp,
                    "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                               capture_output=True, text=True).stdout.strip() or 0)
    if jd:
        open(os.path.join(jd, "total_us"), "w").write(str(int(dur * 1e6)))

    # Decode the WAV ourselves: newer PyAV dropped `metadata_errors`, which faster-whisper 1.2.1 still passes
    # (measured on Windows 2026-11-11: TypeError). numpy input skips PyAV entirely on both machines.
    import wave
    import numpy as np
    with wave.open(wav, "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    from faster_whisper import WhisperModel
    tl = time.time()
    model = WhisperModel(a.model, device="cpu", compute_type=a.compute, cpu_threads=a.threads)
    load_s = time.time() - tl
    segs, info = model.transcribe(audio, language=None if a.lang == "auto" else a.lang, beam_size=a.beam,
                                  word_timestamps=True, vad_filter=not a.no_vad, initial_prompt=a.prompt,
                                  condition_on_previous_text=False)
    out, last_print = [], 0
    for s in segs:
        words = [{"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)}
                 for w in (s.words or [])]
        out.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "words": words})
        if jd:
            with open(os.path.join(jd, "progress"), "a") as f:
                f.write(f"out_time_us={int(s.end * 1e6)}\n")
        if time.time() - last_print > 10:
            print(f"whisper: {s.end:.0f}/{dur:.0f}s", flush=True); last_print = time.time()
    os.remove(wav)

    lines = []
    for s in out:
        lines += split_long(s["words"], s["text"], s["start"], s["end"], a.max_chars)
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i, (st, en, tx) in enumerate(lines, 1):
            f.write(f"{i}\n{ts(st)} --> {ts(en)}\n{tx}\n\n")
    with open(base + ".vtt", "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for st, en, tx in lines:
            f.write(f"{ts(st, '.')} --> {ts(en, '.')}\n{tx}\n\n")
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(s["text"] for s in out) + "\n")
    meta = {"model": a.model, "language": info.language, "language_p": round(info.language_probability, 3),
            "audio_s": round(dur, 2), "load_s": round(load_s, 1), "total_s": round(time.time() - t0, 1),
            "threads": a.threads, "compute": a.compute, "segments": out}
    with open(base + ".words.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    nw = sum(len(s["words"]) for s in out)
    rtf = meta["total_s"] / dur if dur else 0
    print(f"whisper: {base}.srt/.vtt/.txt/.words.json lang={info.language}({info.language_probability:.2f}) "
          f"audio={dur:.1f}s words={nw} lines={len(lines)} load={load_s:.1f}s total={meta['total_s']}s rtf={rtf:.2f}")


if __name__ == "__main__":
    main()
