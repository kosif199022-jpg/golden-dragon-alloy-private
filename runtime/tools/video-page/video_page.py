#!/usr/bin/env python3
"""Video download page + video library (owner's rule, 2026-11-17).

Every finished video gets its own download page (an Artifact) with:
  - in-page playback of a light copy (<15 MB),
  - «تحميل بأعلى جودة»: the original file byte for byte, split into <=14 MB
    parts that the page joins and saves through the `downloads` capability,
  - «تحميل نسخة خفيفة», an optional direct link, and the ready caption.
Then the video is added to the library page («فيديوهات الكوسف»), one Artifact
whose videos.json lists every page.

  python3 video_page.py build VIDEO.mp4 --id ID --title "..." --date 16/11/2026 \
      --caption-file caption.txt [--direct-url URL] [--hub-url URL] --out DIR
  -> DIR/index.html, light.mp4, poster.jpg, full/p*.mp4, entry.json, publish.json
  python3 video_page.py hub-add DIR/entry.json --page-url URL --hub HUBDIR
  -> HUBDIR/index.html, videos.json, posters/ID.jpg
  python3 video_page.py check DIR      (re-joins the parts and compares MD5)

Publish limits this tool respects: 15 MB per binary file, 64 MB per publish
(publish.json lists the batches), 256 MB per artifact version, so one video
per download page and the library page holds only posters and links.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PART = 14_000_000
BATCH = 56_000_000
FALLBACK_DIRECT = "استخدم الرابط المباشر تحت."
FALLBACK_NONE = "جرّب تاني بعد شوية."


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,codec_name:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    fps = round(int(num) / int(den), 2)
    return {"w": s["width"], "h": s["height"], "fps": fps, "codec": s["codec_name"],
            "dur": float(j["format"]["duration"])}


def build(a):
    src = os.path.abspath(a.video)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.join(out, "full"), exist_ok=True)
    for f in os.listdir(os.path.join(out, "full")):
        os.remove(os.path.join(out, "full", f))
    info = probe(src)
    size = os.path.getsize(src)
    # light copy for playback (and a light download): same size, same audio stream
    light = os.path.join(out, "light.mp4")
    if size <= PART:
        shutil.copyfile(src, light)
    else:
        kbps = int(min(4300, (13_000_000 * 8 / info["dur"]) / 1000 - 330))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:v", "libx264", "-profile:v", "high",
                        "-preset", "slow", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps*1.15)}k",
                        "-bufsize", f"{kbps*2}k", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "copy",
                        "-movflags", "+faststart", light], check=True)
        if os.path.getsize(light) > 15_000_000:
            sys.exit("light copy is over 15 MB; lower the bitrate")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(min(a.poster_at, info["dur"] / 2)), "-i", src,
                    "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4",
                    os.path.join(out, "poster.jpg")], check=True)
    parts = []
    with open(src, "rb") as f:
        i = 0
        while True:
            b = f.read(PART)
            if not b:
                break
            name = f"full/p{i}.mp4"
            with open(os.path.join(out, name), "wb") as g:
                g.write(b)
            parts.append(name)
            i += 1
    caption = open(a.caption_file, encoding="utf8").read().strip() if a.caption_file else (a.caption or "")
    t = open(os.path.join(HERE, "template.html"), encoding="utf8").read()
    if not a.direct_url:
        import re
        t = re.sub(r"<!--DIRECT-->.*?<!--/DIRECT-->\n?", "", t, flags=re.S)
    else:
        t = t.replace("<!--DIRECT-->\n", "").replace("<!--/DIRECT-->\n", "").replace("<!--/DIRECT-->", "")
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    base = a.filename or a.id
    rep = {
        "{{TITLE}}": esc(a.title), "{{DATE}}": esc(a.date), "{{HANDLE}}": esc(a.handle),
        "{{CAPTION}}": esc(caption), "{{DIRECT_URL}}": esc(a.direct_url or ""),
        "{{FULL_MB}}": str(round(size / 1e6)), "{{LIGHT_MB}}": str(round(os.path.getsize(light) / 1e6)),
        "{{PARTS_JSON}}": json.dumps(parts), "{{FULL_SIZE}}": str(size),
        "{{FILENAME_JSON}}": json.dumps(base + ".mp4"), "{{LIGHT_FILENAME_JSON}}": json.dumps(base + "_light.mp4"),
        "{{SPECS}}": f'{info["w"]}×{info["h"]} · {info["fps"]:g} fps · {info["dur"]:.1f} s · {info["codec"].upper()}',
        "{{HUB_URL}}": esc(a.hub_url or "#"),
        "{{FALLBACK}}": FALLBACK_DIRECT if a.direct_url else FALLBACK_NONE,
    }
    for k, v in rep.items():
        t = t.replace(k, v)
    if not a.hub_url:
        import re
        t = re.sub(r'\s*<a class="back"[^>]*>[^<]*</a>', "", t)
    assert "{{" not in t, "unfilled placeholder"
    open(os.path.join(out, "index.html"), "w", encoding="utf8").write(t)
    # publish batches (<= 64 MB each; index.html goes with the last batch)
    files = [("light.mp4", os.path.getsize(light)), ("poster.jpg", os.path.getsize(os.path.join(out, "poster.jpg")))]
    files += [(p, os.path.getsize(os.path.join(out, p))) for p in parts]
    batches, cur, tot = [], [], 0
    for name, sz in files:
        if cur and tot + sz > BATCH:
            batches.append(cur); cur, tot = [], 0
        cur.append(name); tot += sz
    batches.append(cur)
    json.dump({"note": "publish each batch with the Artifact tool (files map published path -> DIR/path); "
                       "first publish declares capabilities {downloads: true} and icon 'video'",
               "batches": batches}, open(os.path.join(out, "publish.json"), "w"), indent=1)
    entry = {"id": a.id, "title": a.title, "date": a.date, "duration": f'{int(info["dur"]//60)}:{int(round(info["dur"]%60)):02d}',
             "direct_url": a.direct_url or "", "md5": md5(src), "size": size,
             "poster_file": os.path.join(out, "poster.jpg"), "added": datetime.datetime.now().isoformat(timespec="seconds")}
    json.dump(entry, open(os.path.join(out, "entry.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    check_dir(out)
    print(f"built {out}: {len(parts)} parts, light {os.path.getsize(light)/1e6:.1f} MB, {len(batches)} publish batch(es)")


def check_dir(out):
    out = os.path.abspath(out)
    e = json.load(open(os.path.join(out, "entry.json"), encoding="utf8"))
    h = hashlib.md5()
    i = 0
    while os.path.exists(os.path.join(out, f"full/p{i}.mp4")):
        sz = os.path.getsize(os.path.join(out, f"full/p{i}.mp4"))
        if sz > 15_000_000:
            sys.exit(f"part {i} over 15 MB")
        h.update(open(os.path.join(out, f"full/p{i}.mp4"), "rb").read())
        i += 1
    ok = h.hexdigest() == e["md5"]
    print(f"check: {i} parts, md5 {'matches' if ok else 'DIFFERS'} ({e['md5']})")
    if not ok:
        sys.exit(1)


def hub_add(a):
    hub = os.path.abspath(a.hub)
    os.makedirs(os.path.join(hub, "posters"), exist_ok=True)
    if not os.path.exists(os.path.join(hub, "index.html")):
        shutil.copyfile(os.path.join(HERE, "hub.html"), os.path.join(hub, "index.html"))
    vj = os.path.join(hub, "videos.json")
    vids = json.load(open(vj, encoding="utf8")) if os.path.exists(vj) else []
    e = json.load(open(a.entry, encoding="utf8"))
    shutil.copyfile(e["poster_file"], os.path.join(hub, "posters", e["id"] + ".jpg"))
    row = {k: e[k] for k in ("id", "title", "date", "duration", "direct_url", "added")}
    row["page_url"] = a.page_url
    row["poster"] = "posters/" + e["id"] + ".jpg"
    vids = [v for v in vids if v["id"] != e["id"]] + [row]
    json.dump(vids, open(vj, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"hub: {len(vids)} video(s); publish {hub}/index.html with files videos.json and {row['poster']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build")
    b.add_argument("video"); b.add_argument("--id", required=True); b.add_argument("--title", required=True)
    b.add_argument("--date", default=""); b.add_argument("--handle", default="@elkosif")
    b.add_argument("--caption"); b.add_argument("--caption-file")
    b.add_argument("--direct-url"); b.add_argument("--hub-url"); b.add_argument("--filename")
    b.add_argument("--poster-at", type=float, default=8.0); b.add_argument("--out", required=True)
    h = sp.add_parser("hub-add")
    h.add_argument("entry"); h.add_argument("--page-url", required=True); h.add_argument("--hub", required=True)
    c = sp.add_parser("check"); c.add_argument("dir")
    a = p.parse_args()
    {"build": build, "hub-add": hub_add, "check": lambda a: check_dir(a.dir)}[a.cmd](a)


if __name__ == "__main__":
    main()
