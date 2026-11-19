"""Smart cut: frame-accurate trim that re-encodes only the head up to the next keyframe
and stream-copies the rest, then joins them. Fast, and quality stays the same.

usage: python smart_cut.py IN.mp4 START END OUT.mp4
Times are in seconds. The source file is never modified.
"""
import json, os, subprocess, sys, tempfile


def run(cmd):
    subprocess.run(cmd, check=True)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=codec_name,profile,pix_fmt,r_frame_rate,width,height",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


def keyframes(path, start, end):
    # packet flags are fast to read; K marks a keyframe
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", f"{start}%{end}",
                          "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    ks = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and "K" in parts[1] and parts[0] not in ("", "N/A"):
            ks.append(float(parts[0]))
    return sorted(ks)


def main(src, start, end, dst):
    start, end = float(start), float(end)
    info = probe(src)
    enc = {"h264": "libx264", "hevc": "libx265"}.get(info["codec_name"])
    after = [k for k in keyframes(src, start, end) if k >= start + 0.001 and k < end]
    tmp = tempfile.mkdtemp(prefix="smartcut_")
    head, tail, lst = (os.path.join(tmp, n) for n in ("head.mp4", "tail.mp4", "list.txt"))

    if not after or enc is None:
        # no keyframe inside the range, or a codec we do not re-encode: encode the whole range accurately
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", str(end - start),
             "-c:v", enc or "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", info.get("pix_fmt", "yuv420p"),
             "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", dst])
        print(f"encoded whole range ({end - start:.3f}s): {dst}")
        return

    k = after[0]
    num, den = (int(x) for x in info["r_frame_rate"].split("/"))
    fps = num / den
    head_frames = round((k - start) * fps)
    tail_frames = round(end * fps) - round(start * fps) - head_frames
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", str(k - start), "-frames:v", str(head_frames),
         "-c:v", enc, "-crf", "17", "-preset", "slow", "-pix_fmt", info.get("pix_fmt", "yuv420p"),
         "-r", info["r_frame_rate"], "-c:a", "aac", "-b:a", "320k", head])
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(k), "-i", src, "-t", str(end - k), "-frames:v", str(tail_frames),
         "-c", "copy", "-avoid_negative_ts", "make_zero", tail])
    with open(lst, "w", encoding="utf-8") as f:
        f.write(f"file '{head}'\nfile '{tail}'\n")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
         "-movflags", "+faststart", dst])
    print(f"smart cut: encoded {k - start:.3f}s, copied {end - k:.3f}s -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
