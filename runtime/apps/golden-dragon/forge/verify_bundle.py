"""verify_bundle.py — checks the INSTALLED GoldenDragon.exe without running it: the PyInstaller archive must carry the app's
modules (app, dragon_fusion, golden_tools, golden_steer, control) and _internal must carry the data the code reads.

  python -X utf8 verify_bundle.py [EXE]
"""
import json
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

exe = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "GoldenDragon" / "GoldenDragon.exe")
internal = exe.parent / "_internal"
car = CArchiveReader(str(exe))
names = list(car.toc)
pyz_name = next(n for n in names if n.endswith(".pyz"))
# the PYZ is embedded in the exe; ZlibArchiveReader reads it from "<file>?<offset>"
entry = car.toc[pyz_name]
pyz = ZlibArchiveReader(f"{exe}?{car._start_offset + entry[0]}")
mods = set(pyz.toc)
need_mods = ["dragon_fusion", "golden_tools", "golden_steer", "control", "brain"]
need_data = ["fusion/index.json", "fusion/recipes.json", "fusion/lessons.json", "golden/library.json", "golden/studio.json",
             "ui/index.html", "ui/golden-dragon.ico", "ui/version.txt", "chrome_extension/background.js"]
res = {
    "exe": str(exe), "entry_script": [n for n in names if n == "app"], "pyz_modules": len(mods),
    "modules_missing": [m for m in need_mods if m not in mods],
    "data_missing": [d for d in need_data if not (internal / d).is_file()],
    "fusion_units": len(json.loads((internal / "fusion" / "index.json").read_text(encoding="utf-8"))["units"]),
    "recipes": len(json.loads((internal / "fusion" / "recipes.json").read_text(encoding="utf-8"))),
    "extension_port_47851": "const PORT = 47851;" in (internal / "chrome_extension" / "background.js").read_text(encoding="utf-8"),
    "version": (internal / "ui" / "version.txt").read_text(encoding="utf-8").strip(),
}
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(0 if not res["modules_missing"] and not res["data_missing"] and res["entry_script"] and res["extension_port_47851"] else 1)
