"""Helpers of power_programs/web_research.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from ._lang_common import jaccard
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlparse
from ._lang_common import words


ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(text):
    root = ET.fromstring(text)
    out = []
    if root.tag == "rss":
        for it in root.iter("item"):
            pub = it.findtext("pubDate")
            out.append({"title": it.findtext("title"), "link": it.findtext("link"),
                        "published": parsedate_to_datetime(pub).isoformat() if pub else None})
    elif root.tag == ATOM + "feed":
        for e in root.iter(ATOM + "entry"):
            link = e.find(ATOM + "link")
            out.append({"title": e.findtext(ATOM + "title"), "link": link.get("href") if link is not None else None,
                        "published": e.findtext(ATOM + "published") or e.findtext(ATOM + "updated")})
    return out


def claim_ledger(evidence):
    rows = []
    for claim, ev in evidence.items():
        pro = [e for e in ev if e["supports"]]
        con = [e for e in ev if not e["supports"]]
        values = sorted({e.get("value") for e in ev if e.get("value") is not None})
        if len(values) > 1:
            status = "conflict"
            note = "sources disagree: " + " vs ".join(map(str, values))
        elif pro and any(e["tier"] == 1 for e in pro) and not con:
            status, note = "fact", ""
        elif pro:
            status, note = "inference", "no tier-1 source" if not con else "contested"
        else:
            status, note = "unknown", "no supporting source"
        best = min(ev, key=lambda e: e["tier"]) if ev else {"src": "-", "tier": "-", "date": "-"}
        rows.append([claim, status, f"{best['src']} (T{best['tier']})", best["date"], note])
    return rows


TIER1 = ("docs.", "pypi.org", "github.com", "sec.gov", "w3.org", "rfc-editor.org", "who.int")


TIER3 = ("reddit.com", "medium.com", "stackoverflow.com", "quora.com", "blogspot.", "wordpress.")


def tier(url):
    host = urlparse(url).netloc.lower()
    if any(t in host for t in TIER1) or host.endswith(".gov"):
        return 1
    if any(t in host for t in TIER3):
        return 3
    return 2


def score_hit(doc_terms, query_terms):
    return round(len(doc_terms & query_terms) / max(len(query_terms), 1), 2)


def retrieval_loop(corpus, query, learn, max_cycles=3):
    q = set(query)
    log = []
    for cycle in range(1, max_cycles + 1):
        scored = {d: score_hit(set(t), q) for d, t in corpus.items()}
        kept = {d: s for d, s in scored.items() if s >= 0.2}
        dropped = sorted(d for d, s in scored.items() if s < 0.2)
        strong = sorted(d for d, s in kept.items() if s >= 0.7)
        log.append({"cycle": cycle, "query": sorted(q), "strong": strong, "dropped": dropped})
        if len(strong) >= 3:
            return log, "enough evidence"
        q |= set(learn.get(cycle, []))
    return log, "cycle cap"


def triage(question, given, history):
    qtype = "comparison" if re.search(r"\bvs\b|compare|أفضل", question, re.I) else \
        "lookup" if re.search(r"\bwhat is|when|كم\b", question, re.I) else "analysis"
    ev = [f"user-provided: {g}" for g in given]
    out = {"QUESTION TYPE": qtype, "EVIDENCE": ev, "INFERENCE": "pending new sources",
           "RECOMMENDATION": "start from the user's material"}
    if sum(1 for h in history if jaccard(words(h), words(question)) > 0.6) >= 1:
        out["RECOMMENDATION"] += "; recurring question: propose a scheduled monitor (WEB-20)"
    return out


INJECT = re.compile(r"(ignore (all|any|previous) instructions|you are now|system prompt|as an ai (agent|assistant)|"
                    r"run this command|تجاهل التعليمات)", re.I)


def corroborate(artifacts):
    claims = {}
    flagged = []
    for a in artifacts:
        if INJECT.search(a["page_text"]):
            flagged.append(a["url"])
            continue
        for c in a["claims"]:
            claims.setdefault(c, set()).add(urlparse(a["url"]).netloc)
    usable = sorted(c for c, hosts in claims.items() if len(hosts) >= 2)
    return usable, sorted(flagged), {c: sorted(h) for c, h in claims.items()}


def fetch_report(results):
    rep = []
    for r in results:
        if r["status"] != 200:
            rep.append({"url": r["url"], "finding": "gap: fetch failed (not a disproof)"})
        elif INJECT.search(r["text"]):
            m = INJECT.search(r["text"])
            rep.append({"url": r["url"], "finding": "suspicious agent-directed text", "quote": m.group(0)})
        else:
            rep.append({"url": r["url"], "finding": "data"})
    return rep


def bot_policy(resp):
    if resp["status"] in (401, 403, 429) and re.search(r"robot|bot policy|automated", resp["body"], re.I):
        return {"action": "stop", "spoof_user_agent": False, "retry": False,
                "alternatives": ["site API under its terms", "public dump", "WebFetch", "ask user for the text"],
                "record": f"refused {resp['status']}: {resp['body'][:60]}"}
    return {"action": "use", "retry": False}


def proxy_plan(status, attempts_failed):
    fails = status.get("recentRelayFailures", [])
    plan = []
    for f in fails:
        code = f.get("status")
        if code in (403, 407):
            plan.append({"host": f["host"], "kind": "policy denial", "retries": 0, "report": True})
        else:
            n = min(3, max(0, 3 - attempts_failed))
            plan.append({"host": f["host"], "kind": "transient", "retries": n,
                         "backoff_s": [2 ** i for i in range(n)], "report": n == 0})
    return {"plan": plan, "unset_proxy": False}


def licence_rule(text):
    t = text.lower()
    if not t.strip():
        return "no licence: ideas only"
    if "sharealike" in t.replace("-", "").replace(" ", "") or "cc by-sa" in t:
        return "reuse forces ShareAlike"
    if "mit license" in t or "permission is hereby granted, free of charge" in t:
        return "reuse with notice"
    if "apache license" in t:
        return "reuse with notice"
    return "unknown: ask"


def quote_ok(q, max_words=12):
    return len(q.split()) <= max_words


def perspective_check(perspectives, snippets, outline, sections, questions):
    errors = []
    if not 3 <= len(perspectives) <= 6:
        errors.append("need 3-6 perspectives")
    ids = {s["id"] for s in snippets}
    for h in outline:
        if not set(h["from"]) <= ids:
            errors.append(f"outline item not from snippets: {h['title']}")
    uncited = []
    for sec in sections:
        for sent in sec:
            cites = set(re.findall(r"\[(s\d+)\]", sent))
            if not cites or not cites <= ids:
                uncited.append(sent)
    answered = {s["q"] for s in snippets}
    open_q = [q for q in questions if q not in answered]
    return {"errors": errors, "uncited": uncited, "open_questions": open_q}


def plan_ok(subqs, max_overlap=0.5):
    if not 3 <= len(subqs) <= 6:
        return False, "need 3-6 sub-questions"
    for i in range(len(subqs)):
        for j in range(i + 1, len(subqs)):
            if jaccard(words(subqs[i]), words(subqs[j])) > max_overlap:
                return False, f"overlap: {subqs[i]!r} ~ {subqs[j]!r}"
    return True, ""


def editor(reports, budget):
    merged, conflicts, notes = {}, [], []
    for r in reports:
        if len(r["sources"]) > budget:
            r = dict(r, sources=r["sources"][:budget])
            notes.append(f"{r['who']}: trimmed to {budget} sources")
        if not r["findings"]:
            notes.append(f"{r['who']}: found nothing")
        for k, v in r["findings"].items():
            if k in merged and merged[k] != v:
                conflicts.append((k, merged[k], v))
            merged.setdefault(k, v)
    srcs = sorted({s for r in reports for s in r["sources"][:budget]})
    return {"answer": merged, "conflicts": conflicts, "notes": notes, "sources": srcs}
