#!/usr/bin/env python3
"""insta-reader: يقرا إنستجرام ويحمّل منه بـ instaloader (MIT). الفيديو من أي موقع تاني: video-grabber (yt-dlp).

  doctor                                 instaloader متثبت؟ ولو لأ يقولك تثبّته إزاي
  profile USER [--posts 12] [--json]     بيانات الحساب (المتابعين، البايو، عدد البوستات) + آخر N بوست (لايكات، كومنتات، مشاهدات، الكابشن)
  post URL_OR_CODE [--out DIR] [--no-media] [--comments N]   بوست/ريل واحد: كل الصور والفيديوهات + caption.txt + meta.json
  download USER --out DIR [--max 12] [--since 2026-01-01] [--reels-only]   تحميل بوستات حساب
  top USER [--posts 50] [--by likes|comments|views] [--n 10]   أعلى البوستات أداءً (لدراسة الترند)
  login USER                             (على جهازك بس) تسجيل دخول تفاعلي بحسابك، وinstaloader بيحفظ السيشن بتاعه. التنين مابيشوفش الباسورد
  selftest

حدود: الحسابات العامة من غير دخول. الخاص والستوريز محتاجين --session USER (حسابك إنت، وبس اللي إنت متابعه).
إنستجرام بيحظر لو الطلبات كتير: الافتراضي 12 بوست، وفيه انتظار بين الطلبات. ماتستخدمهوش لجمع بيانات ناس بالجملة.
"""
import argparse, datetime, json, os, re, subprocess, sys, time
from pathlib import Path

CODE_RE = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,})")


def shortcode(s):
    m = CODE_RE.search(s)
    if m:
        return m.group(1)
    s = s.strip().strip("/")
    if re.fullmatch(r"[A-Za-z0-9_-]{5,}", s):
        return s
    raise ValueError(f"مش لينك بوست أو ريل إنستجرام: {s}")


def username(s):
    s = s.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)/?", s)
    u = m.group(1) if m else s.lstrip("@")
    if u in ("p", "reel", "reels", "tv", "stories", "explore") or not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", u):
        raise ValueError(f"مش اسم حساب: {s}")
    return u


def need():
    try:
        import instaloader
        return instaloader
    except ImportError:
        sys.exit("instaloader مش متثبت. ثبّته: pip install instaloader   (رخصته MIT). ولفيديو بس من غير بيانات: rd.py grab <URL> بيستخدم yt-dlp.")


def loader(session=None, quiet=True):
    il = need()
    L = il.Instaloader(quiet=quiet, download_comments=False, save_metadata=False, compress_json=False,
                       download_video_thumbnails=False, post_metadata_txt_pattern="", max_connection_attempts=2,
                       request_timeout=30)
    if session:
        try:
            L.load_session_from_file(session)
        except FileNotFoundError:
            sys.exit(f"مفيش سيشن محفوظة لـ {session}. على جهازك: rd.py insta login {session}")
    return L


def post_info(p):
    """Plain dict from an instaloader Post (or anything with the same attributes)."""
    cap = (p.caption or "").strip()
    d = {"shortcode": p.shortcode, "url": f"https://www.instagram.com/p/{p.shortcode}/",
         "date": p.date_utc.strftime("%Y-%m-%d %H:%M") if getattr(p, "date_utc", None) else None,
         "type": p.typename, "is_video": bool(p.is_video), "likes": p.likes, "comments": p.comments,
         "views": getattr(p, "video_view_count", None) if p.is_video else None,
         "duration": getattr(p, "video_duration", None) if p.is_video else None,
         "caption": cap, "hashtags": list(getattr(p, "caption_hashtags", []) or []), "owner": getattr(p, "owner_username", None)}
    return d


def row(d):
    eng = f"❤ {d['likes']:,} · 💬 {d['comments']:,}" + (f" · ▶ {d['views']:,}" if d.get("views") else "")
    cap = d["caption"].replace("\n", " ")
    return f"{d['date'] or '—'} · {'ريل' if d['is_video'] else 'صورة' if d['type'] == 'GraphImage' else 'ألبوم'} · {eng} · {d['url']}\n    {cap[:110]}{'…' if len(cap) > 110 else ''}"


def cmd_doctor(a):
    try:
        import instaloader
        print(f"✅ instaloader {instaloader.__version__}")
    except ImportError:
        print("❌ instaloader مش متثبت ← pip install instaloader")
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, text=True)
    print(f"{'✅' if r.returncode == 0 else '❌'} yt-dlp {r.stdout.strip() or '(مش متثبت ← pip install yt-dlp)'}")


def cmd_profile(a):
    il = need()
    L = loader(a.session)
    P = il.Profile.from_username(L.context, username(a.user))
    info = {"username": P.username, "name": P.full_name, "followers": P.followers, "following": P.followees,
            "posts": P.mediacount, "bio": P.biography, "private": P.is_private, "verified": P.is_verified,
            "external_url": P.external_url, "recent": []}
    if not P.is_private or a.session:
        for i, p in enumerate(P.get_posts()):
            if i >= a.posts:
                break
            info["recent"].append(post_info(p))
            time.sleep(a.wait)
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return
    print(f"@{info['username']} ({info['name']}){' ✔' if info['verified'] else ''}{' 🔒 خاص' if info['private'] else ''}")
    print(f"متابعين {info['followers']:,} · بيتابع {info['following']:,} · بوستات {info['posts']:,}")
    if info["bio"]:
        print("البايو:", info["bio"].replace("\n", " · "))
    for d in info["recent"]:
        print("- " + row(d))


def save_post(L, p, out, media=True, comments=0):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    d = post_info(p)
    (out / "caption.txt").write_text(d["caption"], encoding="utf-8")
    if comments:
        cs = []
        for i, c in enumerate(p.get_comments()):
            if i >= comments:
                break
            cs.append({"user": c.owner.username, "text": c.text, "likes": getattr(c, "likes_count", None), "date": c.created_at_utc.strftime("%Y-%m-%d")})
        d["top_comments"] = cs
    files = []
    if media:
        items = list(p.get_sidecar_nodes()) if p.typename == "GraphSidecar" else [p]
        for i, n in enumerate(items, 1):
            url = n.video_url if n.is_video else (n.display_url if hasattr(n, "display_url") else n.url)
            ext = "mp4" if n.is_video else "jpg"
            f = out / f"{p.shortcode}_{i:02d}.{ext}"
            if not f.exists():
                L.context.get_and_write_raw(url, str(f))
            files.append(str(f))
    d["files"] = files
    (out / "meta.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def cmd_post(a):
    il = need()
    L = loader(a.session)
    p = il.Post.from_shortcode(L.context, shortcode(a.target))
    out = Path(a.out or f"insta_{p.shortcode}")
    d = save_post(L, p, out, not a.no_media, a.comments)
    print(row(d))
    for f in d["files"]:
        print("  ←", Path(f).resolve())
    print("  ←", (out / "meta.json").resolve())


def cmd_download(a):
    il = need()
    L = loader(a.session)
    P = il.Profile.from_username(L.context, username(a.user))
    since = datetime.datetime.fromisoformat(a.since) if a.since else None
    n = 0
    for p in P.get_posts():
        if since and p.date_utc < since:
            break
        if a.reels_only and not p.is_video:
            continue
        d = save_post(L, p, Path(a.out) / p.shortcode)
        print(f"{n + 1}. " + row(d))
        n += 1
        if n >= a.max:
            break
        time.sleep(a.wait)
    print(f"{n} بوست ← {Path(a.out).resolve()}")


def rank(posts, by="likes", n=10):
    key = {"likes": lambda d: d["likes"] or 0, "comments": lambda d: d["comments"] or 0, "views": lambda d: d.get("views") or 0}[by]
    return sorted(posts, key=key, reverse=True)[:n]


def cmd_top(a):
    il = need()
    L = loader(a.session)
    P = il.Profile.from_username(L.context, username(a.user))
    posts = []
    for i, p in enumerate(P.get_posts()):
        if i >= a.posts:
            break
        posts.append(post_info(p))
        time.sleep(a.wait)
    top = rank(posts, a.by, a.n)
    if a.json:
        print(json.dumps(top, ensure_ascii=False, indent=1))
        return
    print(f"أعلى {len(top)} من آخر {len(posts)} بوست لـ @{P.username} حسب {a.by}:")
    for i, d in enumerate(top, 1):
        print(f"{i}. " + row(d))


def swipe_rows(acct, followers, posts):
    """TSV rows for ig-viral/swipe.py: account, followers, median (of this account's recent reel views), views, hook (first caption line)."""
    vids = sorted(d["views"] for d in posts if d.get("is_video") and d.get("views"))
    med = vids[len(vids) // 2] if len(vids) % 2 else (sum(vids[len(vids) // 2 - 1:len(vids) // 2 + 1]) / 2 if vids else 0)
    rows = []
    for d in posts:
        if d.get("is_video") and d.get("views"):
            hook = (d["caption"].strip().splitlines() or [""])[0].replace("\t", " ")[:200]
            rows.append(f"@{acct}\t{followers}\t{int(med)}\t{d['views']}\t{hook}")
    return rows


def cmd_swipe(a):
    il = need()
    L = loader(a.session)
    out = ["account\tfollowers\tmedian\tviews\thook"]
    for u in a.users:
        P = il.Profile.from_username(L.context, username(u))
        posts = []
        for i, p in enumerate(P.get_posts()):
            if i >= a.posts:
                break
            posts.append(post_info(p))
            time.sleep(a.wait)
        out += swipe_rows(P.username, P.followers, posts)
    Path(a.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(out) - 1} ريل من {len(a.users)} حساب ← {Path(a.out).resolve()}\nالخطوة الجاية: rd.py ig swipe {a.out} --out swipe.md")


def cmd_login(a):
    need()
    print("هتكتب الباسورد في نافذة instaloader نفسها. التنين مابيشوفهاش ومابيحفظهاش. السيشن بتتحفظ في مجلد instaloader على جهازك.")
    raise SystemExit(subprocess.call([sys.executable, "-m", "instaloader", "--login", username(a.user), "--no-posts", "--no-profile-pic", "--", "@" + username(a.user)]))


def cmd_selftest(a):
    ok, bad = 0, []

    def t(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)
    t("shortcode /p/", shortcode("https://www.instagram.com/p/DAbc123_-x/?igsh=xyz") == "DAbc123_-x")
    t("shortcode /reel/", shortcode("https://instagram.com/reel/C9xYz12AbCd/") == "C9xYz12AbCd")
    t("shortcode user/reel", shortcode("https://www.instagram.com/majed_alzaabi_/reel/C9xYz12AbCd/") == "C9xYz12AbCd")
    t("bare shortcode", shortcode("C9xYz12AbCd") == "C9xYz12AbCd")
    t("username from url", username("https://www.instagram.com/khaledragab_official/") == "khaledragab_official")
    t("username @", username("@majed_alzaabi_") == "majed_alzaabi_")
    try:
        username("https://www.instagram.com/p/abc/")
        t("reject post url as user", False)
    except ValueError:
        t("reject post url as user", True)

    class P:  # a fake Post with the attributes instaloader exposes
        def __init__(s, code, likes, comments, views, video=True):
            s.shortcode, s.likes, s.comments, s.video_view_count, s.is_video = code, likes, comments, views, video
            s.caption, s.typename, s.date_utc, s.video_duration = "كابشن #ترند", "GraphVideo" if video else "GraphImage", datetime.datetime(2026, 11, 1), 21.5
            s.caption_hashtags, s.owner_username = ["ترند"], "x"
    ps = [post_info(P("a", 10, 1, 500)), post_info(P("b", 300, 9, 90)), post_info(P("c", 50, 40, 9000)), post_info(P("d", 5, 0, None, False))]
    t("post_info fields", ps[0]["url"].endswith("/p/a/") and ps[0]["hashtags"] == ["ترند"] and ps[3]["views"] is None)
    t("rank by likes", [d["shortcode"] for d in rank(ps, "likes", 2)] == ["b", "c"])
    t("rank by views", rank(ps, "views", 1)[0]["shortcode"] == "c")
    t("row text", "ريل" in row(ps[0]) and "▶ 500" in row(ps[0]))
    sr = swipe_rows("acc", 48000, ps)
    t("swipe rows: median of reel views", len(sr) == 3 and sr[0].split("\t")[2] == "500" and sr[0].startswith("@acc\t48000"))
    ig = Path(__file__).with_name("ig.py")
    lib = Path(__file__).resolve().parents[4] / "library"
    if (lib / "ig-viral" / "swipe.py").is_file():
        import tempfile
        tsv = Path(tempfile.mkdtemp()) / "c.tsv"
        tsv.write_text("account\tfollowers\tmedian\tviews\thook\n" + "\n".join(swipe_rows("acc", 48000, ps)) + "\n", encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ig), "swipe", str(tsv), "--json"], capture_output=True, text=True, encoding="utf-8")
        t("ig swipe runs on insta swipe output", r.returncode == 0 and "acc" in r.stdout)
        h = tsv.with_name("h.txt")
        h.write_text("I lost $18,000 because of one missing contract.\nHey guys, today I wanted to talk about content\n", encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ig), "hooks", str(h)], capture_output=True, text=True, encoding="utf-8")
        t("ig hooks ranks", r.returncode == 0 and "HOOK RANKING" in r.stdout and "Greeting" in r.stdout)
    print(f"{ok}/{ok + len(bad)} insta-reader checks" + (f" · فشل: {', '.join(bad)}" if bad else ""))
    sys.exit(0 if not bad else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor").set_defaults(f=cmd_doctor)
    s = sp.add_parser("profile"); s.add_argument("user"); s.add_argument("--posts", type=int, default=12); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_profile)
    s = sp.add_parser("post"); s.add_argument("target"); s.add_argument("--out"); s.add_argument("--no-media", action="store_true"); s.add_argument("--comments", type=int, default=0); s.set_defaults(f=cmd_post)
    s = sp.add_parser("download"); s.add_argument("user"); s.add_argument("--out", required=True); s.add_argument("--max", type=int, default=12); s.add_argument("--since"); s.add_argument("--reels-only", action="store_true"); s.set_defaults(f=cmd_download)
    s = sp.add_parser("top"); s.add_argument("user"); s.add_argument("--posts", type=int, default=50); s.add_argument("--by", choices=["likes", "comments", "views"], default="likes"); s.add_argument("--n", type=int, default=10); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_top)
    s = sp.add_parser("swipe"); s.add_argument("users", nargs="+"); s.add_argument("--out", required=True); s.add_argument("--posts", type=int, default=24); s.set_defaults(f=cmd_swipe)
    s = sp.add_parser("login"); s.add_argument("user"); s.set_defaults(f=cmd_login)
    sp.add_parser("selftest").set_defaults(f=cmd_selftest)
    for name in ("profile", "post", "download", "top", "swipe"):
        sp.choices[name].add_argument("--session", help="اسم حسابك اللي عملت بيه login (للخاص والستوريز)")
        sp.choices[name].add_argument("--wait", type=float, default=1.5, help="ثواني بين الطلبات")
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
