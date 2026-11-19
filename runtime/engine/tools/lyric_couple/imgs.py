#!/usr/bin/env python3
"""Download Higgsfield results into a film's img folder, 1080 wide, brighten dark ones, add a depth map, and a sheet.

    python imgs.py JOB/film/img name1=hf_2026..._<job-id> name2=... [--cdn URL_PREFIX]

Each NAME=STEM fetches <cdn><STEM>.png. Images with mean luma < 70 get a gentle gamma lift (never dark openings).
Depth maps (<name>_d.png) need rembg (u2netp); without it they are skipped. Writes JOB/sheet.jpg to look at.
"""
import argparse
import os
import subprocess
from pathlib import Path

CDN = "https://d8j0ntlcm91z4.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("items", nargs="+"); ap.add_argument("--cdn", default=CDN)
    a = ap.parse_args()
    from PIL import Image, ImageFilter, ImageStat
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        from rembg import new_session, remove
        sess = new_session("u2netp")
    except Exception:  # noqa: BLE001
        sess = None
    names = []
    for it in a.items:
        n, stem = it.split("=", 1)
        tmp = d / "t.png"
        subprocess.run(["curl", "-sS", "-o", str(tmp), a.cdn + stem + ".png"], check=True)
        im = Image.open(tmp).convert("RGB")
        im = im.resize((1080, round(im.height * 1080 / im.width)), Image.LANCZOS)
        y = ImageStat.Stat(im.convert("L")).mean[0]
        if y < 70:
            im = im.point(lambda v: round(255 * (v / 255) ** (1 / 1.12)))
        p = d / f"{n}.jpg"; im.save(p, quality=92); os.remove(tmp); names.append(p)
        if sess is not None:
            m = remove(im, session=sess, only_mask=True).resize((540, 960)).filter(ImageFilter.GaussianBlur(9))
            al = np.asarray(m, dtype=np.float32) / 255
            yy = np.linspace(0, 1, 960)[:, None] ** 1.5
            Image.fromarray((np.clip(.72 * al + .28 * yy, 0, 1) * 255).astype("uint8")).save(d / f"{n}_d.png")
        print(n, round(y, 1))
    thumbs = [Image.open(p).resize((320, 572)) for p in names]
    sheet = Image.new("RGB", (320 * len(thumbs), 572))
    for k, t in enumerate(thumbs):
        sheet.paste(t, (320 * k, 0))
    sheet.save(d.parent.parent / "sheet.jpg", quality=85)


if __name__ == "__main__":
    main()
