"""gold.py — «الطائر الذهبي» (Golden Bird) inside Red Dragon.

The studio (open-source command-line programs from the owner's «مهارات\\برامج»), the motion library (motion / web / video
libraries with their licences), speech sync and the golden protocol. It runs the SAME golden_tools.py that the Golden Bird
app ships (apps/golden-bird/app), so the app and the skill can never disagree.

  $R gold studio list | show ID | install ID --yes | cmd ID [args...]
  $R gold lib find "words" [--limit N] | show ID | kit WORKDIR ID [ID...] | stats
  $R gold sync SCRIPT.txt WORDS.json OUT_DIR [--fps 30]
  $R gold protocol     the golden protocol: before building, while working, before «done»
  $R gold where        catalogs, unpack folder, and what works on this machine
  $R gold selftest     offline checks: no program is run, nothing is downloaded, only temp folders are written

$R = python -X utf8 scripts/rd.py. Standard library only.
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True          # never leave __pycache__ inside the package
ROOT = Path(__file__).resolve().parents[4]
APP = Path(os.environ.get("GOLDEN_BIRD_APP") or (ROOT / "apps" / "golden-bird" / "app"))

PROTOCOL = """# بروتوكول الذهب (الطائر الذهبي)

**قبل ما تبني**
1. ابدأ من الآخر: اكتب في سطر شكل التسليم (الملف، ومكانه، والمقياس اللي هيثبت إنه صح).
2. تشريح قبل الفشل: تخيّل إن التسليم اترفض. اكتب أرجح 3 أسباب، واقفل كل سبب بخطوة أو فحص.
3. الجاهز قبل الجديد: `$R gold lib find "<الحركة>"` و`$R gold studio list` قبل أي كود من الصفر. الأداة اللي اتحقق منها أحسن من كود جديد.

**وإنت شغّال**
4. الأمر من الدليل مش من الذاكرة: `$R gold studio show ID` فيه الاستخدام والأمثلة والتنبيهات من البرنامج نفسه. جرّب على عيّنة صغيرة الأول.
5. أفلام HTML من غير نت: `$R gold lib kit <مجلد الشغل> ID…` بيحط النسخة الجاهزة في `vendor/` ومعاها `LICENSES.md`.
6. الوقت مربوط بالكلام: سكريبت بعلامات (`@{x}…@{/x}`، `@{x!}`، `||`) وملف كلمات من التسجيل الحقيقي. `$R sync script` هو الكامل (كاريوكي، أحداث، نص مزدوج)، و`$R gold sync` هو نفس أداة التطبيق (sync.json + captions.srt).
7. وازي: الأجزاء المستقلة (قراية، قياس، بحث، رندر مقاطع) مع بعض، مش ورا بعض.

**قبل «خلص»**
8. قيس كل ناتج (`$E verify` أو بصّ على فريم بعينك). ماتقولش «خلص» على حاجة ماتقاستش.
9. الرخص قبل الشغل التجاري: أي مكتبة `commercial_ok` بتاعتها مش `yes` قولها لصاحب الشغل الأول (غير تجاري، GPL/AGPL، Commons Clause، ترخيص تجاري).
10. ناقد داخلي: إيه أضعف حاجة في الناتج؟ صلّحها لو رخيصة، أو قولها بصراحة. والرد بأسلوب Apple: النتيجة في أول سطر، وبعدها أقل كلام يوصّل المعنى.

**بموافقة صريحة:** فك برنامج (`studio install … --yes`) وتشغيله، وأي حاجة بفلوس أو نشر.
"""


def gt():
    """golden_tools from the Golden Bird app folder (one source of truth)."""
    src = APP / "golden_tools.py"
    if not src.is_file():
        raise SystemExit(f"✗ كود الطائر الذهبي مش موجود: {src}")
    spec = importlib.util.spec_from_file_location("golden_tools", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



def where():
    g = gt()
    lib = g.library()
    roots = [Path(r) for r in lib.get("roots") or []]
    local = any(r.is_dir() for r in roots)
    st = g.stats()
    print(f"الكتالوج: {g.DATA}")
    print(f"- مكتبة الموشن: {st['library']} عنصر، منهم {st['ready_offline']} جاهزين من غير نت")
    print(f"- الاستوديو: {st['studio']} برنامج، منهم {st['studio_ready']} متفكوك في {g.STUDIO_HOME}")
    print(f"- مجلد «مهارات» (مصدر الملفات): {'موجود ✓' if local else 'مش على الجهاز ده'}")
    print("- شغّال هنا: " + ("كل حاجة (find/show/kit/install/cmd/sync)" if local and g.seven_zip()
                             else "find/show/sync بس؛ kit وinstall محتاجين لابتوب صاحب الشغل" + ("" if g.seven_zip() else " و7-Zip")))
    return 0


def selftest():
    g = gt()
    ok, bad = 0, []

    def t(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    lib, progs = g.lib_items(), g.studio_items()
    t("catalog: library >= 150", len(lib) >= 150)
    t("catalog: studio >= 10", len(progs) >= 10)
    t("catalog: unique ids", len({i["id"] for i in lib}) == len(lib) and len({p["id"] for p in progs}) == len(progs))
    t("catalog: every item has a licence", all(i.get("license") for i in lib + progs))
    t("catalog: offline-ready items have an entry", sum(1 for i in lib if i.get("offline_entry")) >= 10)
    t("find: Arabic «انيميشن» reaches GSAP or anime.js", any(i["id"] in ("gsap", "animejs") for i in g.lib_find("انيميشن", 8)))
    t("find: lottie first", (g.lib_find("lottie", 3) or [{}])[0].get("id") == "lottie-web")
    try:
        t("show: every studio program renders with usage + examples",
          all("الاستخدام" in g.md_studio_show(p["id"]) and p.get("examples") for p in progs))
    except Exception as e:      # noqa: BLE001 — a selftest reports, it does not crash
        bad.append(f"show: {type(e).__name__}")

    tmp = Path(tempfile.mkdtemp(prefix="gold_selftest_"))
    # studio: a .cmd target refuses cmd.exe metacharacters (BatBadBut); a fake unpack, nothing is executed
    g.STUDIO_HOME = tmp / "studio"
    gm = next((p for p in progs if p["exe"].lower().endswith(".cmd")), None)
    if gm:
        fake = g.studio_dir(gm) / gm["exe"]
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_text("@echo off\n", encoding="utf-8")
        try:
            g.studio_cmd(gm["id"], ["a & calc"])
            t("studio: .cmd refuses & | ^ < > %", False)
        except ValueError:
            t("studio: .cmd refuses & | ^ < > %", True)
        t("studio: plain args pass", g.studio_cmd(gm["id"], ["--help"])[0][1:] == ["--help"])
    # studio: the archive hash is checked before anything is unpacked
    if g.seven_zip():
        arc = tmp / "arc.zip"
        with zipfile.ZipFile(arc, "w") as z:
            z.writestr("demo/x.exe", "not a program")
        g.studio_items = lambda: [{"id": "demo", "name": "demo", "exe": "demo/x.exe", "archive": str(arc), "archive_sha256": "0" * 64}]
        out, good = g.studio_install("demo")
        t("studio: wrong archive hash = no unpack", not good and not (g.STUDIO_HOME / "demo").exists())
    # kit: copies only from inside the library roots, and writes LICENSES.md
    root = tmp / "libs"
    (root / "ok").mkdir(parents=True)
    (root / "ok" / "ok.min.js").write_text("/*ok*/", encoding="utf-8")
    (tmp / "outside").mkdir()
    (tmp / "outside" / "x.js").write_text("/*x*/", encoding="utf-8")
    fake_lib = {"roots": [str(root)], "items": [
        {"id": "ok", "name": "ok", "offline_entry": str(root / "ok" / "ok.min.js"), "license": "MIT", "commercial_ok": "yes", "source": "test"},
        {"id": "out", "name": "out", "offline_entry": str(tmp / "outside" / "x.js"), "license": "MIT", "commercial_ok": "yes", "source": "test"}]}
    g.library = lambda: fake_lib
    work = tmp / "work"
    _, good = g.lib_kit(work, ["ok"])
    t("kit: copies + LICENSES.md", good and (work / "vendor" / "ok" / "ok.min.js").is_file() and (work / "vendor" / "LICENSES.md").is_file())
    _, good = g.lib_kit(work, ["out"])
    t("kit: refuses a file outside the library roots", not good and not (work / "vendor" / "out").exists())
    # kit + ES module (golden_tools follows relative imports since 2026-11-14): three.module.js -> three.core.js comes along,
    # and an import above the module's own folder is a failure that copies nothing
    (root / "m" / "util").mkdir(parents=True)
    (root / "m" / "lib.module.js").write_text("import {a} from './core.js';\n", encoding="utf-8")
    (root / "m" / "core.js").write_text("export * from \"./util/x.js\";\nexport const a = 1;\n", encoding="utf-8")
    (root / "m" / "util" / "x.js").write_text("export const x = 2;\n", encoding="utf-8")
    (root / "n").mkdir()
    (root / "n" / "n.module.js").write_text("import '../ok/ok.min.js';\n", encoding="utf-8")
    for i, f in (("m", root / "m" / "lib.module.js"), ("n", root / "n" / "n.module.js")):
        fake_lib["items"].append({"id": i, "name": i, "offline_entry": str(f), "offline_kind": "esm",
                                  "license": "MIT", "commercial_ok": "yes", "source": "test"})
    _, good = g.lib_kit(work, ["m"])
    vm = work / "vendor" / "m"
    t("kit: ES module imports copied (core.js, util/x.js)", good and (vm / "core.js").is_file() and (vm / "util" / "x.js").is_file())
    out, good = g.lib_kit(work, ["n"])
    t("kit: ES module import above its folder = failure, not copied",
      not good and "../ok/ok.min.js" in out and not (work / "vendor" / "n" / "ok.min.js").exists())
    # speech sync: marks follow the words, Arabic spelling variants and a split word still match
    words = {"segments": [{"words": [{"word": w, "start": s, "end": e} for w, s, e in [
        ("اهلا", 0.5, 0.9), ("بيكم", 0.95, 1.4), ("في", 1.6, 1.7), ("الطائر", 1.75, 2.2), ("الذهبي", 2.25, 2.9),
        ("مع", 3.2, 3.35), ("عبد", 3.4, 3.6), ("الله", 3.62, 3.95)]]}]}
    wp = tmp / "words.json"
    wp.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    res, srt = g.speech_sync("@{hook!}أهلاً بيكم || @{gold}في الطائر الذهبي@{/gold} مع عبدالله", wp, fps=30)
    t("sync: moment on its word", res["moments"]["hook"]["t"] == 0.5 and res["moments"]["hook"]["f"] == 15)
    t("sync: range span", res["ranges"]["gold"]["start"] == 1.6 and res["ranges"]["gold"]["end"] == 2.9)
    t("sync: hamza + tanween + split word all matched", res["stats"]["matched"] == res["stats"]["script_words"] == 7)
    t("sync: two caption lines", len(res["captions"]) == 2 and srt.count("-->") == 2)
    t("protocol: 10 rules", sum(1 for ln in PROTOCOL.splitlines() if re.match(r"\d+\. ", ln)) == 10)
    total = ok + len(bad)
    print(f"{ok}/{total} golden-bird checks" + (f" · فشل: {', '.join(bad)}" if bad else ""))
    return 0 if not bad else 1


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == "protocol":
        print(PROTOCOL)
        return 0
    if argv[0] == "where":
        return where()
    if argv[0] == "selftest":
        return selftest()
    if argv[:2] == ["studio", "install"]:
        if "--yes" not in argv:      # unpacking writes a program onto the PC: the owner says yes first (same rule as skills install)
            ident = next((a for a in argv[2:] if not a.startswith("--")), "ID")
            print(f"هيتعمل: فحص بصمة أرشيف «{ident}» ثم فكّه بـ 7-Zip في {gt().STUDIO_HOME} (مفيش أي برنامج بيتشغّل).\n"
                  f"بعد موافقة صاحب الشغل: $R gold studio install {ident} --yes")
            return 3
        argv = [a for a in argv if a != "--yes"]
    return gt().main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
