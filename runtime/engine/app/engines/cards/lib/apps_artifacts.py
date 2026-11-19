"""Helpers of power_programs/apps_artifacts.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from bs4 import BeautifulSoup
from pathlib import Path
import re


def _w(work: Path, name: str, text: str) -> Path:
    p = work / name
    p.write_text(text, encoding="utf-8")
    return p


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


ALLOWED_CDN = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net/npm/", "unpkg.com", "cdn.tailwindcss.com", "code.jquery.com")


def artifact_contract(html: str, size_limit=16 * 1024 * 1024) -> list:
    """Return the list of contract violations of one page (empty = publishable)."""
    soup = BeautifulSoup(html, "html.parser")
    bad = []
    title = (soup.title.string or "").strip() if soup.title else ""
    if not 2 <= len(title.split()) <= 4:
        bad.append(f"title words {len(title.split())}")
    css = " ".join(s.get_text() for s in soup.find_all("style"))
    if ":root" not in css:
        bad.append("no :root tokens")
    if ':root:not([data-theme="light"])' not in css.replace("'", '"') or ':root[data-theme="dark"]' not in css.replace("'", '"'):
        bad.append("dark override not guarded")
    if not re.search(r"body\s*{[^}]*background", css):
        bad.append("no body background")
    for s in soup.find_all("script", src=True):
        src = s["src"]
        if not any(h in src for h in ALLOWED_CDN):
            bad.append(f"script host {src}")
        elif not re.search(r"@\d+\.\d+\.\d+", src) and not re.search(r"/\d+\.\d+\.\d+/", src):
            bad.append(f"inexact version {src}")
    if len(html.encode()) > size_limit:
        bad.append("over 16 MB")
    return bad


def storage_choice(item: dict) -> str:
    return "db" if item.get("shared") or item.get("must_persist") else "localStorage"


def unguarded_localstorage(js: str) -> int:
    """Count localStorage uses that are not inside a try { } block."""
    count, depth_try = 0, []
    tokens = re.finditer(r"try\s*{|{|}|localStorage", js)
    for m in tokens:
        t = m.group(0)
        if t.startswith("try"):
            depth_try.append(True)
        elif t == "{":
            depth_try.append(False)
        elif t == "}":
            if depth_try:
                depth_try.pop()
        elif not any(depth_try):
            count += 1
    return count


def design_smells(html: str) -> list:
    css = html.lower()
    out = []
    grads = re.findall(r"linear-gradient\(([^)]*)\)", css)
    purple = ("#7c3aed", "#8b5cf6", "purple", "#a855f7", "#6d28d9")
    blue = ("#3b82f6", "#2563eb", "blue", "#1d4ed8", "#60a5fa")
    if any(any(p in g for p in purple) and any(b in g for b in blue) for g in grads):
        out.append("purple-to-blue gradient")
    if "blob" in css:
        out.append("decorative blob")
    soup = BeautifulSoup(html, "html.parser")
    if any(c.find_parent(class_="card") for c in soup.find_all(class_="card")):
        out.append("card inside card")
    hues = set()
    flat = re.sub(r"linear-gradient\([^)]*\)", "", css)
    for h in re.findall(r"#([0-9a-f]{6})\b", flat):
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        mx, mn = max(r, g, b), min(r, g, b)
        if mx - mn < 30:
            continue
        if mx == r:
            hue = (60 * ((g - b) / (mx - mn))) % 360
        elif mx == g:
            hue = 60 * ((b - r) / (mx - mn)) + 120
        else:
            hue = 60 * ((r - g) / (mx - mn)) + 240
        hues.add(int(hue // 30))
    if len(hues) <= 1:
        out.append("one-hue palette")
    hero = soup.find("h1")
    if hero and re.search(r"(unlock|supercharge|revolutioni[sz]e|next[- ]level|the future of)", hero.text.lower()):
        out.append("vague hero copy")
    return out


STATES = ("loading", "empty", "error", "partial", "success", "permission")


def state_matrix_missing(matrix: dict) -> list:
    return [s for s in STATES if not all(matrix.get(s, {}).get(k) for k in ("trigger", "feedback", "next"))]


def polish_lint(css: str) -> list:
    out = []
    if re.search(r"transition\s*:\s*all", css):
        out.append("transition: all")
    for prop in re.findall(r"transition\s*:\s*([^;}]*)", css):
        for part in prop.split(","):
            name = part.strip().split()[0] if part.strip() else ""
            if name not in ("transform", "opacity", "all", "none", ""):
                out.append(f"animates {name}")
    m = re.search(r"\.outer{[^}]*border-radius:(\d+)px[^}]*padding:(\d+)px", css)
    n = re.search(r"\.inner{[^}]*border-radius:(\d+)px", css)
    if m and n and int(m.group(1)) != int(n.group(1)) + int(m.group(2)):
        out.append(f"radius {m.group(1)} != {n.group(1)}+{m.group(2)}")
    if "prefers-reduced-motion" not in css:
        out.append("no reduced-motion")
    return out


def preview(cfg: dict) -> str:
    cols = "1fr" if cfg["layout"] == "stack" else ("1fr 1fr" if cfg["layout"] == "split" else "repeat(3,1fr)")
    return "\n".join([
        "<!doctype html>", "<html><head><style>",
        f"body{{font-family:{cfg['font']};background:{cfg['bg']};color:{cfg['ink']}}}",
        f".g{{display:grid;grid-template-columns:{cols}}}", "</style></head><body>",
        f"<h1>{cfg['title']}</h1>", '<div class="g"><div>a</div><div>b</div><div>c</div></div>', "</body></html>"])


def previews_distinct(cfgs: list, pages: list) -> list:
    bad = []
    for i, p in enumerate(pages):
        if p.count("\n") + 1 >= 100:
            bad.append(f"preview {i} too long")
    for axis in ("layout", "font", "bg"):
        vals = [c[axis] for c in cfgs]
        if len(set(vals)) != len(vals):
            bad.append(f"same {axis}")
    return bad


RUBRIC = {"design": 0.3, "originality": 0.2, "craft": 0.3, "function": 0.2}


def anchor(score: float) -> str:
    return "generic" if score < 4 else "competent" if score < 7 else "distinctive" if score < 9 else "professional"


def rubric_score(s: dict) -> float:
    if set(s) != set(RUBRIC):
        raise ValueError("criteria mismatch")
    return round(sum(RUBRIC[k] * s[k] for k in RUBRIC), 2)


def finish_gate(page: dict) -> dict:
    res = {"contrast": all(contrast(fg, bg) >= 4.5 for fg, bg in page["text_pairs"]),
           "touch": all(min(w, h) >= 44 for w, h in page["targets"]),
           "reduced_motion": bool(re.search(r"prefers-reduced-motion:\s*reduce\)\s*{[^}]*transform:\s*none", page["css"])),
           "focus_order": page["tab_order"] == sorted(page["tab_order"])}
    res["not_checked"] = ["390x844 render", "1440x900 render"]
    return res


def second_peak(h: float, e: float) -> float:
    """Ball dropped from h with restitution e: peak after the 2nd bounce = h * e**4 (height scales by e**2 per bounce)."""
    return h * e ** 4


def challenge(target: float, tol: float, lo=0.5, hi=3.0, e=0.8, step=0.01) -> dict:
    best = None
    n = int(round((hi - lo) / step))
    for i in range(n + 1):
        h = lo + i * step
        v = second_peak(h, e)
        if best is None or abs(v - target) < abs(best[1] - target):
            best = (h, v)
    met = abs(best[1] - target) <= tol
    return {"met": met, "value": round(best[1], 4), "setting": round(best[0], 2), "target": target,
            "tolerance": tol, "possible": met}


def build_prefs_page() -> str:
    return ('<!doctype html><html><head><style>.loader{position:fixed;inset:0;font-family:"Cairo"}'
            '@media (prefers-reduced-motion: reduce){*{animation:none!important}}body.still *{animation:none!important}'
            'body.projector{font-size:125%;--ink:#000}.sr{position:absolute;left:-9999px}.sr:focus{left:8px}</style></head>'
            '<body><a class="sr" href="#text">تخطَّ إلى النص</a><div class="loader">...</div>'
            '<div id="nogl" hidden><a href="#text">النسخة النصية</a></div><noscript><a href="#text">النسخة النصية</a></noscript>'
            '<script>try{if(localStorage.getItem("still")==="1")document.body.classList.add("still")}catch(e){}'
            'function toggleStill(){document.body.classList.toggle("still");try{localStorage.setItem("still",'
            'document.body.classList.contains("still")?"1":"0")}catch(e){}}</script><main id="text"></main></body></html>')


def prefs_audit(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    js = " ".join(s.get_text() for s in soup.find_all("script"))
    css = " ".join(s.get_text() for s in soup.find_all("style"))
    return {"reduced_motion": "prefers-reduced-motion" in css, "still_class": "body.still" in css,
            "storage_guarded": "localStorage" in js and unguarded_localstorage(js) == 0,
            "projector": "body.projector" in css, "nogl": soup.find(id="nogl") is not None,
            "noscript": soup.find("noscript") is not None,
            "skip_link": bool(soup.select_one("a.sr")) and ".sr:focus" in css,
            "inline_loader": ".loader" in css}
