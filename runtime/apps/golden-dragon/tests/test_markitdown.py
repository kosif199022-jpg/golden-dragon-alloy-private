"""📄 Attachments -> Markdown with MarkItDown (gd_patches/gd_markitdown.py)."""
import ast
import re
import sys
from pathlib import Path

import pytest

from conftest import FORGE, read, tree


def _methods():
    """The generated MarkItDown helpers, lifted out of app.py into a small stand-in class (no window, no API)."""
    cls = next(n for n in ast.walk(tree()) if isinstance(n, ast.ClassDef)
               and any(isinstance(f, ast.FunctionDef) and f.name == "_gd_markdown" for f in n.body))
    keep = [n for n in cls.body if (isinstance(n, ast.FunctionDef) and n.name in ("_gd_fix_arabic", "_gd_markdown"))
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("GD_MD_EXT", "GD_MD_MAX"))]
    mod = ast.Module(body=[ast.ClassDef(name="C", bases=[], keywords=[], body=keep, decorator_list=[])], type_ignores=[])
    ns = {"re": re, "Path": Path}
    exec(compile(ast.fix_missing_locations(mod), "app.py", "exec"), ns)
    return ns["C"]


def test_patch_is_in_the_app_and_the_forge():
    app = read("app.py")
    assert app.count("def _gd_markdown(self, p):") == 1
    assert app.count("elif ext in self.GD_MD_EXT") == 1
    assert app.index("elif ext in self.GD_MD_EXT") < app.index('elif ext == ".pdf" and p.stat().st_size < 30 * 1024 * 1024:')
    assert "## 📄 المستندات ← Markdown" in app
    forge = (FORGE / "make_golden_dragon.py").read_text(encoding="utf-8")
    assert 'gd_patches" / "gd_markitdown.py"' in forge


def test_arabic_pdf_in_visual_order_is_fixed():
    C = _methods()
    assert C._gd_fix_arabic("ﺎًﻧﺎﺠﻣ — ﻦﻳﻼﻧوا ﲑﺒﺧ تﺎﻔﻠﻣ") == "ملفات خبير اونلاين — مجانًا"
    assert C._gd_fix_arabic("Claude Code 3.2 ﻞﻳر") == "ريل Claude Code 3.2"
    assert C._gd_fix_arabic("plain English 123\nسطر عادي") == "plain English 123\nسطر عادي"


def test_without_markitdown_the_old_path_is_kept(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "markitdown", None)          # import fails as if it was not installed
    C = _methods()
    c = C()
    c.wd = lambda: tmp_path
    f = tmp_path / "a.docx"
    f.write_bytes(b"PK\x03\x04")
    assert c._gd_markdown(f) is None
    assert not (tmp_path / "_md").exists()


def test_with_markitdown_a_word_file_becomes_markdown(tmp_path):
    pytest.importorskip("markitdown")
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_heading("تقرير التنين", 1)
    d.add_paragraph("الفقرة الأولى من التقرير، وفيها كلام كفاية عشان يعدّي حد الأربعين حرف.")
    f = tmp_path / "r.docx"
    d.save(f)
    C = _methods()
    c = C()
    c.wd = lambda: tmp_path / "work"
    saved, text = c._gd_markdown(f)
    assert "# تقرير التنين" in text and saved == tmp_path / "work" / "_md" / "r.docx.md" and saved.read_text(encoding="utf-8") == text
    c.GD_MD_MAX = 30
    _, cut = c._gd_markdown(f)
    assert "اتقصّ هنا" in cut and str(saved) in cut
