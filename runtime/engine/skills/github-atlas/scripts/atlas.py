#!/usr/bin/env python3
"""github-atlas: search the top-1000 most-starred GitHub repos (stdlib only).

  atlas.py find "تحميل فيديو" [--cat media-processing] [--windows] [--alive] [--min-value 3] [-n 8] [--json]
  atlas.py show owner/repo
  atlas.py cats
  atlas.py top [--by stars|downloads|value|relevance] [--cat X] [-n 20]
  atlas.py lessons [--grep word]
  atlas.py stats
  atlas.py refresh            # re-pull stars/push dates with gh (needs gh login)
"""
import argparse, json, os, re, shutil, subprocess, sys, unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "atlas.jsonl")

AR_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = AR_DIAC.sub("", s)
    s = re.sub("[إأآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return s


def toks(s):
    out = []
    for t in re.findall(r"[\w\+\#\.]+", norm(s)):
        t = t.strip(".")
        if not t:
            continue
        out.append(t)
        if re.match(r"^[؀-ۿ]+$", t):  # strip common Arabic prefixes
            for p in ("وال", "بال", "لل", "ال", "و", "ب"):
                if t.startswith(p) and len(t) - len(p) >= 3:
                    out.append(t[len(p):])
                    break
    return out


# Egyptian/Arabic -> English bridge (the query is expanded with these)
SYN = {
    "تحميل": "download downloader", "نزل": "download", "حمل": "download", "داونلود": "download",
    "فيديو": "video", "فديو": "video", "مونتاج": "video editing montage", "مونتاتج": "video editing",
    "صوت": "audio speech", "صوره": "image", "صور": "image photo", "تصميم": "design ui",
    "ترجمه": "translation subtitles", "تفريغ": "transcription speech-to-text whisper",
    "كابشن": "subtitles captions", "ذكاء": "ai llm", "شات": "chat llm", "وكيل": "agent",
    "وكلاء": "agents", "برومنت": "prompt prompts", "موقع": "website web", "تطبيق": "app application",
    "موبايل": "mobile android ios", "اندرويد": "android", "قاعده": "database", "بيانات": "data database",
    "سيرفر": "server backend self-hosted", "استضافه": "self-hosted hosting", "امان": "security",
    "هندسه": "reverse engineering", "عكسيه": "reverse engineering", "اختراق": "security pentest",
    "متصفح": "browser", "سكرابنج": "scraping crawler", "كشط": "scraping", "اتمته": "automation workflow",
    "تعلم": "learning tutorial", "كورس": "course tutorial", "كتب": "books", "مقابله": "interview",
    "لعبه": "game engine", "العاب": "games", "ثلاثي": "3d", "رسم": "drawing diagram paint",
    "خط": "font", "خطوط": "fonts", "ملاحظات": "notes markdown", "مستندات": "documents pdf",
    "ضغط": "compression", "تكبير": "upscale super-resolution", "خلفيه": "background removal",
    "تيرمنال": "terminal shell cli", "محرر": "editor", "كود": "code", "برمجه": "programming",
    "شبكه": "network vpn proxy", "بروكسي": "proxy", "جدول": "spreadsheet table",
    "رسوم": "charts visualization", "داشبورد": "dashboard", "بحث": "search", "ويندوز": "windows",
    "نوشن": "notion", "فوتوشوب": "photoshop image editor", "كاب كات": "capcut video editor", "كابكات": "capcut",
    "اكسل": "excel spreadsheet", "يوتيوب": "youtube", "تيك توك": "tiktok", "تيكتوك": "tiktok", "واتساب": "whatsapp",
    "بلندر": "blender 3d", "كروم": "chrome browser", "انستجرام": "instagram", "تيليجرام": "telegram",
    "تفعيل": "activation activator", "بديل": "alternative", "اوفيس": "office", "باوربوينت": "powerpoint slides",
    "عرض": "slides presentation", "ورد": "word docx", "تلفزيون": "tv iptv", "سطح المكتب": "desktop",
    "نموذج": "model llm", "موديل": "model", "محلي": "local offline", "مجاني": "free open-source",
}


# repo -> executable name, to tell Claude what is already installed on this PC
EXE = {
    "yt-dlp/yt-dlp": "yt-dlp", "FFmpeg/FFmpeg": "ffmpeg", "aria2/aria2": "aria2c", "jqlang/jq": "jq",
    "BurntSushi/ripgrep": "rg", "jgm/pandoc": "pandoc", "cli/cli": "gh", "git/git": "git", "curl/curl": "curl.exe",
    "astral-sh/uv": "uv", "astral-sh/ruff": "ruff", "nodejs/node": "node", "python/cpython": "python",
    "tesseract-ocr/tesseract": "tesseract", "upscayl/upscayl": "upscayl-bin", "ollama/ollama": "ollama",
    "openai/whisper": "whisper", "ggml-org/whisper.cpp": "whisper-cli", "sharkdp/fd": "fd", "mpv-player/mpv": "mpv",
    "PowerShell/PowerShell": "pwsh", "microsoft/playwright": "playwright", "NationalSecurityAgency/ghidra": "ghidraRun",
    "skylot/jadx": "jadx", "mitmproxy/mitmproxy": "mitmdump", "rclone/rclone": "rclone", "denoland/deno": "deno",
    "oven-sh/bun": "bun", "pnpm/pnpm": "pnpm", "docker/compose": "docker", "koalaman/shellcheck": "shellcheck",
    "typst/typst": "typst", "duckdb/duckdb": "duckdb", "morluto/rea": "rea", "anthropics/claude-code": "claude",
    "mifi/lossless-cut": "LosslessCut", "danielgatis/rembg": "rembg", "ImageMagick/ImageMagick": "magick",
    "blender/blender": "blender", "ocrmypdf/OCRmyPDF": "ocrmypdf", "junegunn/fzf": "fzf", "casey/just": "just",
}


def installed(r):
    exe = EXE.get(r["repo"])
    return bool(exe and shutil.which(exe))


def load():
    if not os.path.exists(DATA):
        sys.exit(f"missing {DATA}")
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
    for r in rows:
        r["_name"] = toks(re.sub(r"[/\-_]", " ", r["repo"]))
        r["_kw"] = toks(" ".join(r.get("keywords_en", []) + r.get("keywords_ar", [])))
        r["_txt"] = toks(" ".join([r.get("what", ""), r.get("use_when", ""), r.get("topics", ""),
                                   r.get("desc", ""), r.get("category", "")]))
    return rows


def expand(q):
    nq = norm(q)
    extra = []
    for k, v in SYN.items():
        if norm(k) in nq:
            extra += v.split()
    return toks(q), toks(" ".join(extra))


def score(r, qt, xt):
    s = 0.0
    for t in qt:
        if t in r["_name"]:
            s += 6
        if t in r["_kw"]:
            s += 4
        elif len(t) >= 3 and any(t in k for k in r["_kw"]):
            s += 2
        if t in r["_txt"]:
            s += 1.5
    for t in xt:
        if t in r["_kw"]:
            s += 2.5
        if t in r["_txt"]:
            s += 1
        if t in r["_name"]:
            s += 2
    if s == 0:
        return 0
    # specific words (not generic ones like free/open-source/alternative) found in name/what count extra
    generic = {"free", "open", "source", "open-source", "alternative", "tool", "app", "local", "offline", "data"}
    hits = sum(1 for t in set(qt + xt) if t not in generic and len(t) > 2 and (t in r["_name"] or t in r["_kw"]))
    s += 3 * hits * hits
    s *= 1 + 0.08 * (r.get("value_for_claude") or 0) + 0.04 * (r.get("owner_relevance") or 0)
    if r.get("alive") == "archived":
        s *= 0.6
    if r.get("kind") in ("list", "learning") and not any(t in ("awesome", "list", "learning", "course", "tutorial", "تعلم", "كورس") for t in qt + xt):
        s *= 0.65  # a tool beats a list of tools unless the user asked for lists/courses
    s *= 1 + min(r.get("stars") or 0, 300000) / 1.5e6
    if installed(r):
        s *= 1.25  # prefer what already works on this PC
    return s


def fmt_num(n):
    n = n or 0
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k" if n >= 1e3 else str(n)


def line(r, i=None):
    pre = f"{i:>2}. " if i is not None else ""
    flags = []
    if installed(r):
        flags.append("INSTALLED here")
    if r.get("windows_ok") not in (None, "yes", "n/a"):
        flags.append("win:" + str(r["windows_ok"]))
    if r.get("alive") == "archived":
        flags.append("ARCHIVED")
    if r.get("release_downloads"):
        flags.append("dl " + fmt_num(r["release_downloads"]))
    if r.get("policy") == "consent":
        flags.append("CONSENT: " + r.get("policy_note", ""))
    if r.get("policy") == "blocked":
        flags.append("BLOCKED: " + r.get("policy_note", ""))
    if "?" in (r.get("install_windows") or ""):
        flags.append("install unverified")
    f = ("  [" + ", ".join(flags) + "]") if flags else ""
    return (f"{pre}{r['repo']}  ★{fmt_num(r.get('stars'))}  {r.get('category')}  value {r.get('value_for_claude')}{f}\n"
            f"    {r.get('what', '')}\n    use when: {r.get('use_when', '')}\n    install: {r.get('install_windows', '')}")


def filt(rows, a):
    out = rows if getattr(a, "all", False) else [r for r in rows if r.get("policy") != "blocked"]
    if getattr(a, "cat", None):
        out = [r for r in out if r.get("category") == a.cat]
    if getattr(a, "windows", False):
        out = [r for r in out if r.get("windows_ok") in ("yes", "wsl", "docker")]
    if getattr(a, "alive", False):
        out = [r for r in out if r.get("alive") != "archived"]
    if getattr(a, "min_value", None) is not None:
        out = [r for r in out if (r.get("value_for_claude") or 0) >= a.min_value]
    return out


def clean(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("find")
    f.add_argument("query")
    f.add_argument("-n", type=int, default=8)
    f.add_argument("--cat")
    f.add_argument("--windows", action="store_true")
    f.add_argument("--alive", action="store_true")
    f.add_argument("--min-value", type=int)
    f.add_argument("--json", action="store_true")
    f.add_argument("--all", action="store_true", help="include blocked repos (for explaining why not)")
    s = sp.add_parser("show")
    s.add_argument("repo")
    sp.add_parser("cats")
    sp.add_parser("stats")
    t = sp.add_parser("top")
    t.add_argument("--by", default="value", choices=["stars", "downloads", "value", "relevance"])
    t.add_argument("--cat")
    t.add_argument("--windows", action="store_true")
    t.add_argument("--alive", action="store_true")
    t.add_argument("-n", type=int, default=20)
    t.add_argument("--json", action="store_true")
    l = sp.add_parser("lessons")
    l.add_argument("--grep")
    sp.add_parser("refresh")
    sp.add_parser("have", help="list atlas tools already installed on this PC")
    a = ap.parse_args()
    rows = load()

    if a.cmd == "find":
        qt, xt = expand(a.query)
        res = sorted(((score(r, qt, xt), r) for r in filt(rows, a)), key=lambda x: -x[0])
        res = [r for sc, r in res if sc > 0][: a.n]
        if a.json:
            print(json.dumps([clean(r) for r in res], ensure_ascii=False, indent=1))
            return
        if not res:
            print("no match. Try English words, or `cats` / `top --cat ...`")
            return
        for i, r in enumerate(res, 1):
            print(line(r, i))
    elif a.cmd == "show":
        key = a.repo.lower().strip("/").replace("https://github.com/", "")
        hit = [r for r in rows if r["repo"].lower() == key] or [r for r in rows if key in r["repo"].lower()]
        if not hit:
            sys.exit("not in atlas")
        print(json.dumps(clean(hit[0]), ensure_ascii=False, indent=1))
    elif a.cmd == "cats":
        for c, n in Counter(r.get("category") for r in rows).most_common():
            print(f"{n:>4}  {c}")
    elif a.cmd == "top":
        key = {"stars": "stars", "downloads": "release_downloads", "value": "value_for_claude",
               "relevance": "owner_relevance"}[a.by]
        res = sorted(filt(rows, a), key=lambda r: (r.get(key) or 0, r.get("stars") or 0), reverse=True)[: a.n]
        if a.json:
            print(json.dumps([clean(r) for r in res], ensure_ascii=False, indent=1))
            return
        for i, r in enumerate(res, 1):
            print(line(r, i))
    elif a.cmd == "lessons":
        for r in rows:
            les = r.get("lesson") or ""
            if les and (not a.grep or norm(a.grep) in norm(les)):
                print(f"- {les}  ({r['repo']})")
    elif a.cmd == "stats":
        print("repos:", len(rows))
        print("value>=4:", sum((r.get("value_for_claude") or 0) >= 4 for r in rows))
        print("categories:", len(set(r.get("category") for r in rows)))
        print("windows:", dict(Counter(r.get("windows_ok") for r in rows)))
        print("alive:", dict(Counter(r.get("alive") for r in rows)))
        print("kinds:", dict(Counter(r.get("kind") for r in rows)))
    elif a.cmd == "have":
        for r in rows:
            if installed(r):
                print(f"{r['repo']:<35} {EXE[r['repo']]:<14} {r.get('category')}")
    elif a.cmd == "refresh":
        ok = 0
        for r in rows:
            p = subprocess.run(["gh", "api", f"repos/{r['repo']}", "--jq", "[.stargazers_count,.pushed_at,.archived]"],
                               capture_output=True, text=True, encoding="utf-8")
            if p.returncode == 0:
                st, pu, ar = json.loads(p.stdout)
                r["stars"], r["pushed"] = st, pu[:10]
                if ar:
                    r["alive"] = "archived"
                ok += 1
        with open(DATA, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(clean(r), ensure_ascii=False) + "\n")
        print("refreshed", ok, "of", len(rows))


if __name__ == "__main__":
    main()
