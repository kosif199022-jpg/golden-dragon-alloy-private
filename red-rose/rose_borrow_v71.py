"""V71 «الاستعارات المتاحة»: one list of everything Red Rose can borrow for directing and montage.

Styles come from agent/style_registry_v70.json (via rose_styles_v70); tools, engines and machines come from
agent/tools_registry_v71.json. Availability is checked live (path exists / program on PATH). Read-only:
listing never runs, installs or downloads anything. Borrowing a tool means running its own documented command.
"""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
import rose_styles_v70 as styles

TOOLS = Path(__file__).resolve().parent / "agent" / "tools_registry_v71.json"


def tool_registry(path=TOOLS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))["tools"]
    ids = [t["id"] for t in data]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate tool id")
    return data


def available(detect: str) -> bool:
    kind, _, ref = detect.partition(":")
    if kind == "which":
        return shutil.which(ref) is not None
    if kind == "path":
        return Path(ref.replace("~", str(Path.home()), 1) if ref.startswith("~") else ref).exists()
    raise ValueError(f"bad detect '{detect}'")


def _words(text):
    return [w for w in re.findall(r"[^\W_]{2,}", text.casefold())]


def _match(words, *fields):
    hay = " ".join(f for f in fields if f).casefold()
    return sum(1 for w in words if w in hay)


def borrow(kind="all", for_text=None, style_reg=None, tools=None, lib=styles.LIB, tested=None):
    if kind not in ("all", "styles", "tools"):
        raise ValueError("kind must be all|styles|tools")
    words = _words(for_text) if for_text else []
    out = {"styles": [], "tools": []}
    if kind in ("all", "styles"):
        tested = tested if tested is not None else styles.tests()
        for s in (style_reg if style_reg is not None else styles.registry()):
            score = _match(words, s["name_ar"], s["name_en"], s["best_for"], s["family"], " ".join(s.get("substyles", [])))
            if words and not score:
                continue
            out["styles"].append({"id": s["id"], "name_ar": s["name_ar"], "family": s["family"], "best_for": s["best_for"],
                                  "install": styles.install_state(s, lib), "substyles": s.get("substyles", []),
                                  "render_test": tested.get(s["id"], {}).get("status", "not_tested_here"), "score": score})
    if kind in ("all", "tools"):
        for t in (tools if tools is not None else tool_registry()):
            score = _match(words, t["name_ar"], t["best_for"], t["id"], t["kind"])
            if words and not score:
                continue
            out["tools"].append({"id": t["id"], "name_ar": t["name_ar"], "kind": t["kind"], "best_for": t["best_for"],
                                 "available": available(t["detect"]), "use": t["use"], "score": score})
    for k in out:
        out[k].sort(key=lambda x: -x["score"])
    return {"query": for_text, "styles": len(out["styles"]), "tools": len(out["tools"]), **{"list_" + k: v for k, v in out.items()},
            "execution_allowed": False,
            "note": "Read the chosen style/tool doc before running it; third-party engines need the owner's OK to run."}


def handle(a):
    try:
        print(json.dumps(borrow(a.kind, a.for_text), ensure_ascii=False, indent=1 if a.pretty else None))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)[:300]}, ensure_ascii=False))
        return 1


def register(sub):
    p = sub.add_parser("borrow", help="V71 available borrowings: styles + tools/engines/machines (read-only)")
    p.add_argument("--kind", default="all", choices=["all", "styles", "tools"])
    p.add_argument("--for", dest="for_text", help="filter by the owner's words")
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(ext_func=handle)
