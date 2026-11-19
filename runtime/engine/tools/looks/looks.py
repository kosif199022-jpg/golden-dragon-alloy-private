#!/usr/bin/env python3
"""Looks library (v1990.5, v1990.6): the characters, outfits, expressions, scenes, styles, layouts, models
and (v1990.6) the film methods from every project chat (Mayar films, map film, shadow theatre, cartoon...).

    dragon.py tool looks list [--kind character|wardrobe|singer|expression|scene|style|layout|model|method]
    dragon.py tool looks find "كلامه"          # search names, uses, notes and aliases (Arabic or English)
    dragon.py tool looks remind "كلامه" --out DIR [--top 3]   # picture card(s) to SEND before using a model
    dragon.py tool looks show ID          # card + image path + prompt + example film link
    dragon.py tool looks sheet OUT.jpg [--kind K]   # one contact sheet with ids on the pictures (send it to the owner)
    dragon.py tool looks prompt ID [ID ...] --scene "what happens"   # ready Higgsfield prompt with the couple refs

Offline. Images are small thumbnails under tools/looks/img; every look carries its example film link.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "looks.json"
KINDS = ("character", "wardrobe", "singer", "expression", "scene", "style", "layout", "model", "method")


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def find(data, i):
    for x in data["looks"]:
        if x["id"].lower() == i.lower():
            return x
    return None


def cmd_list(data, kind):
    for x in data["looks"]:
        if kind and x["kind"] != kind:
            continue
        print(f"{x['id']:5} {x['kind']:10} {x['name']}")
    return 0


def cmd_show(data, i):
    x = find(data, i)
    if not x:
        print(f"no look {i!r}; try: looks list")
        return 1
    print(f"{x['id']} · {x['kind']} · {x['name']}")
    for k in ("use", "prompt", "cost", "notes", "example", "aliases"):
        if x.get(k):
            print(f"  {k}: {x[k]}")
    if x.get("image"):
        print(f"  image: {HERE / x['image']}")
    if x["kind"] in ("character", "wardrobe", "singer", "expression", "scene"):
        print(f"  refs: {', '.join(data['refs'])}")
    return 0


_AR = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ـ": None})


def norm(t):
    t = "".join(c for c in str(t) if not ("\u064b" <= c <= "\u065f" or c == "\u0670"))
    return t.translate(_AR).lower()


def search(data, query, kind=None):
    """Rank looks for a free-text request. An exact id wins; then alias/name hits, then use/notes hits."""
    q = norm(query).strip()
    stop = {"زي", "بتاع", "بتاعة", "عايز", "عاوز", "اعمل", "استخدم", "نفس", "على", "في", "من", "the", "like"}
    words = []
    for w in q.replace("،", " ").replace(",", " ").split():
        for pre in ("وال", "بال", "لل", "ال"):
            if w.startswith(pre) and len(w) - len(pre) >= 3:
                w = w[len(pre):]
                break
        if len(w) > 1 and w not in stop:
            words.append(w)
    hits = []
    for x in data["looks"]:
        if kind and x["kind"] != kind:
            continue
        if x["id"].lower() == q:
            return [x]
        strong = norm(" ".join([x["id"], x["name"], " ".join(x.get("aliases", []))]))
        weak = norm(" ".join(str(x.get(k, "")) for k in ("use", "notes", "prompt")))
        score = 0
        for a in x.get("aliases", []):
            if norm(a) in q:
                score += 6
        for w in words:
            if w in strong:
                score += 3
            elif w in weak:
                score += 1
        if score:
            hits.append((score, x))
    hits.sort(key=lambda t: -t[0])
    return [x for _, x in hits]


def cmd_find(data, query, kind):
    res = search(data, query, kind)
    if not res:
        print(f"no look matches {query!r}; send the whole sheet instead: looks sheet OUT.jpg")
        return 1
    for x in res[:10]:
        print(f"{x['id']:5} {x['kind']:10} {x['name']}")
    return 0


def cmd_remind(data, query, out, top):
    """Write a picture card for the best matches so Claude can send it to the owner BEFORE using the look."""
    res = search(data, query)[:top]
    if not res:
        print(f"no look matches {query!r}; send: looks sheet OUT.jpg")
        return 1
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        Image = None
    for x in res:
        src = HERE / x["image"] if x.get("image") else None
        dest = outdir / f"{x['id']}.jpg"
        if src and Image:
            im = Image.open(src).convert("RGB").resize((540, 960))
            d = ImageDraw.Draw(im)
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
            except OSError:
                font = ImageFont.load_default()
            d.rectangle([0, 0, 170, 62], fill=(0, 0, 0))
            d.text((12, 6), x["id"], fill=(255, 214, 80), font=font)
            im.save(dest, quality=88)
        elif src:
            dest.write_bytes(src.read_bytes())
        else:
            dest = None
        print(f"[{x['id']}] {x['name']}")
        print(f"  picture: {dest if dest else '(no picture: model/price card)'}")
        if x.get("use"):
            print(f"  use: {x['use']}")
        if x.get("example"):
            print(f"  example: {x['example']}")
    print()
    print("SEND the picture(s) above to the owner with the id and name, ask:")
    ids = " / ".join(x["id"] for x in res)
    print(f"  «ده النموذج اللي تقصده؟ ({ids}) أستخدمه؟»  then wait for the owner's yes before generating or rendering.")
    return 0


def compose(data, ids, scene):
    parts, used = [], []
    for i in ids:
        x = find(data, i)
        if not x:
            raise SystemExit(f"no look {i!r}")
        used.append(x["id"])
        if x.get("prompt"):
            parts.append(x["prompt"])
    base = find(data, "C01")["prompt"]
    if not parts or parts[0] != base:
        parts.insert(0, base)
    if scene:
        parts.append(scene.strip().rstrip(".") + ".")
    parts.append(data["prompt_tail"])
    text = " ".join(parts).replace('"', "'").replace("\n", " ")
    return {"looks": used, "prompt": text,
            "params": {"model": "gpt_image_2_6", "aspect_ratio": "9:16", "count": 1, "use_unlim": False,
                       "medias": [{"value": r, "role": "image"} for r in data["refs"]], "prompt": text},
            "note": data["modesty"]}


def cmd_sheet(data, out, kind):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow is needed for sheet (pip install pillow)")
        return 1
    items = [x for x in data["looks"] if x.get("image") and (not kind or x["kind"] == kind)]
    if not items:
        print("nothing to draw")
        return 1
    w, h, cols = 240, 427, 6
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for n, x in enumerate(items):
        im = Image.open(HERE / x["image"]).convert("RGB").resize((w, h))
        cx, cy = (n % cols) * w, (n // cols) * h
        sheet.paste(im, (cx, cy))
        d.rectangle([cx, cy, cx + 112, cy + 40], fill=(0, 0, 0))
        d.text((cx + 6, cy + 4), x["id"], fill=(255, 214, 80), font=font)
    sheet.save(out, quality=85)
    print(f"wrote {out}  ({len(items)} looks; ids on the pictures)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="looks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list"); ls.add_argument("--kind", choices=KINDS)
    sh = sub.add_parser("show"); sh.add_argument("id")
    st = sub.add_parser("sheet"); st.add_argument("out"); st.add_argument("--kind", choices=KINDS)
    pr = sub.add_parser("prompt"); pr.add_argument("ids", nargs="+"); pr.add_argument("--scene", default="")
    fd = sub.add_parser("find"); fd.add_argument("query"); fd.add_argument("--kind", choices=KINDS)
    rm = sub.add_parser("remind"); rm.add_argument("query"); rm.add_argument("--out", default="looks_remind")
    rm.add_argument("--top", type=int, default=3)
    a = ap.parse_args(argv)
    data = load()
    if a.cmd == "list":
        return cmd_list(data, a.kind)
    if a.cmd == "show":
        return cmd_show(data, a.id)
    if a.cmd == "sheet":
        return cmd_sheet(data, a.out, a.kind)
    if a.cmd == "find":
        return cmd_find(data, a.query, a.kind)
    if a.cmd == "remind":
        return cmd_remind(data, a.query, a.out, a.top)
    print(json.dumps(compose(data, a.ids, a.scene), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
