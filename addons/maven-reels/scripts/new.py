#!/usr/bin/env python3
"""Maven Reels: start a new reel folder. (c) 2026 Maven.
usage: python new.py <folder>
Copies templates/reel.html into <folder> with the kit linked, so the folder can live anywhere."""
import os
import pathlib
import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)
here = pathlib.Path(__file__).resolve().parent.parent
dest = pathlib.Path(sys.argv[1]).resolve()
dest.mkdir(parents=True, exist_ok=True)
page = dest / "reel.html"
if page.exists():
    sys.exit(f"{page} already exists")
html = (here / "templates" / "reel.html").read_text(encoding="utf-8")
html = html.replace("KIT_URL", (here / "kit" / "reel.js").as_uri())
page.write_text(html, encoding="utf-8")
print(f"made {page}\nrender a sheet: node {here / 'scripts' / 'render.mjs'} {page} {dest / 'sheet.jpg'} --sheet")
