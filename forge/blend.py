"""The blender: melt the whole golden-dragon repository into one skill (golden-dragon-alloy).

    python -I -X utf8 forge/blend.py --src <git checkout of main> --out <alloy root> [--branches take.json] [--skip-copy]

What it does (never executes anything from the source; reads files and git objects only):
 1. runtime/  = byte-identical copy of every tracked file of main (the engine room keeps its own
               manifests, selftest and paths, so the hook, the app and old commands keep working).
 2. branches/ = files taken from unmerged branches (from the reviewed take-list), under their branch name.
 3. kb/alloy.db = ONE knowledge base: every document (679 SKILL.md, references, modules, mind), the fused
               index (1101), the engine catalog (22k), roads (38 playbooks x 43 recipes), lessons, rules,
               thinking tools and runnable scripts, Arabic-normalised FTS5, with provenance, licence, status.
               Exact duplicates become one unit with many sources; same-name versions keep the newest
               active and mark the rest superseded; near-duplicate rules/lessons are merged, never dropped.
 4. ledger    = every source file -> where it went (100% coverage is a selftest gate).
 5. references/*.md digests (ROADS, RULES, LESSONS, THINKING, CAPABILITIES, MAP, BLEND_REPORT) + MANIFEST.json.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import alloy  # noqa: E402  (norm(), VERSION)

norm = alloy.norm
USER_HOME_RX = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+cinde", re.I)


def lp(p: Path) -> str:
    """Long-path-safe string for Windows file APIs."""
    s = str(p.resolve()) if not str(p).startswith("\\\\?\\") else str(p)
    return "\\\\?\\" + s if os.name == "nt" and not s.startswith("\\\\?\\") else s


def read_bytes(p: Path) -> bytes:
    with open(lp(p), "rb") as f:
        return f.read()


def decode(b: bytes) -> str:
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        return b.decode("utf-16", errors="replace")
    return b.decode("utf-8-sig", errors="replace")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sanitize(s: str | None) -> str:
    return USER_HOME_RX.sub("~", s or "")


def git(src: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(src), "-c", "core.quotepath=false", *args],
                          capture_output=True, check=True).stdout


# ----------------------------------------------------------------------------- front matter / text helpers
FM_RX = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.S)


def frontmatter(text: str) -> tuple[dict, str]:
    m = FM_RX.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if mm:
            key, val = mm.group(1).lower(), mm.group(2).strip()
            if val in (">", "|", ">-", "|-", ">+", "|+"):
                block = []
                i += 1
                while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                    block.append(lines[i].strip())
                    i += 1
                fm[key] = " ".join(x for x in block if x)
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            fm[key] = val
        i += 1
    return fm, text[m.end():]


def first_heading(text: str) -> str:
    m = re.search(r"^#{1,3}\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def first_paragraph(text: str, limit: int = 400) -> str:
    for block in re.split(r"\n\s*\n", text):
        b = block.strip()
        if not b or b.startswith(("#", "```", "|", "<!--", "---")):
            continue
        b = re.sub(r"\s+", " ", b)
        return b[:limit]
    return ""


def grams(s: str, n: int = 3) -> set[str]:
    s = re.sub(r"\s+", " ", norm(s))
    s = re.sub(r"[`*_>#\-\[\]()«»\"'.,:;!?،؛]", "", s)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def bullets(section: str) -> list[str]:
    """Top-level '- ' bullets of a markdown section, each joined with its continuation lines."""
    out, cur = [], None
    for ln in section.splitlines():
        if re.match(r"^- ", ln):
            if cur:
                out.append(cur.strip())
            cur = ln[2:]
        elif cur is not None and (ln.startswith("  ") or ln.startswith("\t")) and ln.strip():
            cur += "\n" + ln.rstrip()
        elif cur is not None and not ln.strip():
            out.append(cur.strip())
            cur = None
        elif cur is not None:
            out.append(cur.strip())
            cur = None
    if cur:
        out.append(cur.strip())
    return [b for b in out if len(b) > 8]


def sections(text: str, level: str = "## ") -> list[tuple[str, str]]:
    parts = re.split(rf"(?m)^{re.escape(level)}", text)
    out = []
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        out.append((title.strip(), body))
    return out


# ----------------------------------------------------------------------------- licence detection
LICENSE_RX = [("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
              ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
              ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
              ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
              ("BSD", r"Redistribution and use in source and binary forms"),
              ("CC-BY", r"Creative Commons Attribution"),
              ("ISC", r"\bISC License\b")]


def skill_root(rel_dir: str) -> str:
    """The skill folder a file belongs to (licence and SOURCE.json live there, not in references/)."""
    p = rel_dir.split("/")
    if p[:1] == ["library"] and len(p) >= 2:
        return "/".join(p[:2])
    if p[:3] == ["engine", "skills", "library"] and len(p) >= 4:
        return "/".join(p[:4])
    if p[:2] == ["engine", "skills"] and len(p) >= 3:
        return "/".join(p[:3])
    return rel_dir


def licence_for(skill_dir: Path, rel_dir: str, cache: dict) -> tuple[str, str]:
    """(licence, origin) for a skill directory. Owner content unless it lives in a third-party library."""
    if rel_dir in cache:
        return cache[rel_dir]
    third = rel_dir.startswith("library/") or "/library/" in rel_dir or rel_dir.startswith("engine/skills/library/")
    lic = ""
    src_json = skill_dir / "SOURCE.json"
    try:
        if os.path.exists(lp(src_json)):
            sj = json.loads(decode(read_bytes(src_json)))
            lic = str(sj.get("license") or sj.get("licence") or "")
            if sj.get("repo") or sj.get("url") or sj.get("source"):
                third = True
    except Exception:
        pass
    if not lic:
        for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING"):
            f = skill_dir / name
            if os.path.exists(lp(f)):
                t = decode(read_bytes(f))[:4000]
                lic = next((k for k, rx in LICENSE_RX if re.search(rx, t, re.I)), "see LICENSE")
                third = True
                break
    res = (lic or ("unknown" if third else "owner"), "third-party" if third else "owner")
    cache[rel_dir] = res
    return res


# ----------------------------------------------------------------------------- the blend
class Blend:
    def __init__(self, src: Path, out: Path):
        self.src, self.out = src, out
        self.units: dict[str, dict] = {}
        self.ledger: dict[str, dict] = {}
        self.conflicts: list[dict] = []
        self.report: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.lic_cache: dict = {}

    # -------------------------------------------------------------- units
    def add(self, uid: str, kind: str, title: str, summary: str = "", body: str = "", path: str = "",
            sources: list | None = None, how: str = "", license: str = "", status: str = "active",
            origin: str = "owner", meta: dict | None = None, index_text: str = "") -> dict:
        u = self.units.get(uid)
        if u:  # merge, never lose a source
            u["sources"].extend(s for s in (sources or []) if s not in u["sources"])
            if meta:
                u["meta"].update({k: v for k, v in meta.items() if k not in u["meta"]})
            if index_text:
                u["index_extra"] += " " + index_text
            return u
        u = {"id": uid, "kind": kind, "title": title or uid, "summary": summary or "", "body": body or "",
             "path": path, "sources": list(sources or []), "how": how, "license": license, "status": status,
             "origin": origin, "meta": dict(meta or {}), "index_extra": index_text or ""}
        self.units[uid] = u
        return u

    def led(self, path: str, place: str, unit_id: str | None = None, note: str = "", sha256: str = "", size: int = 0):
        e = self.ledger.setdefault(path, {"path": path, "sha256": sha256, "size": size, "place": place,
                                          "units": [], "note": note})
        if unit_id and unit_id not in e["units"]:
            e["units"].append(unit_id)
        if note and note not in e["note"]:
            e["note"] = (e["note"] + "; " + note).strip("; ")

    # -------------------------------------------------------------- 1) runtime copy
    def copy_runtime(self, files: list[str], skip_copy: bool) -> None:
        rt = self.out / "runtime"
        copied = same = 0
        self.file_sha: dict[str, str] = {}
        self.file_size: dict[str, int] = {}
        for f in files:
            s = self.src / f
            b = read_bytes(s)
            h = sha(b)
            self.file_sha[f], self.file_size[f] = h, len(b)
            d = rt / f
            if skip_copy and os.path.exists(lp(d)) and os.path.getsize(lp(d)) == len(b):
                same += 1
            else:
                os.makedirs(lp(d.parent), exist_ok=True)
                with open(lp(d), "wb") as fh:
                    fh.write(b)
                copied += 1
            self.led(f, f"runtime/{f}", sha256=h, size=len(b))
        self.report["runtime_files"] = len(files)
        self.report["runtime_bytes"] = sum(self.file_size.values())
        self.report["runtime_copied"] = copied
        lines = "".join(f"{p}\t{self.file_sha[p]}\n" for p in sorted(files))
        self.report["runtime_digest"] = sha(lines.encode("utf-8"))

    # -------------------------------------------------------------- 2) documents
    def ingest_docs(self, files: list[str], prefix: str = "runtime/", origin_tag: str = "", base: Path | None = None):
        base = base or self.src
        by_sha: dict[str, list[str]] = defaultdict(list)
        for f in files:
            if f.lower().endswith((".md", ".markdown")):
                by_sha[self.file_sha.get(f) or sha(read_bytes(base / f))].append(f)
        skills_by_name: dict[str, list[dict]] = defaultdict(list)
        n_docs = 0
        for h, paths in by_sha.items():
            paths.sort(key=lambda p: (p.count("/"), p))
            p0 = paths[0]
            text = decode(read_bytes(base / p0))
            fm, body = frontmatter(text)
            name = os.path.basename(p0)
            rel_dir = os.path.dirname(p0)
            root_dir = skill_root(rel_dir)
            lic, origin = licence_for(base / root_dir, root_dir, self.lic_cache)
            if origin_tag:
                origin = origin_tag if origin == "owner" else f"{origin_tag}+{origin}"
            if p0.startswith("mind/chats/") or p0.endswith("RD_CHATS_MEMORY.md"):
                kind = "memory"
            elif name == "SKILL.md" or name.endswith("SKILL_white.md"):
                kind = "skill"
            elif name == "MODULE.md":
                kind = "module"
            else:
                kind = "reference"
            title = fm.get("name") or first_heading(body) or name
            summary = fm.get("description") or first_paragraph(body)
            srcs = [{"path": prefix + p, "sha": h[:16]} for p in paths]
            if kind == "skill":
                sname = (fm.get("name") or os.path.basename(rel_dir) or "skill").strip().lower()
                skills_by_name[sname].append({"paths": paths, "text": text, "fm": fm, "summary": summary,
                                              "lic": lic, "origin": origin, "sha": h, "srcs": srcs})
                continue
            uid = f"doc:{prefix}{p0}" if prefix != "runtime/" else f"doc:{p0}"
            self.add(uid, kind, title, summary, text, prefix + p0, srcs, license=lic, origin=origin,
                     status="private" if kind == "memory" else "active",
                     meta={"version": fm.get("version")} if fm.get("version") else None)
            for p in paths:
                self.led(self.lkey(p, prefix), prefix + p, uid, note="" if p == p0 else f"exact duplicate of {p0}")
            n_docs += 1
        # skills: one unit per name; differing versions -> newest active, others superseded
        for sname, versions in skills_by_name.items():
            if len(versions) > 1:
                for v in versions:
                    v["ts"] = max(self.last_commit(p, base) for p in v["paths"])
                    v["len"] = len(v["text"])
                versions.sort(key=lambda v: (v["ts"], v["len"]), reverse=True)
                self.conflicts.append({"kind": "skill-version", "name": sname,
                                       "kept": versions[0]["paths"][0],
                                       "superseded": [v["paths"][0] for v in versions[1:]],
                                       "rule": "newest last-commit wins; ties -> longer text; older kept as superseded"})
            for i, v in enumerate(versions):
                uid = f"skill:{sname}" if i == 0 else f"skill:{sname}@{v['paths'][0].rsplit('/SKILL', 1)[0]}"
                if origin_tag and i == 0 and f"skill:{sname}" in self.units:
                    uid = f"skill:{sname}@{prefix.rstrip('/')}"
                p0 = v["paths"][0]
                body_fm, body = frontmatter(v["text"])
                self.add(uid, "skill", v["fm"].get("name") or sname, v["summary"], v["text"], prefix + p0, v["srcs"],
                         how=f"اقرا {prefix}{p0}", license=v["lic"], origin=v["origin"],
                         status="active" if i == 0 else "superseded",
                         meta={k: v["fm"][k] for k in ("version", "license", "metadata") if k in v["fm"]} |
                              ({"superseded_by": f"skill:{sname}"} if i else {}))
                for p in v["paths"]:
                    self.led(self.lkey(p, prefix), prefix + p, uid, note="" if p == p0 else f"exact duplicate of {p0}")
                n_docs += 1
        self.report.setdefault("doc_units", 0)
        self.report["doc_units"] += n_docs
        self.report.setdefault("doc_files", 0)
        self.report["doc_files"] += sum(len(v) for v in by_sha.values())

    def lkey(self, p: str, prefix: str) -> str:
        """Ledger key: the path in main, or branch:<name>:<path> for files taken from a branch."""
        return p if prefix == "runtime/" else f"branch:{self._cur_branch}:{p}"

    _cur_branch = ""

    def last_commit(self, path: str, base: Path) -> int:
        try:
            return int(git(base, "log", "-1", "--format=%ct", "--", path).decode().strip() or 0)
        except Exception:
            return 0

    # -------------------------------------------------------------- 3) structured knowledge
    def jload(self, rel: str):
        return json.loads(decode(read_bytes(self.src / rel)))

    def ingest_roads(self):
        pbs = self.jload("mind/playbooks.json")["playbooks"]
        recipes = {r["id"]: r for r in self.jload("apps/golden-dragon/app/fusion/recipes.json")}
        overlay = self.jload("mind/fusion_overlay.json")
        for r in overlay.get("recipes", []):
            recipes.setdefault(r["id"], r)
        rd_map = dict(self.jload("apps/golden-dragon/app/fusion/rd_map.json"))
        for k, v in (overlay.get("rd_map") or {}).items():
            rd_map.setdefault(k, [])
            rd_map[k] = list(dict.fromkeys([*rd_map[k], *(v if isinstance(v, list) else [v])]))
        # route examples: dev split only (odd ids are the hidden test split of mind/route_eval)
        examples: dict[str, list[str]] = defaultdict(list)
        n_ex = n_test = 0
        for ln in decode(read_bytes(self.src / "mind/route_examples.jsonl")).splitlines():
            if not ln.strip():
                continue
            e = json.loads(ln)
            m = re.match(r"^(old|fresh):(\d+)", str(e.get("src", "")))
            if m and int(m.group(2)) % 2 == 1:
                n_test += 1
                continue
            examples[e.get("pb", "")].append(e["q"])
            n_ex += 1
        self.report["route_examples_used"] = n_ex
        self.report["route_examples_hidden_test"] = n_test
        used = set()

        def recipe_md(r: dict) -> str:
            out = [f"### وصفة عقل الانصهار: {r.get('title_ar', r['id'])} (`{r['id']}`)"]
            if r.get("when"):
                out.append("- بتتفعّل لما: " + " · ".join(r["when"]))
            for i, s in enumerate(r.get("steps", []), 1):
                bits = [s.get("do_ar", "")]
                if s.get("read"):
                    bits.append("اقرا: " + ", ".join(s["read"]))
                if s.get("use"):
                    bits.append("استخدم: " + ", ".join(s["use"]))
                if s.get("gate_ar"):
                    bits.append("البوابة: " + s["gate_ar"])
                out.append(f"{i}. " + " — ".join(b for b in bits if b))
            if r.get("deliver_ar"):
                out.append(f"- التسليم: {r['deliver_ar']}")
            if r.get("approvals_ar"):
                ap = r["approvals_ar"]
                out.append("- الموافقات: " + (" · ".join(ap) if isinstance(ap, list) else str(ap)))
            return "\n".join(out)

        for pb in pbs:
            rid = pb["id"]
            mapped = [recipes[x] for x in rd_map.get(rid, []) if x in recipes]
            used.update(x["id"] for x in mapped)
            md = [f"# {pb.get('ar', rid)} — {pb.get('en', '')}",
                  f"- الطريق: `{rid}` · المجال: {pb.get('domain', '')} · الوصفات المنصهرة: "
                  + (", ".join(f"`{m['id']}`" for m in mapped) or "—"),
                  f"- بيتفعّل بكلام زي: {pb.get('triggers', '')}"]
            if pb.get("phrases"):
                md.append("- عبارات: " + " · ".join(pb["phrases"] if isinstance(pb["phrases"], list) else [pb["phrases"]]))
            if pb.get("ask"):
                ask = pb["ask"]
                md.append("\n## اسأل قبل ما تبدأ (لو مش معروف من الملفات)\n" +
                          "\n".join(f"- {a}" for a in (ask if isinstance(ask, list) else [ask])))
            md.append("\n## الخطوات (طريق العقل المقاس)\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(pb.get("steps", []), 1)))
            for m in mapped:
                md.append("\n" + recipe_md(m))
            if pb.get("gates"):
                g = pb["gates"]
                md.append("\n## بوابات قبل التسليم\n" + "\n".join(f"- {x}" for x in (g if isinstance(g, list) else [g])))
            if pb.get("pitfalls"):
                p = pb["pitfalls"]
                md.append("\n## مطبات اتعلّمناها\n" + "\n".join(f"- {x}" for x in (p if isinstance(p, list) else [p])))
            if pb.get("skills") or pb.get("powers"):
                md.append("\n## المهارات والقدرات\n- مهارات: " + ", ".join(pb.get("skills") or []) +
                          "\n- قدرات: " + ", ".join(pb.get("powers") or []))
            ex = examples.get(rid, [])
            if ex:
                md.append("\n## طلبات حقيقية راحت للطريق ده\n" + "\n".join(f"- {q}" for q in ex[:12]))
            index = " ".join([pb.get("ar", ""), pb.get("en", ""), pb.get("triggers", ""),
                              " ".join(pb.get("phrases") or []) if isinstance(pb.get("phrases"), list) else str(pb.get("phrases") or ""),
                              *[" ".join(m.get("when", [])) + " " + " ".join(m.get("tags", [])) + " " + m.get("title_ar", "")
                                for m in mapped], " ".join(ex)])
            self.add(f"road:{rid}", "road", pb.get("ar", rid), pb.get("en", ""), "\n".join(md),
                     "references/ROADS.md", [{"ref": "mind/playbooks.json#" + rid},
                                             *[{"ref": "apps/golden-dragon/app/fusion/recipes.json#" + m["id"]} for m in mapped]],
                     how=f'alloy route "<الطلب>"  (الطريق {rid})', meta={"domain": pb.get("domain"),
                                                                       "recipes": [m["id"] for m in mapped]},
                     index_text=index)
        for rid, r in recipes.items():
            if rid in used:
                continue
            self.add(f"road:{rid}", "road", r.get("title_ar", rid), " · ".join(r.get("when", [])[:2]),
                     f"# {r.get('title_ar', rid)}\n- وصفة من غير طريق مقابل في العقل المقاس.\n\n" + recipe_md(r),
                     "references/ROADS.md", [{"ref": "apps/golden-dragon/app/fusion/recipes.json#" + rid}],
                     meta={"recipe_only": True},
                     index_text=" ".join(r.get("when", [])) + " " + " ".join(r.get("tags", [])))
        self.report["roads"] = sum(1 for u in self.units.values() if u["kind"] == "road")
        self.report["playbooks"] = len(pbs)
        self.report["recipes"] = len(recipes)
        for rel in ("mind/playbooks.json", "apps/golden-dragon/app/fusion/recipes.json", "mind/fusion_overlay.json",
                    "apps/golden-dragon/app/fusion/rd_map.json", "mind/route_examples.jsonl"):
            self.led(rel, f"runtime/{rel}", "road:*", note="blended into roads")

    def ingest_lessons(self):
        items = []
        seen_ids: Counter = Counter()
        for ln in decode(read_bytes(self.src / "mind/lessons_seed.jsonl")).splitlines():
            if ln.strip():
                e = json.loads(ln)
                seen_ids[e["id"]] += 1
                if seen_ids[e["id"]] > 1:  # the seed repeats an id (s09): keep both, never overwrite
                    e["id"] = f"{e['id']}-{seen_ids[e['id']]}"
                items.append({"id": f"lesson:{e['id']}", "text": e.get("text", ""), "title": e.get("trigger", ""),
                              "domain": e.get("domain", ""), "prio": int(e.get("seen") or 1),
                              "src": "mind/lessons_seed.jsonl#" + e["id"], "extra": {"seen": e.get("seen")}})
        for e in self.jload("apps/golden-dragon/app/fusion/lessons.json"):
            sev = {"high": 3, "critical": 4, "medium": 2, "low": 1}.get(str(e.get("severity", "")).lower(), 2)
            items.append({"id": f"lesson:{e['id']}", "text": e.get("lesson_ar", "") + (
                f"\n(EN) {e['rule_en']}" if e.get("rule_en") else ""), "title": e.get("lesson_ar", "")[:70],
                          "domain": e.get("domain", ""), "prio": sev + 1, "src": "apps/golden-dragon/app/fusion/lessons.json#" + e["id"],
                          "extra": {"severity": e.get("severity"), "evidence": e.get("evidence")}})
        merged = self.merge_near(items, 0.55, "lesson")
        for it in items:
            self.add(it["id"], "lesson", it["title"] or it["text"][:70], it["text"][:300], it["text"], "references/LESSONS.md",
                     [{"ref": it["src"]}], status="merged" if it["id"] in merged else "active",
                     meta={"domain": it["domain"], **it["extra"], **({"merged_into": merged[it["id"]]} if it["id"] in merged else {})})
        self.report["lessons_in"] = len(items)
        self.report["lessons_merged"] = len(merged)
        for rel in ("mind/lessons_seed.jsonl", "apps/golden-dragon/app/fusion/lessons.json"):
            self.led(rel, f"runtime/{rel}", "lesson:*", note="blended into lessons")

    def merge_near(self, items: list[dict], thr: float, label: str) -> dict:
        """Mark near-duplicates (char-3-gram Jaccard >= thr) as merged into the higher-priority item."""
        g = [grams(it["text"]) for it in items]
        merged: dict[str, str] = {}
        order = sorted(range(len(items)), key=lambda i: -items[i]["prio"])
        canon: list[int] = []
        for i in order:
            best, bj = None, 0.0
            for c in canon:
                if items[c]["id"] == items[i]["id"]:
                    continue
                j = jaccard(g[i], g[c])
                if j > bj:
                    best, bj = c, j
            if best is not None and bj >= thr:
                merged[items[i]["id"]] = items[best]["id"]
                self.conflicts.append({"kind": f"{label}-near-duplicate", "kept": items[best]["id"],
                                       "merged": items[i]["id"], "similarity": round(bj, 3)})
            else:
                canon.append(i)
        return merged

    def ingest_rules(self):
        items = []
        rd = decode(read_bytes(self.src / "references/RD_RULES.md"))
        for title, body in sections(rd):
            for k, b in enumerate(bullets(body), 1):
                items.append({"id": f"rule:rd-{title.split('.')[0].strip()}-{k}", "text": b, "topic": title,
                              "prio": 5, "src": f"references/RD_RULES.md#{title}"})
        boot = decode(read_bytes(self.src / "BOOT.md"))
        for title, body in sections(boot):
            if title.startswith(("4)", "5)")):
                for k, b in enumerate(bullets(body), 1):
                    items.append({"id": f"rule:boot-{title[0]}-{k}", "text": b,
                                  "topic": "لكل طلب (BOOT §4)" if title.startswith("4") else "التحديث والرفع (BOOT §5)",
                                  "prio": 4, "src": f"BOOT.md#{title}"})
        eng = decode(read_bytes(self.src / "engine/SKILL.md"))
        for title, body in sections(eng):
            if title.startswith("11.") or title.startswith("⛔"):
                bl = bullets(body) or [re.sub(r"\s+", " ", body.strip())[:900]]
                for k, b in enumerate(bl, 1):
                    items.append({"id": f"rule:engine-{len(items)}", "text": b, "topic": "المحرك: " + title,
                                  "prio": 3, "src": f"engine/SKILL.md#{title}"})
        ult = decode(read_bytes(self.src / "modules/ultra/MODULE.md"))
        for title, body in sections(ult):
            if title.startswith("3."):
                for k, b in enumerate(bullets(body), 1):
                    items.append({"id": f"rule:ultra-{k}", "text": b, "topic": "الفائق: " + title, "prio": 2,
                                  "src": f"modules/ultra/MODULE.md#{title}"})
        wd = decode(read_bytes(self.src / "legacy/white-dragon/references/WD_RULES.md"))
        for k, b in enumerate(bullets(wd), 1):
            items.append({"id": f"rule:wd-{k}", "text": b, "topic": "التنين الأبيض", "prio": 1,
                          "src": "legacy/white-dragon/references/WD_RULES.md"})
        merged = self.merge_near(items, 0.5, "rule")
        for it in items:
            self.add(it["id"], "rule", it["topic"], it["text"][:300], it["text"], "references/RULES.md",
                     [{"ref": it["src"]}], status="merged" if it["id"] in merged else "active",
                     meta={"topic": it["topic"], **({"merged_into": merged[it["id"]]} if it["id"] in merged else {})})
        self.rule_items = items
        self.report["rules_in"] = len(items)
        self.report["rules_merged"] = len(merged)

    def ingest_thinking(self):
        t = self.jload("apps/golden-dragon/app/fusion/thinking.json")
        old = {x["id"] for x in self.jload("apps/golden-dragon/analysis/thinking_toolkit.json")["tools"]}
        for x in t["tools"]:
            body = [f"# {x.get('name_ar', x['id'])}", f"- id: `{x['id']}`"]
            if x.get("use_when"):
                body.append(f"- إمتى: {x['use_when']}")
            if x.get("steps_ar"):
                body.append("\n## الخطوات\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(x["steps_ar"], 1)))
            if x.get("check_ar"):
                body.append(f"\n## سؤال الناقد\n- {x['check_ar']}")
            if x.get("source"):
                src = x["source"] if isinstance(x["source"], list) else [x["source"]]
                body.append("\n## المصدر\n" + "\n".join(f"- {sanitize(s)}" for s in src))
            srcs = [{"ref": "apps/golden-dragon/app/fusion/thinking.json#" + x["id"]}]
            if x["id"] in old:
                srcs.append({"ref": "apps/golden-dragon/analysis/thinking_toolkit.json#" + x["id"]})
            uw = x.get("use_when")
            uw = " · ".join(map(str, uw)) if isinstance(uw, list) else str(uw or "")
            self.add(f"thinking:{x['id']}", "thinking", x.get("name_ar", x["id"]), uw[:300],
                     "\n".join(body), "references/THINKING.md", srcs,
                     meta={"from_books": x.get("from_books"), "trigger_words": x.get("trigger_words")},
                     index_text=" ".join(x.get("trigger_words") or []) if isinstance(x.get("trigger_words"), list) else str(x.get("trigger_words") or ""))
        for p in t.get("paths") or []:
            self.add(f"thinking:path-{p.get('id')}", "thinking", p.get("name_ar", p.get("id")),
                     json.dumps({k: v for k, v in p.items() if k not in ("name_ar",)}, ensure_ascii=False)[:300],
                     json.dumps(p, ensure_ascii=False, indent=1), "references/THINKING.md",
                     [{"ref": "apps/golden-dragon/app/fusion/thinking.json#paths"}], meta={"path": True})
        self.thinking_protocol = t.get("protocol_ar") or []
        self.report["thinking_tools"] = len(t["tools"])
        self.report["thinking_paths"] = len(t.get("paths") or [])
        self.report["thinking_old_subset"] = len(old)
        for rel in ("apps/golden-dragon/app/fusion/thinking.json", "apps/golden-dragon/analysis/thinking_toolkit.json"):
            self.led(rel, f"runtime/{rel}", "thinking:*", note="blended into thinking")

    def ingest_fusion_index(self):
        idx = self.jload("apps/golden-dragon/app/fusion/index.json")
        merged = new = 0
        for u in idx["units"]:
            kind, name = u.get("kind"), u.get("name") or u["id"].split(":", 1)[-1]
            meta = {k: u.get(k) for k in ("status", "cost", "family", "lang") if u.get(k)}
            meta["fusion_id"] = u["id"]
            if kind == "playbook":
                continue  # roads already carry every playbook
            sk = f"skill:{name.lower()}"
            if kind == "skill" and sk in self.units:
                self.add(sk, "skill", name, meta={"fusion": meta}, sources=[{"ref": "fusion:" + u["id"]}],
                         index_text=(u.get("what_ar") or "") + " " + (u.get("what") or ""))
                merged += 1
                continue
            uid = u["id"] if kind != "skill" else f"skill:{name.lower()}"
            self.add(uid, kind, name, u.get("what_ar") or u.get("what") or "", "", sanitize(u.get("path") or ""),
                     [{"ref": "fusion:" + u["id"]}], how=sanitize(u.get("how") or ""),
                     origin="installed-pc" if kind == "skill" else "fusion", meta=meta,
                     index_text=(u.get("what") or "") + " " + (u.get("family") or ""))
            new += 1
        self.report["fusion_units"] = len(idx["units"])
        self.report["fusion_merged_into_docs"] = merged
        self.report["fusion_new_units"] = new
        self.led("apps/golden-dragon/app/fusion/index.json", "runtime/apps/golden-dragon/app/fusion/index.json",
                 "fusion:*", note=f"{len(idx['units'])} units blended (merged {merged} into repo skills)")

    def ingest_catalog(self):
        con = sqlite3.connect(f"file:{(self.src / 'engine/app/data/catalog.sqlite').as_posix()}?mode=ro", uri=True)
        merged = new = 0
        names = {u["title"].lower(): u["id"] for u in self.units.values() if u["kind"] == "skill"}
        for (iid, kind, source, name, tar, ten, summ, path, status, command, req, extra) in con.execute(
                "SELECT id, kind, source, name, title_ar, title_en, summary, path, status, command, requires, extra FROM items"):
            meta = {"source": source, "status": status, "requires": req or None, "catalog_id": iid}
            if kind == "skill" and (name or "").lower() in names:
                self.add(names[name.lower()], "skill", name, meta={"catalog": meta}, sources=[{"ref": "catalog:" + iid}])
                merged += 1
                continue
            k = "catalog-skill" if kind == "skill" else kind
            self.add(f"catalog:{iid}", k, name or iid, (tar or ten or summ or "")[:400] if not summ else summ[:400],
                     "", sanitize(path), [{"ref": "catalog:" + iid}], how=sanitize(command or ""),
                     origin=f"catalog:{source}", meta=meta, index_text=" ".join(x for x in (tar, ten) if x))
            new += 1
        self.report["catalog_items"] = merged + new
        self.report["catalog_merged"] = merged
        self.led("engine/app/data/catalog.sqlite", "runtime/engine/app/data/catalog.sqlite", "catalog:*",
                 note=f"{merged + new} items blended")

    def ingest_scripts(self, files: list[str], prefix: str = "runtime/", origin_tag: str = "", base: Path | None = None):
        base = base or self.src
        n = 0
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in (".py", ".js", ".mjs", ".ps1", ".sh", ".cmd", ".bat"):
                continue
            low = f.lower()
            if "/tests/" in f"/{low}" or os.path.basename(low).startswith("test_") or "/vendor/" in f"/{low}" \
                    or "/node_modules/" in low or low.endswith(".min.js"):
                continue
            b = read_bytes(base / f)
            if len(b) > 600_000:
                continue
            text = decode(b)
            doc, runnable = "", False
            if ext == ".py":
                runnable = "__main__" in text or "argparse" in text
                try:
                    doc = ast.get_docstring(ast.parse(text)) or ""
                except Exception:
                    doc = ""
            else:
                runnable = ext in (".ps1", ".sh", ".cmd", ".bat") or "process.argv" in text
                lines = []
                for ln in text.splitlines()[:12]:
                    s = ln.strip()
                    if s.startswith(("#!", "'use strict'", '"use strict"')):
                        continue
                    if s.startswith(("#", "//", "REM ", "rem ", "::", "<#", "*", "/*")):
                        lines.append(s.lstrip("#/*:<> ").replace("REM ", ""))
                    elif s:
                        break
                doc = " ".join(x for x in lines if x)
            if not runnable:
                continue
            rel_dir = os.path.dirname(f)
            third = f.startswith("library/") or "/library/" in f
            origin = ("third-party" if third else "owner") if not origin_tag else origin_tag
            uid = f"script:{prefix + f if prefix != 'runtime/' else f}"
            self.add(uid, "script", os.path.basename(f), (doc.strip().splitlines() or [""])[0][:300] if doc else rel_dir,
                     doc[:3000], prefix + f, [{"path": prefix + f, "sha": sha(b)[:16]}],
                     how=f"alloy run {f if prefix == 'runtime/' else prefix + f}", origin=origin,
                     status="review-before-run" if third else "active", index_text=rel_dir.replace("/", " "))
            self.led(self.lkey(f, prefix), prefix + f, uid)
            n += 1
        self.report.setdefault("script_units", 0)
        self.report["script_units"] += n

    def quarantine(self):
        """Things that stay in the engine room but are kept out of active use (dragon rules §6)."""
        q = 0
        for u in self.units.values():
            p = (u.get("path") or "").lower()
            if "cookie" in p and ("library/cookie-copy" in p or u["id"].startswith("skill:cookie-copy")):
                u["status"] = "quarantined"
                u["meta"]["why"] = "browser cookie migration: dragon rule §6 (cookies/sessions never leave the owner's browser)"
                q += 1
        self.report["quarantined"] = q

    # -------------------------------------------------------------- branches
    def ingest_branches(self, take_file: Path | None):
        """Exact take-list from forge/take_branches.py: whole new files, staged patches, laptop-newer overrides."""
        if not take_file or not take_file.exists():
            self.report["branches"] = "no take-list"
            return
        data = json.loads(decode(read_bytes(take_file)))
        taken = []
        n_files = n_patches = 0
        for br in data:
            name = br["branch"].removeprefix("origin/")
            slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
            for path, why in br.get("skipped", []):
                self.led(f"branch:{name}:{path}", f"not-taken ({br['verdict']})", note=f"{why} · {(br.get('evidence') or '')[:240]}")
            files, patches = [], []
            for path in br.get("take", []):
                src_override = br.get("overrides", {}).get(path)
                b = read_bytes(Path(src_override)) if src_override else git(self.src, "show", f"origin/{name}:{path}")
                dest = self.out / "branches" / slug / path
                os.makedirs(lp(dest.parent), exist_ok=True)
                with open(lp(dest), "wb") as fh:
                    fh.write(b)
                files.append(path)
                note = f"from {name}@{br['sha']}" + (" (laptop-installed copy is newer: taken from it)" if src_override else "")
                self.led(f"branch:{name}:{path}", f"branches/{slug}/{path}", sha256=sha(b), size=len(b), note=note)
            for path in br.get("patch", []):
                diff = git(self.src, "diff", br["merge_base"], f"origin/{name}", "--", path)
                flat = path.replace("/", "__") + ".diff"
                dest = self.out / "branches" / slug / "PATCHES" / flat
                os.makedirs(lp(dest.parent), exist_ok=True)
                with open(lp(dest), "wb") as fh:
                    fh.write(diff)
                place = f"branches/{slug}/PATCHES/{flat}"
                uid = f"patch:{slug}:{path}"
                self.add(uid, "patch", f"{path} ← {name}", (br.get("adds") or "")[:300], decode(diff), place,
                         [{"ref": f"git:{name}@{br['sha']}:{path}"}], status="staged", origin=f"branch:{slug}",
                         how=f"git apply --3way {place}  (جوه نسخة من المستودع، وبعدين manifests + selftest)",
                         meta={"target": f"runtime/{path}", "warn": br.get("warn") or None})
                self.led(f"branch:{name}:{path}", place, uid, note="staged patch (not applied to runtime/)"
                         + (f" ⚠ {br['warn']}" if br.get("warn") else ""))
                patches.append(path)
            base = self.out / "branches" / slug
            self._cur_branch = name
            before = set(self.units)
            self.ingest_docs(files, prefix=f"branches/{slug}/", origin_tag=f"branch:{slug}", base=base)
            self.ingest_scripts(files, prefix=f"branches/{slug}/", origin_tag=f"branch:{slug}", base=base)
            # a newer branch version of something main already has: the branch one becomes the active unit
            for path in br.get("already_in_main", []):
                try:
                    t_b = int(git(self.src, "log", "-1", "--format=%ct", f"origin/{name}", "--", path).decode().strip() or 0)
                    t_m = int(git(self.src, "log", "-1", "--format=%ct", "origin/main", "--", path).decode().strip() or 0)
                except Exception:
                    continue
                if t_b <= t_m:
                    continue
                for uid in self.ledger.get(path, {}).get("units", []):
                    u = self.units.get(uid)
                    new = [x for x in set(self.units) - before
                           if any(s.get("path") == f"branches/{slug}/{path}" for s in self.units[x]["sources"])]
                    if u and new:
                        u["status"] = "superseded"
                        u["meta"]["superseded_by"] = new[0]
                        self.conflicts.append({"kind": "branch-newer", "path": path, "kept": new[0], "superseded": uid,
                                               "rule": "branch commit newer than main's last commit for the same path"})
            n_files += len(files)
            n_patches += len(patches)
            if files or patches:
                taken.append({"branch": name, "sha": br["sha"], "files": len(files), "patches": len(patches),
                              "laptop_newer": len(br.get("overrides", {})), "adds": br.get("adds", ""), "warn": br.get("warn", "")})
        self.report["branches_reviewed"] = len(data)
        self.report["branches_taken"] = taken
        self.report["branch_files"] = n_files
        self.report["branch_patches"] = n_patches

    # -------------------------------------------------------------- write KB
    def write_kb(self):
        kb = self.out / "kb" / "alloy.db"
        os.makedirs(lp(kb.parent), exist_ok=True)
        if kb.exists():
            kb.unlink()
        con = sqlite3.connect(str(kb))
        con.executescript("""
        CREATE TABLE units(id TEXT PRIMARY KEY, kind TEXT, title TEXT, summary TEXT, body BLOB, path TEXT,
                           sources TEXT, how TEXT, license TEXT, status TEXT, origin TEXT, meta TEXT);
        CREATE INDEX units_kind ON units(kind);
        CREATE VIRTUAL TABLE fts USING fts5(title, summary, body, content='', tokenize='unicode61 remove_diacritics 2');
        CREATE TABLE ledger(path TEXT PRIMARY KEY, sha256 TEXT, size INTEGER, place TEXT, units TEXT, note TEXT);
        CREATE TABLE conflicts(n INTEGER PRIMARY KEY, kind TEXT, payload TEXT);
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        """)
        for u in self.units.values():
            body = u["body"] or ""
            cur = con.execute("INSERT INTO units VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (u["id"], u["kind"], u["title"], u["summary"],
                               zlib.compress(body.encode("utf-8"), 9) if body else None,
                               u["path"], json.dumps(u["sources"], ensure_ascii=False), u["how"], u["license"],
                               u["status"], u["origin"], json.dumps(u["meta"], ensure_ascii=False, default=str)))
            heads = " ".join(re.findall(r"(?m)^#{1,4}\s+(.+)$", body))[:4000]
            idx_body = f"{body[:8000]} {heads} {u['index_extra']}"
            con.execute("INSERT INTO fts(rowid, title, summary, body) VALUES (?,?,?,?)",
                        (cur.lastrowid, norm(f"{u['title']} {u['id'].split(':', 1)[-1].replace('-', ' ')}"),
                         norm(u["summary"]), norm(idx_body)))
        for e in self.ledger.values():
            con.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?)", (e["path"], e["sha256"], e["size"], e["place"],
                                                                    ",".join(e["units"]), e["note"]))
        for i, c in enumerate(self.conflicts):
            con.execute("INSERT INTO conflicts VALUES (?,?,?)", (i, c["kind"], json.dumps(c, ensure_ascii=False)))
        meta = {"alloy_version": alloy.VERSION, "source": self.report.get("source"), "built": time.strftime("%Y-%m-%d %H:%M"),
                "units": len(self.units), "ledger": len(self.ledger)}
        for k, v in meta.items():
            con.execute("INSERT INTO meta VALUES (?,?)", (k, str(v)))
        con.commit()
        con.execute("INSERT INTO fts(fts) VALUES ('optimize')")
        con.commit()
        con.execute("VACUUM")
        con.close()
        self.report["kb_bytes"] = kb.stat().st_size
        self.report["units"] = len(self.units)
        self.report["units_by_kind"] = dict(Counter(u["kind"] for u in self.units.values()).most_common())
        self.report["units_by_status"] = dict(Counter(u["status"] for u in self.units.values()).most_common())
        self.report["units_by_origin"] = dict(Counter(u["origin"].split(":")[0] for u in self.units.values()).most_common())
        self.report["ledger_entries"] = len(self.ledger)
        self.report["conflicts"] = dict(Counter(c["kind"] for c in self.conflicts))

    # -------------------------------------------------------------- digests
    def write_digests(self):
        ref = self.out / "references"
        os.makedirs(lp(ref), exist_ok=True)

        def W(name: str, text: str) -> None:
            with open(lp(ref / name), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        roads = [u for u in self.units.values() if u["kind"] == "road"]
        roads.sort(key=lambda u: (u["meta"].get("recipe_only", False), u["id"]))
        W("ROADS.md", "# كتاب الطرق المنصهر — 38 طريق من العقل المقاس × وصفات عقل الانصهار\n\n"
          "> كل طريق هنا = playbook من `runtime/mind/playbooks.json` ومعاه الوصفات اللي `rd_map.json` بيربطها بيه، "
          "في مكان واحد. التوجيه نفسه: `alloy route \"<الطلب>\"`.\n\n"
          + "\n\n---\n\n".join(u["body"] for u in roads) + "\n")
        rules = [u for u in self.units.values() if u["kind"] == "rule"]
        by_topic: dict[str, list] = defaultdict(list)
        for u in rules:
            by_topic[u["meta"]["topic"]].append(u)
        out = ["# كتاب القواعد المنصهر\n",
               "> القواعد كانت مكتوبة في 5 أماكن: `RD_RULES.md`، `BOOT.md` §4–§5، `engine/SKILL.md` §11 و⛔، "
               "`modules/ultra` §3، و`WD_RULES.md`. هنا كلها في كتاب واحد. القاعدة اللي ليها نسخة شبه مطابقة في مكان تاني "
               "اتدمجت في الأقدم مصدرًا (RD_RULES أولًا) واتكتب جنبها «كمان في»، ومفيش قاعدة اتشالت.\n"]
        merged_into = defaultdict(list)
        for u in rules:
            if u["status"] == "merged":
                merged_into[u["meta"]["merged_into"]].append(u)
        for topic, us in by_topic.items():
            act = [u for u in us if u["status"] != "merged"]
            if not act:
                continue
            out.append(f"\n## {topic}\n")
            for u in act:
                also = merged_into.get(u["id"], [])
                tag = f"  _(`{u['sources'][0]['ref']}`" + (", كمان في: " + ", ".join(f"`{x['sources'][0]['ref']}`" for x in also) if also else "") + ")_"
                out.append(f"- {u['body'].strip()}\n{tag}")
        W("RULES.md", "\n".join(out) + "\n")
        lessons = [u for u in self.units.values() if u["kind"] == "lesson"]
        by_dom: dict[str, list] = defaultdict(list)
        for u in lessons:
            by_dom[u["meta"].get("domain") or "عام"].append(u)
        mi = defaultdict(list)
        for u in lessons:
            if u["status"] == "merged":
                mi[u["meta"]["merged_into"]].append(u["id"])
        out = ["# دفتر الدروس المنصهر\n",
               f"> {len(lessons)} درس من `mind/lessons_seed.jsonl` و`fusion/lessons.json`. الدرس المكرر اتدمج في الأعلى أولوية "
               "(الأخطر أو الأكتر تكرارًا) واتكتب رقمه جنبه. اللي اتعلّم على اللابتوب بعد كده بيتسجّل بـ `alloy learn` في `~/.red-dragon`.\n"]
        for dom in sorted(by_dom):
            act = [u for u in by_dom[dom] if u["status"] != "merged"]
            if not act:
                continue
            out.append(f"\n## {dom}\n")
            for u in act:
                extra = f" _(+ {', '.join(mi[u['id']])})_" if mi.get(u["id"]) else ""
                out.append(f"- **{u['id'].split(':', 1)[1]}** {u['body'].strip()}{extra}")
        W("LESSONS.md", "\n".join(out) + "\n")
        th = [u for u in self.units.values() if u["kind"] == "thinking"]
        W("THINKING.md", "# أدوات التفكير وسبله (44 أداة من كتب العلماء + 7 سبل)\n\n## السلّم\n"
          + "\n".join(f"- {sanitize(p)}" for p in self.thinking_protocol) + "\n\n"
          + "\n\n".join(u["body"] for u in sorted(th, key=lambda u: u["id"]) if not u["meta"].get("path"))
          + "\n\n## السبل السبعة (`alloy fusion think <السبيل>`)\n"
          + "\n".join(f"- {u['title']}: `{u['id']}`" for u in th if u["meta"].get("path")) + "\n")
        R = self.report
        kinds = R["units_by_kind"]
        W("CAPABILITIES.md", "# كل القدرات من باب واحد\n\n| النوع | العدد | إزاي توصله |\n|---|---|---|\n" +
          "\n".join(f"| {k} | {n} | `alloy find \"…\" --kind {k}` |" for k, n in kinds.items()) +
          "\n\n## المحركات\n| الأمر | بيشغّل |\n|---|---|\n" +
          "\n".join(f"| `alloy {k} …` | `{p.relative_to(ROOT).as_posix()}` |" for k, p in alloy.ENGINES.items()) +
          "\n\n- أي أمر من `rd.py` (plan، brief، check، consent، learn، teach، think، understand، chats، files، md، sync، ref، arena، "
          "insta، ig، krita، hypit، gold، x…) بيعدّي من `alloy` على طول، زي `alloy plan \"<الطلب>\"`.\n"
          "- أي سكربت: `alloy run <مسار جوه runtime/> [args]` (سكربتات المكتبة بتطلب `--yes` بعد ما تقراها).\n")
        self.report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        json.dump(self.report, open(lp(self.out / "ledger" / "blend_report.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
        json.dump(self.conflicts, open(lp(self.out / "ledger" / "conflicts.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    def write_ledger_file(self):
        os.makedirs(lp(self.out / "ledger"), exist_ok=True)
        with open(lp(self.out / "ledger" / "sources.jsonl"), "w", encoding="utf-8", newline="\n") as f:
            for e in sorted(self.ledger.values(), key=lambda e: e["path"]):
                f.write(json.dumps(e, ensure_ascii=False) + "\n")


def write_manifest(out: Path, report: dict) -> dict:
    files = {}
    for dp, dn, fn in os.walk(lp(out)):
        rel_dir = os.path.relpath(dp, lp(out)).replace("\\", "/")
        if rel_dir == "runtime" or rel_dir.startswith("runtime/") or "__pycache__" in rel_dir:
            dn[:] = []
            continue
        for n in fn:
            rel = (n if rel_dir == "." else f"{rel_dir}/{n}")
            if rel == "MANIFEST.json":
                continue
            b = read_bytes(Path(dp) / n)
            files[rel] = {"bytes": len(b), "sha256": sha(b)}
    man = {"name": "golden-dragon-alloy", "version": alloy.VERSION, "source": report.get("source"),
           "runtime_files": report.get("runtime_files"), "runtime_digest": report.get("runtime_digest"),
           "files": dict(sorted(files.items()))}
    with open(lp(out / "MANIFEST.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--branches", type=Path)
    ap.add_argument("--skip-copy", action="store_true")
    ap.add_argument("--manifest-only", action="store_true", help="only rewrite MANIFEST.json (after editing SKILL.md etc.)")
    a = ap.parse_args()
    src, out = a.src.resolve(), a.out.resolve()
    if a.manifest_only:
        rep = json.loads(decode(read_bytes(out / "ledger" / "blend_report.json")))
        man = write_manifest(out, rep)
        print(f"MANIFEST.json: {len(man['files'])} files")
        return
    if out == src or str(out).startswith(str(src) + os.sep):
        sys.exit("output must be outside the source checkout")
    t0 = time.time()
    b = Blend(src, out)
    head = git(src, "log", "-1", "--format=%h %cI %s").decode().strip()
    b.report["source"] = "kosif199022-jpg/black-dragon-skill@" + head.split()[0]
    b.report["source_head"] = head
    files = [f for f in git(src, "ls-files", "-z").decode("utf-8").split("\0") if f]
    print(f"[1/8] engine room: copying {len(files)} files …", flush=True)
    b.copy_runtime(files, a.skip_copy)
    print(f"[2/8] documents …", flush=True)
    b.ingest_docs(files)
    print(f"[3/8] roads (playbooks × recipes) · lessons · rules · thinking …", flush=True)
    b.ingest_roads(); b.ingest_lessons(); b.ingest_rules(); b.ingest_thinking()
    print(f"[4/8] fused index + engine catalog …", flush=True)
    b.ingest_fusion_index(); b.ingest_catalog()
    print(f"[5/8] runnable scripts …", flush=True)
    b.ingest_scripts(files)
    print(f"[6/8] branches …", flush=True)
    b.ingest_branches(a.branches)
    b.quarantine()
    # every runtime file must be in the ledger (selftest gate)
    missing = [f for f in files if f not in b.ledger]
    b.report["ledger_missing_runtime"] = len(missing)
    print(f"[7/8] knowledge base + ledger …", flush=True)
    b.write_ledger_file()
    b.write_kb()
    b.write_digests()
    print(f"[8/8] manifest …", flush=True)
    man = write_manifest(out, b.report)
    b.report["manifest_files"] = len(man["files"])
    b.report["seconds"] = round(time.time() - t0, 1)
    json.dump(b.report, open(lp(out / "ledger" / "blend_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    write_manifest(out, b.report)
    print(json.dumps({k: v for k, v in b.report.items() if k not in ("branches_taken",)}, ensure_ascii=False, indent=1,
                     default=str))


if __name__ == "__main__":
    main()
