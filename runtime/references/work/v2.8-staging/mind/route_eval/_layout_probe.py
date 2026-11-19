"""Compare fix_layout on bracketed / all-caps English between two rd.py copies (argv: SCRIPTS_DIR...)."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-lp-")
CASES = ["[OPTIONS] اعمل مونتاج", "OPTIONS", "[OPTIONS]", "README.md اقراه", "اقرا SKILL.md", "P'DJ TDK LIHVM HGJKDK",
         "شغل ffmpeg -i in.mp4", "[ERROR] الفيديو مش بيشتغل", "خلي الـ FPS 60", "اعمل PDF من الصور",
         "[d] [hl]", "[hl] ;fdv", "hulg l,kjh[ tdn,", "[INFO] lhaD", "',g ,i, fdplg hgjd; j,; hdi hgla;gm"]
for i, d in enumerate(sys.argv[1:]):
    spec = importlib.util.spec_from_file_location(f"rd{i}", Path(d) / "rd.py")
    rd = importlib.util.module_from_spec(spec); argv = sys.argv; sys.argv = [argv[0]]; spec.loader.exec_module(rd); sys.argv = argv
    print("==", rd.VERSION, d)
    for c in CASES:
        print(json.dumps({"in": c, "out": rd.understand(c)["text"]}, ensure_ascii=False))
