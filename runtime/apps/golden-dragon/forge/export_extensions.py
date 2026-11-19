"""export_extensions.py — the same thing as the app's «انسخ الإضافة» (Api.extension_to_desktop), for both apps, but taking
the v1.4.0 extension (the Golden Bird's staged build / the installed Golden Dragon) instead of the running Golden Bird's
older copy. Writes Desktop\\<name> - إضافة كروم\\ with config.json {token, port} and the install note. The pairing token
is read from the app settings and written only into config.json; it is never printed.

  python -X utf8 export_extensions.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
DESK = HOME / "OneDrive" / "Desktop" if (HOME / "OneDrive" / "Desktop").exists() else HOME / "Desktop"
APPDATA = Path(os.environ["APPDATA"])
README = ('تثبيت إضافة {name} في كروم (مرة واحدة):\r\n1) افتح كروم واكتب في العنوان: chrome://extensions\r\n'
          '2) فعّل Developer mode (فوق على اليمين).\r\n3) دوس Load unpacked واختار المجلد ده نفسه.\r\n'
          '4) خلاص: الإضافة بتتوصل بالتطبيق لوحدها (كود الربط جوه config.json). أيقونة الإضافة بيظهر عليها نقطة خضرا لما تتوصل.\r\n\r\n'
          'عشان {name} يتحكم في كروم: في التطبيق فعّل «🖥 تحكم في الجهاز وكروم» في المحادثة.\r\n'
          'ماتشيلش المجلد ده من مكانه بعد التثبيت، كروم بيشغّل الإضافة منه.\r\n')
APPS = [  # (name, settings folder, extension source (v1.4), port)
    ("الطائر الذهبي", "GoldenBird", HOME / ".goldenbird-build" / "dist" / "GoldenBird" / "_internal" / "chrome_extension", 47841),
    ("التنين الذهبي", "GoldenDragon", HOME / "GoldenDragon" / "_internal" / "chrome_extension", 47851),
]


def token_of(folder):
    """bridge_token of this app, else of the Golden Bird (the Golden Dragon copies it on its first run)."""
    for f in (APPDATA / folder / "settings.json", APPDATA / "GoldenBird" / "settings.json"):
        if f.is_file():
            t = json.loads(f.read_text(encoding="utf-8-sig")).get("bridge_token")
            if t:
                return t, f.parent.name
    return None, None


def main():
    ok = True
    for name, folder, src, port in APPS:
        if not (src / "manifest.json").is_file():
            print(f"✗ {name}: الإضافة مش موجودة في {src}")
            ok = False
            continue
        token, origin = token_of(folder)
        if not token:
            print(f"✗ {name}: مفيش كود ربط في الإعدادات")
            ok = False
            continue
        dst = DESK / f"{name} - إضافة كروم"
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("config.json"))
        (dst / "config.json").write_text(json.dumps({"token": token, "port": port}), encoding="utf-8")
        (dst / "اقرأني - طريقة التثبيت.txt").write_text(README.format(name=name), encoding="utf-8", newline="")
        man = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
        js = (dst / "background.js").read_text(encoding="utf-8")
        print(f"✓ {name}: {dst} | v{man.get('version')} | port {port} | background.js port ok: {f'const PORT = {port};' in js}"
              f" | token from {origin} settings (not shown)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
