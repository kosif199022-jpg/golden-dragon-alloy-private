#!/usr/bin/env python3
"""doc-reader: يحوّل أي مستند لـ Markdown بـ Microsoft MarkItDown (MIT) قبل ما التنين يقراه.

  doctor                                    MarkItDown متثبت؟ وأنهي صيغ شغالة؟ ولو لأ يقولك تثبّته إزاي
  convert FILE [FILE ...] [--out DIR] [--print] [--max-chars N] [--json]
                                            كل ملف ← DIR/<الاسم بامتداده>.md (الافتراضي: مجلد _md جنب الملف)
  batch DIR [--out DIR] [--recursive] [--json]
                                            كل المستندات اللي في المجلد
  exts                                      الصيغ اللي بيحوّلها
  install [--yes]                           pip install "markitdown[all]" (من غير --yes بيطبع الأمر بس)
  selftest                                  فحوص من غير نت

الصيغ: PDF، Word (docx)، PowerPoint (pptx)، Excel (xlsx/xls)، HTML، CSV، JSON، XML، EPUB، Outlook (msg)، ZIP، ونصوص.
من غير MarkItDown: النص وCSV وJSON وHTML بيتحوّلوا بمكتبة بايثون العادية، والـ PDF بـ PyMuPDF لو موجودة.
ملفات محلية بس: لينك من النت يتحمّل الأول (بموافقة صاحب الشغل)، وبعدين يتحوّل.
"""
import argparse, csv, html, io, json, logging, re, subprocess, sys, tempfile, unicodedata
from html.parser import HTMLParser
from pathlib import Path

DOC_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm", ".csv", ".json", ".xml", ".epub", ".msg", ".zip",
           ".txt", ".md", ".rtf", ".ipynb"}
TEXT_EXT = {".txt", ".md", ".rtf"}
MAX_BYTES = 200 * 1024 * 1024


def markitdown():
    try:
        from markitdown import MarkItDown
        return MarkItDown
    except Exception:
        return None


def version():
    try:
        import importlib.metadata as md
        return md.version("markitdown")
    except Exception:
        return None


# ---------------------------------------------------------------- fallbacks (stdlib, + PyMuPDF for PDF)
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table"}

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.head = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def _tidy(t):
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


def _table(rows):
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    w = max(len(r) for r in rows)
    rows = [[c.replace("|", "\\|").replace("\n", " ").strip() for c in r] + [""] * (w - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines) + "\n"


def _lf(s):
    """One kind of line end. A Windows file keeps \\r\\n, and write_text on Windows then writes \\r\\r\\n (v3.4 fix)."""
    return s.replace("\r\n", "\n").replace("\r", "\n") if s else s


def fallback(p):
    ext = p.suffix.lower()
    raw = p.read_bytes()
    if ext in TEXT_EXT:
        return _lf(raw.decode("utf-8-sig", errors="replace")), "text"
    if ext == ".csv":
        return _table(list(csv.reader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))))), "csv"
    if ext in (".json", ".ipynb"):
        return "```json\n" + json.dumps(json.loads(raw.decode("utf-8-sig")), ensure_ascii=False, indent=2) + "\n```\n", "json"
    if ext in (".html", ".htm", ".xml"):
        h = _Text()
        h.feed(raw.decode("utf-8-sig", errors="replace"))
        return _tidy(html.unescape("".join(h.out))), "html"
    if ext == ".pdf":
        try:
            import pymupdf
        except ImportError:
            try:
                import fitz as pymupdf
            except ImportError:
                return None, None
        with pymupdf.open(str(p)) as d:
            return fix_arabic(_tidy("\n\n".join(f"<!-- page {i} -->\n{pg.get_text()}" for i, pg in enumerate(d, 1))))[0], "pymupdf"
    return None, None


# ---------------------------------------------------------------- Arabic PDF text in visual order
# pdfminer (MarkItDown's PDF reader) gives many Arabic PDFs back as presentation forms in visual order: «ﻦﻳﻼﻧوا ﲑﺒﺧ».
# Such a line is folded to normal letters (NFKC), reversed, and its Latin/number runs are turned back the right way.
PF = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
LTR = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:;/_\-+@#&%'\"]*[A-Za-z0-9]|[A-Za-z0-9]")
MIRROR = str.maketrans("()[]{}«»<>", ")(][}{»«><")


def fix_arabic_line(s):
    if not PF.search(s):
        return s
    s = unicodedata.normalize("NFKC", s[::-1]).translate(MIRROR)   # reverse first, so a ligature (ﲑ) expands in reading order
    return LTR.sub(lambda m: m.group(0)[::-1], s)


def fix_arabic(text):
    if not PF.search(text):
        return text, False
    return "\n".join(fix_arabic_line(x) for x in text.split("\n")), True


# ---------------------------------------------------------------- convert
def convert_one(p, md_cls=None):
    """(markdown, engine) for one local file. Raises ValueError with an Egyptian-Arabic reason."""
    p = Path(p)
    if not p.is_file():
        raise ValueError(f"الملف مش موجود: {p}")
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(f"الملف أكبر من {MAX_BYTES // 1024 // 1024} ميجا: {p.name}")
    md_cls = md_cls if md_cls is not None else markitdown()
    logging.getLogger("pdfminer").setLevel(logging.ERROR)    # pdfminer prints a FontBBox warning per page on many PDFs
    err = None
    if md_cls:
        try:
            r = md_cls(enable_plugins=False).convert(str(p))
            text = _lf(r.text_content or "")
            if p.suffix.lower() == ".pdf":
                text, fixed = fix_arabic(text)
                if fixed:
                    return text, "markitdown+arabic-fix"
            if text.strip() or p.suffix.lower() not in (".pdf",):
                return text, "markitdown"
            err = "MarkItDown طلّع نص فاضي"
        except Exception as e:            # missing optional extra (pdf/docx/…) or a broken file
            err = f"{type(e).__name__}: {str(e)[:200]}"
    text, eng = fallback(p)
    if text is not None:
        return text, eng
    if p.suffix.lower() == ".pdf" and err == "MarkItDown طلّع نص فاضي":
        raise ValueError(f"{p.name}: مفيش نص في الـ PDF (غالبًا صور ممسوحة). اقراه كصور أو OCR.")
    hint = "ثبّت MarkItDown: python -m pip install \"markitdown[all]\"" if not md_cls else f"MarkItDown فشل ({err})"
    raise ValueError(f"{p.name}: مش عارف أحوّله. {hint}")


def out_path(p, out):
    d = Path(out) if out else Path(p).parent / "_md"
    d.mkdir(parents=True, exist_ok=True)
    return d / (Path(p).name + ".md")      # report.pdf -> report.pdf.md, so report.docx in the same folder never collides


def write_md(dst, text):
    """Every engine and fallback goes through here: one kind of line end, so Windows never writes \\r\\r\\n (v3.4)."""
    dst.write_text(_lf(text), encoding="utf-8")


def run(files, out=None, show=False, max_chars=0, as_json=False):
    res, bad = [], 0
    md_cls = markitdown()
    for f in files:
        try:
            text, eng = convert_one(f, md_cls)
            dst = out_path(f, out)
            write_md(dst, text)
            row = {"file": str(f), "md": str(dst), "engine": eng, "chars": len(text), "ok": True}
            if show:
                row["text"] = text[:max_chars] if max_chars else text
        except ValueError as e:
            bad += 1
            row = {"file": str(f), "ok": False, "error": str(e)}
        res.append(row)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for r in res:
            if r["ok"]:
                print(f"✅ {r['file']} ← {r['md']}  ({r['engine']}، {r['chars']:,} حرف)")
                if show:
                    print(r["text"] + ("\n…[اتقصّ]" if max_chars and r["chars"] > max_chars else ""))
            else:
                print(f"❌ {r['error']}")
    return 1 if bad else 0


def batch(d, out=None, recursive=False, as_json=False):
    d = Path(d)
    if not d.is_dir():
        sys.exit(f"مش مجلد: {d}")
    it = d.rglob("*") if recursive else d.iterdir()
    files = sorted(p for p in it if p.is_file() and p.suffix.lower() in DOC_EXT - {".md"} and "_md" not in p.parts)
    if not files:
        print("مفيش مستندات في المجلد ده.")
        return 0
    return run(files, out or d / "_md", as_json=as_json)


def doctor():
    v = version()
    print(f"MarkItDown: {'✅ ' + v if v else '❌ مش متثبت'}")
    extras = {"pdf": "pdfminer", "docx": "mammoth", "pptx": "pptx", "xlsx": "openpyxl", "xls": "xlrd", "outlook": "olefile"}
    import importlib.util as iu
    for k, mod in extras.items():
        print(f"  {k:8} {'✅' if iu.find_spec(mod) else '—'}")
    print(f"PyMuPDF (بديل الـ PDF): {'✅' if iu.find_spec('pymupdf') or iu.find_spec('fitz') else '—'}")
    if not v:
        print('ثبّته: python -m pip install "markitdown[all]"   (رخصته MIT، Microsoft)')
    return 0


def install(yes):
    cmd = [sys.executable, "-m", "pip", "install", "markitdown[all]"]
    if not yes:
        print("هيتثبت بالأمر ده (ضيف --yes عشان يشتغل):\n  " + " ".join(cmd))
        return 0
    return subprocess.call(cmd)


# ---------------------------------------------------------------- selftest (offline)
def selftest():
    ok, n = 0, 0

    def check(name, cond):
        nonlocal ok, n
        n += 1
        ok += bool(cond)
        print(("✅ " if cond else "❌ ") + name)

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "a.csv").write_text("الاسم,السعر\nقلم,5\nكشكول|كبير,20\n", encoding="utf-8")
        (t / "b.html").write_text("<html><head><style>x{}</style><script>bad()</script></head><body><h1>عنوان</h1>"
                                  "<p>فقرة &amp; نص</p><ul><li>واحد</li><li>اتنين</li></ul></body></html>", encoding="utf-8")
        (t / "c.json").write_text('{"اسم": "تنين"}', encoding="utf-8")
        (t / "d.txt").write_text("سطر عربي\n", encoding="utf-8")
        md, eng = fallback(t / "a.csv")
        check("CSV ← جدول Markdown", md.startswith("| الاسم | السعر |") and "كشكول\\|كبير" in md and eng == "csv")
        md, _ = fallback(t / "b.html")
        check("HTML ← عناوين وقوائم من غير script/style", "# عنوان" in md and "- واحد" in md and "bad()" not in md and "فقرة & نص" in md)
        visual = "ﺎًﻧﺎﺠﻣ — ﻦﻳﻼﻧوا ﲑﺒﺧ تﺎﻔﻠﻣ"
        check("PDF عربي مقلوب (visual order) ← يتعدل", fix_arabic(visual)[0] == unicodedata.normalize("NFKC", "ملفات خبير اونلاين — مجانًا"))
        check("السطر الإنجليزي والأرقام يفضلوا زي ما هم", fix_arabic_line("Claude Code 3.2 ﻞﻳر") == "ريل Claude Code 3.2"
              and fix_arabic("Hello 123")[0] == "Hello 123")
        md, _ = fallback(t / "c.json")
        check("JSON ← بلوك كود والعربي سليم", "```json" in md and "تنين" in md)
        check("نص عادي زي ما هو", fallback(t / "d.txt")[0] == "سطر عربي\n")
        (t / "w.txt").write_bytes("سطر\r\nتاني\r\n".encode("utf-8"))          # a real Windows file (CRLF), v3.4
        rc_w = run([t / "w.txt"], out=t / "ow", as_json=False)
        check("ملف ويندوز CRLF ← مفيش \\r\\r في الناتج", fallback(t / "w.txt")[0] == "سطر\nتاني\n" and rc_w == 0
              and b"\r\r" not in (t / "ow" / "w.txt.md").read_bytes())
        write_md(t / "mixed.md", "أ\r\nب\rج\n")                            # HTML/XML/CSV fallbacks keep \r: the writer fixes all
        check("الكتابة بتوحّد نهايات السطور لأي محرك", b"\r\r" not in (t / "mixed.md").read_bytes()
              and (t / "mixed.md").read_text(encoding="utf-8") == "أ\nب\nج\n")
        check("صيغة مش معروفة من غير MarkItDown ← رسالة واضحة", _raises(lambda: convert_one(_mk(t / "e.bin"), md_cls=False), "مش عارف أحوّله"))
        check("ملف مش موجود ← رسالة واضحة", _raises(lambda: convert_one(t / "zz.pdf"), "مش موجود"))
        check("الناتج في _md جنب الملف", out_path(t / "a.csv", None) == t / "_md" / "a.csv.md" and out_path(t / "a.html", None) != out_path(t / "a.csv", None))
        rc = run([t / "a.csv", t / "d.txt"], out=t / "o", as_json=False)
        check("convert بيكتب ملفات .md", rc == 0 and (t / "o" / "a.csv.md").is_file() and (t / "o" / "d.txt.md").is_file())
        check("batch بيتجاهل _md ونفسه", batch(t, out=t / "o2") == 0 and not (t / "o2" / "a.csv.md").read_text(encoding="utf-8") == "")
        M = markitdown()
        if M:
            md, eng = convert_one(t / "b.html", M)
            check(f"MarkItDown {version()} على HTML", eng == "markitdown" and "عنوان" in md)
            md, eng = convert_one(t / "a.csv", M)
            check("MarkItDown على CSV ← جدول", eng == "markitdown" and "| الاسم" in md)
            try:
                import docx
                doc = docx.Document()
                doc.add_heading("تقرير التنين", 1)
                doc.add_paragraph("الفقرة الأولى")
                doc.save(t / "f.docx")
                md, eng = convert_one(t / "f.docx", M)
                check("MarkItDown على Word (docx)", eng == "markitdown" and "# تقرير التنين" in md and "الفقرة الأولى" in md)
            except ImportError:
                print("— python-docx مش موجودة، فحص Word اتساب")
        else:
            print("— MarkItDown مش متثبت: فحوص البديل بس (ثبّته بـ install --yes)")
    print(f"doc-reader selftest: {ok}/{n} ok")
    return 0 if ok == n else 1


def _mk(p):
    Path(p).write_bytes(b"\x00\x01")
    return p


def _raises(fn, needle):
    try:
        fn()
    except ValueError as e:
        return needle in str(e)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rd.py md", description="أي مستند ← Markdown بـ MarkItDown")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("exts")
    sub.add_parser("selftest")
    s = sub.add_parser("install"); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("convert"); s.add_argument("files", nargs="+"); s.add_argument("--out"); s.add_argument("--print", dest="show", action="store_true")
    s.add_argument("--max-chars", type=int, default=0); s.add_argument("--json", action="store_true")
    s = sub.add_parser("batch"); s.add_argument("dir"); s.add_argument("--out"); s.add_argument("--recursive", action="store_true"); s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "exts":
        print(" ".join(sorted(DOC_EXT)))
        return 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "install":
        return install(a.yes)
    if a.cmd == "convert":
        urls = [f for f in a.files if re.match(r"https?://", f)]
        if urls:
            sys.exit("لينكات مش مسموحة هنا: حمّل الملف الأول (بموافقة صاحب الشغل) وبعدين حوّله.")
        return run(a.files, a.out, a.show, a.max_chars, a.json)
    return batch(a.dir, a.out, a.recursive, a.json)


if __name__ == "__main__":
    sys.exit(main())
