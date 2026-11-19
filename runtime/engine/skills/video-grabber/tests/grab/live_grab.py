"""Live end-to-end checks for grab.py (real network). Usage:
    python tests/grab/live_grab.py [OUT_DIR]
Each case runs grab.py --json and checks the ffprobe facts in the summary line.
"""
import json
import subprocess
import sys
from pathlib import Path

GRAB = Path(__file__).resolve().parents[2] / "scripts" / "grab.py"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "video-grabber-tests"

CASES = [
    ("youtube", ["https://www.youtube.com/watch?v=jNQXAC9IVRw", "--no-browser"], lambda f: f["height"] == 240 and f["has_audio"]),
    ("youtube-compat", ["https://www.youtube.com/watch?v=jNQXAC9IVRw", "--compat", "--no-browser"],
     lambda f: f["vcodec"] == "h264" and f["acodec"] == "aac"),
    ("direct-mp4", ["https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4"], lambda f: f["height"] == 480),
    ("hls-section", ["https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8", "--section", "00:00:30-00:00:45", "--no-browser"],
     lambda f: 14 <= f["duration"] <= 17 and f["height"] == 1080),
    ("mp3", ["https://www.youtube.com/watch?v=jNQXAC9IVRw", "--audio-only", "mp3", "--no-browser"],
     lambda f: f["acodec"] == "mp3" and not f["has_video"]),
    ("sniff", ["https://www.w3schools.com/html/html5_video.asp", "--sniff"], lambda f: f["has_video"] and f["has_audio"]),
]


def main():
    ok_all = True
    for name, extra, check in CASES:
        d = OUT / name
        p = subprocess.run([sys.executable, str(GRAB), *extra, "-o", str(d), "--json"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            s = json.loads(p.stdout.strip().splitlines()[-1])
            r = s["results"][0]
            good = r["ok"] and all(check(f) for f in r["files"])
            facts = [(Path(f["path"]).name, f.get("width"), f.get("height"), f.get("vcodec"), f.get("acodec"),
                      f.get("duration")) for f in r["files"]]
            print(f"{'PASS' if good else 'FAIL'} {name}: {r.get('method') or r.get('status')} {facts}")
        except Exception as e:
            good = False
            print(f"FAIL {name}: {e}\n{p.stderr[-800:]}")
        ok_all &= good
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
