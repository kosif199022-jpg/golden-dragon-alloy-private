# -*- coding: utf-8 -*-
"""التنين الذهبي — المرفقات بتتحوّل لـ Markdown بـ MarkItDown (2026-11-16)

أي PDF أو Word أو PowerPoint أو Excel أو EPUB أو Outlook مرفق في الشات بيتحوّل لـ Markdown بـ Microsoft MarkItDown (MIT)،
وبيتبعت للنموذج كنص (أرخص وأدق من قراية الـ PDF كصور)، وبتتحفظ نسخة في «_md» جوه مجلد الشغل.
- الـ PDF العربي اللي pdfminer بيطلّعه حروف معروضة ومقلوبة بيتعدل (نفس تصليح engine/skills/doc-reader).
- لو MarkItDown مش متثبت، أو التحويل فشل، أو الـ PDF ممسوح ومافيهوش نص: المرفق بيتبعت زي ما كان قبل كده بالظبط.
- أطول من 150 ألف حرف: أوله بيتبعت، والباقي في الملف المتحفظ، والنموذج بيتقاله يقراه بأداة القراية.

بيتنادي من make_golden_dragon.py بعد gd_reviewer:  gd_markitdown.patch_app(t, sub)
"""

APP_ANCHOR = "    def attach_list(self):\n"

APP_METHODS = r'''    # ===== التنين الذهبي 2026-11-16: المرفقات ← Markdown بـ MarkItDown =====
    GD_MD_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".epub", ".msg"}
    GD_MD_MAX = 150_000

    @staticmethod
    def _gd_fix_arabic(text):
        """Arabic PDF text that pdfminer returns as presentation forms in visual order -> normal letters in reading order."""
        import unicodedata
        pf = re.compile(r"[ﭐ-﷿ﹰ-﻿]")
        if not pf.search(text):
            return text
        ltr = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:;/_\-+@#&%'\"]*[A-Za-z0-9]|[A-Za-z0-9]")
        mirror = str.maketrans("()[]{}«»<>", ")(][}{»«><")
        out = []
        for line in text.split("\n"):
            if pf.search(line):
                line = unicodedata.normalize("NFKC", line[::-1]).translate(mirror)
                line = ltr.sub(lambda m: m.group(0)[::-1], line)
            out.append(line)
        return "\n".join(out)

    def _gd_markdown(self, p):
        """(saved .md path, text for the model) via MarkItDown, or None to fall back to the old attachment path."""
        try:
            import logging
            from markitdown import MarkItDown
            logging.getLogger("pdfminer").setLevel(logging.ERROR)
            text = MarkItDown(enable_plugins=False).convert(str(p)).text_content or ""
        except Exception:
            return None
        if p.suffix.lower() == ".pdf":
            text = self._gd_fix_arabic(text)
        if len(text.strip()) < 40:          # a scanned PDF (images only) or an empty file: send it the old way
            return None
        try:
            out = Path(self.wd()) / "_md"
            out.mkdir(parents=True, exist_ok=True)
            saved = out / (p.name + ".md")      # a.pdf and a.docx in one chat never overwrite each other
            saved.write_text(text, encoding="utf-8")
        except OSError:
            saved = None
        if len(text) > self.GD_MD_MAX:
            text = (text[:self.GD_MD_MAX] + f"\n\n…[اتقصّ هنا: المستند {len(text):,} حرف، والباقي في "
                    f"{saved or 'الملف الأصلي'}، اقراه من هناك]")
        return saved, text

'''

LOOP_OLD = '            elif ext == ".pdf" and p.stat().st_size < 30 * 1024 * 1024:\n'
LOOP_NEW = (
    '            elif ext in self.GD_MD_EXT and p.stat().st_size < 100 * 1024 * 1024 and (gd_md := self._gd_markdown(p)):\n'
    '                blocks.append({"type": "text", "text": f"[ملف مرفق (اتحوّل لـ Markdown بـ MarkItDown): {p}]\\n"\n'
    '                                                       + (f"[نسخة الـ Markdown متحفظة في: {gd_md[0]}]\\n" if gd_md[0] else "")\n'
    '                                                       + gd_md[1]})\n'
    + LOOP_OLD)

PROMPT_ANCHOR = "## عقل التنين الذهبي (تفكير فائق بالعربي والإنجليزي)"
PROMPT_SECTION = (
    "## 📄 المستندات ← Markdown\n"
    "- المرفقات (PDF، Word، PowerPoint، Excel، EPUB) بتوصلك متحوّلة لـ Markdown بـ MarkItDown، ونسختها في «_md» جوه مجلد الشغل. "
    "اشتغل على النص ده. لو مكتوب «اتقصّ هنا» اقرا الباقي من الملف المتحفظ.\n"
    "- مستند على الجهاز مش مرفق: حوّله الأول بـ `rd.py md convert <الملف> --out <مجلد الشغل>/_md` واقرا الـ .md.\n\n"
)


def patch_app(t, sub):
    t = sub(t, APP_ANCHOR, APP_METHODS + APP_ANCHOR, 1, "gd_markitdown: MarkItDown helpers")
    t = sub(t, LOOP_OLD, LOOP_NEW, 1, "gd_markitdown: attachments -> Markdown")
    t = sub(t, PROMPT_ANCHOR, PROMPT_SECTION + PROMPT_ANCHOR, 1, "gd_markitdown: prompt section")
    head = "\n".join(line for line in t.splitlines()[:40] if line.startswith(("import ", "from ")))
    for mod in ("re", "Path"):
        if mod not in head:
            raise SystemExit(f"✗ gd_markitdown: app.py no longer imports {mod}")
    return t
