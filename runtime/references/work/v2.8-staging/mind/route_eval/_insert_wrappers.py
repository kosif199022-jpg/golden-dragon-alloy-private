"""One-off: copy strip_wrappers (lines 16..135 of wrappers_proposal.py) into rd.py just before fix_layout, and wire understand()."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
rd = HERE.parent.parent / "scripts" / "rd.py"
src = (HERE / "wrappers_proposal.py").read_text(encoding="utf-8").splitlines()
block = "\n".join(src[15:135]).rstrip() + "\n\n\n"
code = rd.read_text(encoding="utf-8")
assert "def strip_wrappers" not in code
head = "# ------------------------------------------------------------------ v2.8: the fixed text the app wraps around a request\n"
anchor = "def fix_layout(text):"
assert code.count(anchor) == 1
code = code.replace(anchor, head + block + anchor)
old = '''def understand(text):
    t1, lay = fix_layout(" ".join(str(text).split()))
    t2, hits = fix_dictation(t1)
    return {"text": t2, "layout_fixed": lay, "words_fixed": hits, "changed": lay or bool(hits)}'''
new = '''def understand(text):
    clean, wraps = strip_wrappers(str(text))          # v2.8: agents-team / work-folder / skills prefixes / error tails are not the request
    t1, lay = fix_layout(" ".join(clean.split()))
    t2, hits = fix_dictation(t1)
    return {"text": t2, "layout_fixed": lay, "words_fixed": hits, "changed": lay or bool(hits), "wrappers": wraps}'''
assert code.count(old) == 1
code = code.replace(old, new)
rd.write_text(code, encoding="utf-8")
print("ok", len(block.splitlines()), "lines inserted")
