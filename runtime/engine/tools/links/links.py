#!/usr/bin/env python3
"""links - registry of the links the owner used with Black Dragon (offline, no network).

    python scripts/dragon.py tool links stats [--json]
    python scripts/dragon.py tool links find TEXT [--limit N] [--json]     # url / domain / category / note
    python scripts/dragon.py tool links list --category video-source [--limit 20] [--json]
    python scripts/dragon.py tool links route URL [--json]                 # which dragon tool handles it + the command
    python scripts/dragon.py tool links add URL --note "text" [--json]     # user-local file, never the skill

Data: app/data/links.json (read only, shipped, already scrubbed). User additions go to
%LOCALAPPDATA%\\BlackDragon\\links_user.json (or ~/.local/share/BlackDragon when LOCALAPPDATA is unset).
URLs that carry secrets (token, key, sig, X-Amz-*, session, password...) or an e-mail are refused.
This tool never opens a URL.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve()
SKILL = HERE.parents[2]
DATA = SKILL / "app" / "data" / "links.json"
SCHEMA = "black-dragon.links.v1"

SENS_Q = re.compile(r"token|key|sig|signature|x-amz|access_token|auth|password|passwd|session|secret|credential|jwt|bearer|cookie", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PRIV = re.compile(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.0\.0\.0|169\.254\.)", re.I)
CDN = re.compile(r"googlevideo|fbcdn|cdninstagram|tiktokcdn|amazonaws|blob\.core", re.I)

# (category, regex on host, handler id, command template). First match wins. {u} = the url.
FETCH = 'python scripts/dragon.py tool fetch "{u}" --dir out/job'
RULES = [
    ("claude-artifact", r"(^|\.)claude\.ai$", None, None),  # path-checked below
    ("video-source", r"(^|\.)(youtube\.com|youtu\.be|tiktok\.com|instagram\.com|facebook\.com|fb\.watch|fb\.com|x\.com|twitter\.com|t\.co|vimeo\.com|dailymotion\.com|twitch\.tv|reddit\.com|snapchat\.com)$", "fetch", FETCH),
    ("music", r"(^|\.)(soundcloud\.com|spotify\.com|music\.apple\.com|bandcamp\.com|freemusicarchive\.org|incompetech\.com|musicbed\.com|epidemicsound\.com|artlist\.io|anghami\.com|audionautix\.com|jamendo\.com)$", "fetch", FETCH + " --audio"),
    ("ai-service", r"(^|\.)(higgsfield\.ai|kling\.ai|klingai\.com|suno\.(com|ai)|elevenlabs\.io|runway(ml)?\.(com|ai)|lumalabs\.ai|pika\.art|ideogram\.ai|leonardo\.ai|krea\.ai|midjourney\.com|openai\.com|chatgpt\.com|creatify\.ai|heygen\.com|hailuoai\.com|minimax\.io|veo\.google|gemini\.google\.com|aistudio\.google\.com|replicate\.com|huggingface\.co|stability\.ai|pixverse\.ai|vidu\.com|capcut\.com|d-id\.com|synthesia\.io|opus\.pro|descript\.com|invideo\.io)$", None, None),
    ("stock-media", r"(^|\.)(pexels\.com|pixabay\.com|mixkit\.co|videvo\.net|storyblocks\.com|coverr\.co|videezy\.com|shutterstock\.com|pond5\.com|freepik\.com|vecteezy\.com|stock\.adobe\.com|istockphoto\.com|gettyimages\.com|123rf\.com|elements\.envato\.com|motionarray\.com|unsplash\.com|polyhaven\.com|commons\.wikimedia\.org|upload\.wikimedia\.org|archive\.org|loc\.gov|flickr\.com|metmuseum\.org|nasa\.gov|esa\.int|media\.un\.org|europeana\.eu|artgrid\.io|giphy\.com|arabsstock\.com|everypixel\.com|designcuts\.com|ambientcg\.com|openverse\.org|rijksmuseum\.nl|artic\.edu|hosiho\.com|motionelements\.com|dissolve\.com|envato\.com|depositphotos\.com|dreamstime\.com)$", "hunter", 'python scripts/dragon.py tool hunter hunt "<keywords>" --type video'),
    ("font", r"(^|\.)(fonts\.google\.com|fonts\.gstatic\.com|fonts\.googleapis\.com|dafont\.com|fontsquirrel\.com|fontspace\.com|fontsarena\.com|arabicfonts\.net|1001fonts\.com)$", "fonts", "python scripts/dragon.py tool fonts doctor"),
    ("docs", r"(^|\.)(code\.claude\.com|platform\.claude\.com|docs\.claude\.com|docs\.anthropic\.com|learn\.microsoft\.com|docs\.python\.org|pypi\.org|npmjs\.com|developer\.mozilla\.org|ghidradocs\.com|hex-rays\.com|ffmpeg\.org|docs\.blender\.org|download\.blender\.org|blender\.org|yt-dlp\.org|stackoverflow\.com|readthedocs\.io|developers\.[a-z.]+|docs\.[a-z0-9.-]+)$", "fusion", 'python scripts/dragon.py tool fusion find "<topic>"'),
]
GH_HOSTS = ("github.com", "www.github.com")
NONREPO = {"search", "topics", "marketplace", "settings", "orgs", "sponsors", "features", "pricing", "login", "explore", "notifications", "pulls", "issues", "apps", "collections", "about", "enterprise"}

HANDLER_NOTES = {  # handler id -> (what, covered)
    "fetch": ("tool fetch (yt-dlp) - video/audio pages", True),
    "tiktok-post": ("tool tiktok-post - TikTok photo posts", True),
    "hunter": ("tool hunter / tool stock - stock footage, photos, archives", True),
    "repo": ("tool repo - repo link and fusion references", True),
    "fonts": ("tool fonts - OFL fonts", True),
    "fusion": ("tool fusion find - offline docs / capability references", True),
    "hf": ("tool hf - Higgsfield free sandbox recipe (approval before credits)", True),
    "visual-forge": ("tool visual-forge - prompt builder for ChatGPT Images / Kling", True),
    "artifact": ("Artifact tool (outside dragon) - read/update a published page", True),
    "none": ("no Black Dragon tool - open by hand or use WebFetch", False),
}


def domain_of(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def secret_reason(url: str) -> str | None:
    """Why a URL must not be stored/kept, else None. Offline, regex only."""
    try:
        p = urlsplit(url)
    except ValueError:
        return "malformed"
    if p.scheme not in ("http", "https"):
        return "scheme (only http/https)"
    host = (p.hostname or "").lower()
    if not host:
        return "no host"
    if PRIV.match(host) or host.endswith(".local"):
        return "local/private address"
    if p.username or p.password:
        return "credentials in the URL"
    if EMAIL.search(url):
        return "e-mail address"
    if p.query and (SENS_Q.search(p.query) or CDN.search(host)):
        return "query string with a secret/signature"
    if re.search(r"(?i)(token|secret|password|api[_-]?key)=", url) or "X-Amz-" in url:
        return "secret parameter"
    for s in p.path.split("/"):
        if len(s) >= 40 and re.fullmatch(r"[A-Za-z0-9_\-+=]{40,}", s) and "claude.ai" not in host and "github.com" not in host:
            return "long token-like path segment"
    return None


def classify(url: str) -> dict:
    """Return {category, domain, handler, cmd}. Pure, offline."""
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    dom = domain_of(url)
    path = p.path
    if host in GH_HOSTS:
        seg = [s for s in path.split("/") if s]
        if len(seg) >= 2 and seg[0].lower() not in NONREPO:
            return _r("github-repo", dom, "repo", "python scripts/dragon.py tool repo status")
        return _r("reference", dom, "none", None)
    if host in ("api.github.com", "raw.githubusercontent.com", "gist.github.com", "codeload.github.com", "objects.githubusercontent.com", "img.shields.io"):
        return _r("reference", dom, "none", None)
    if host.endswith("tiktok.com") and "/photo/" in path:
        return _r("video-source", dom, "tiktok-post", f'python scripts/dragon.py tool tiktok-post "{url}"')
    for cat, rx, h, cmd in RULES:
        if re.search(rx, host):
            if cat == "claude-artifact":
                if path.startswith(("/artifact/", "/code/artifact/", "/public/artifacts/")):
                    return _r(cat, dom, "artifact", f"Artifact tool: action=read url={url}")
                return _r("other", dom, "none", None)
            if cat == "ai-service":
                if host.endswith("higgsfield.ai"):
                    return _r(cat, dom, "hf", "python scripts/dragon.py tool hf guide")
                if re.search(r"kling|openai|chatgpt", host):
                    return _r(cat, dom, "visual-forge", 'python scripts/dragon.py tool visual-forge plan "<brief>"')
                return _r(cat, dom, "none", None)
            if cat == "video-source" and host.endswith("youtube.com") and not re.search(r"^/(watch|shorts|live|embed)|^/@|^/playlist|^/channel", path):
                return _r("reference", dom, "none", None)
            if cat == "video-source" and host in ("x.com", "twitter.com") and "/status/" not in path:
                return _r("reference", dom, "none", None)
            if cat == "video-source" and host.endswith("instagram.com") and not re.search(r"^/(reel|reels|p|tv|stories)/", path):
                return _r("reference", dom, "none", None)
            return _r(cat, dom, h, cmd.format(u=url) if cmd and "{u}" in cmd else cmd)
    if host.endswith("pixabay.com") and "/music" in path:
        return _r("music", dom, "fetch", FETCH.format(u=url) + " --audio")
    if re.search(r"stock|footage|pics|photo|image|clip|vector|pixel|wallpaper|texture|freepik|picture|gallery|b-?roll|drone|noirlab|usgs\.gov|\.nasa\.|hubblesite|pxhere|burst\.shopify|picjumbo|nappy|cosmos\.so|criticalpast|airvuz|skypixel|filmsupply", host):
        return _r("stock-media", dom, "hunter", 'python scripts/dragon.py tool hunter hunt "<keywords>" --type video')
    if re.search(r"font|arfonts|typeface", host):
        return _r("font", dom, "fonts", "python scripts/dragon.py tool fonts doctor")
    if re.search(r"wikipedia\.org|news|akhbar|bbc\.|cnn\.|aljazeera|youm7|masrawy|almasryalyoum|medium\.com|substack|blog|wikihow|alternativeto|oreilly|who\.int|apple\.com|anthropic\.com", host):
        return _r("reference", dom, "none", None)
    return _r("other", dom, "none", None)


def _r(cat, dom, handler, cmd):
    return {"category": cat, "domain": dom, "handler": handler, "cmd": cmd}


def load_registry(path: Path | None = None) -> dict:
    try:
        return json.loads((path or DATA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": SCHEMA, "generated": None, "counts": {}, "links": []}


def user_file() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "BlackDragon" if base else Path.home() / ".local" / "share" / "BlackDragon"
    return root / "links_user.json"


def load_user() -> list:
    try:
        d = json.loads(user_file().read_text(encoding="utf-8"))
        return d.get("links", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def all_links() -> list:
    out = list(load_registry().get("links", []))
    for u in load_user():
        out.append({"url": u["url"], "domain": u.get("domain") or domain_of(u["url"]), "category": u.get("category", "other"),
                    "handler": u.get("handler", "none"), "first_seen": u.get("added", ""), "mentions": 1, "roles": ["user"], "note": u.get("note", "")})
    return out


def _emit(obj, as_json: bool, text: str):
    print(json.dumps(obj, ensure_ascii=False, indent=1) if as_json else text)


def cmd_stats(a) -> int:
    ls = all_links()
    cats, doms, roles = {}, {}, {}
    for l in ls:
        cats[l["category"]] = cats.get(l["category"], 0) + 1
        doms[l["domain"]] = doms.get(l["domain"], 0) + 1
        for r in l.get("roles", []):
            roles[r] = roles.get(r, 0) + 1
    top = sorted(doms.items(), key=lambda x: -x[1])[:15]
    obj = {"total": len(ls), "user_added": len(load_user()), "categories": dict(sorted(cats.items(), key=lambda x: -x[1])), "roles": roles,
           "top_domains": top, "generated": load_registry().get("generated")}
    txt = [f"links: {len(ls)} (user-added: {len(load_user())})"]
    txt += [f"  {c:16s} {n}" for c, n in obj["categories"].items()]
    txt.append("top domains: " + ", ".join(f"{d}={n}" for d, n in top))
    _emit(obj, a.json, "\n".join(txt))
    return 0


def _show(l) -> str:
    n = f" | {l['note']}" if l.get("note") else ""
    return f"[{l['category']}] {l['url']}  x{l.get('mentions', 1)} ({'/'.join(l.get('roles', []))}) -> {l.get('handler')}{n}"


def cmd_find(a) -> int:
    q = a.text.lower()
    hits = [l for l in all_links() if q in l["url"].lower() or q in l["domain"].lower() or q in l["category"].lower() or q in (l.get("note") or "").lower()]
    hits.sort(key=lambda l: (-("user" in l.get("roles", [])), -l.get("mentions", 1)))
    _emit({"query": a.text, "matches": len(hits), "links": hits[: a.limit]}, a.json,
          f"{len(hits)} match(es)\n" + "\n".join(_show(l) for l in hits[: a.limit]))
    return 0


def cmd_list(a) -> int:
    ls = [l for l in all_links() if not a.category or l["category"] == a.category]
    ls.sort(key=lambda l: (-("user" in l.get("roles", [])), -l.get("mentions", 1)))
    _emit({"category": a.category, "total": len(ls), "links": ls[: a.limit]}, a.json,
          f"{len(ls)} link(s)\n" + "\n".join(_show(l) for l in ls[: a.limit]))
    return 0


def cmd_route(a) -> int:
    why = secret_reason(a.url)
    if why:
        _emit({"url": None, "refused": why}, a.json, f"refused: {why}")
        return 2
    c = classify(a.url)
    what, covered = HANDLER_NOTES.get(c["handler"], HANDLER_NOTES["none"])
    obj = dict(c, url=a.url, covered=covered, tool=what)
    txt = f"{c['category']} | {c['domain']}\nhandler: {what}\n" + (f"command: {c['cmd']}" if c["cmd"] else "command: (none - not covered by a Black Dragon tool)")
    _emit(obj, a.json, txt)
    return 0


def cmd_add(a) -> int:
    why = secret_reason(a.url)
    if why:
        _emit({"added": False, "refused": why}, a.json, f"refused: {why} - nothing was saved")
        return 2
    c = classify(a.url)
    f = user_file()
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {"schema": SCHEMA, "links": []}
    from datetime import date
    rec = {"url": a.url, "domain": c["domain"], "category": c["category"], "handler": c["handler"], "note": a.note or "", "added": date.today().isoformat()}
    d["links"] = [x for x in d.get("links", []) if x.get("url") != a.url] + [rec]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    _emit({"added": True, "file": str(f), "record": rec}, a.json, f"saved to {f}\n[{c['category']}] {a.url} -> {c['handler']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="links", description="Offline registry of the links used with Black Dragon: stats, find, list, route, add.")
    sub = ap.add_subparsers(dest="cmd")
    for name, fn, hlp in (("stats", cmd_stats, "counts by category / domain"), ("find", cmd_find, "search url, domain, category, note"),
                          ("list", cmd_list, "list links, optionally by category"), ("route", cmd_route, "which dragon tool handles a URL (offline)"),
                          ("add", cmd_add, "save a link + note to the user-local file")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--json", action="store_true", help="JSON output")
        if name == "find":
            s.add_argument("text"); s.add_argument("--limit", type=int, default=20)
        if name == "list":
            s.add_argument("--category", default=None); s.add_argument("--limit", type=int, default=20)
        if name in ("route", "add"):
            s.add_argument("url")
        if name == "add":
            s.add_argument("--note", default="")
        s.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
