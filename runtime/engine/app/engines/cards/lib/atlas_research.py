"""Helpers of power_programs/atlas_research.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from bs4 import BeautifulSoup
import math
from scipy.stats import norm
import re
from urllib import robotparser
from ._lang_common import words
import yaml


WAF = ("cf-chl", "cf_chl_opt", "attention required! | cloudflare", "akamai", "incapsula", "_px", "datadome")


def needs_browser(html: str, mode: str = "auto", known_spa=False) -> dict:
    if mode == "never":
        return {"browser": False, "warnings": ["browser disabled: static result may be incomplete"]}
    if mode == "always" or known_spa:
        return {"browser": True, "warnings": ["forced browser mode"]}
    soup = BeautifulSoup(html, "html.parser")
    has_noscript = soup.find("noscript") is not None
    for t in soup(["noscript", "script", "style"]):
        t.decompose()
    body = soup.body.get_text(" ", strip=True) if soup.body else ""
    warn = []
    if len(body) < 40:
        warn.append("near-empty body")
    if has_noscript and re.search(r"enable javascript|requires javascript", html, re.I):
        warn.append("noscript warning")
    low = html.lower()
    waf = [w for w in WAF if w in low]
    if waf:
        warn.append("WAF fingerprint: " + ",".join(waf))
    return {"browser": bool(warn), "warnings": warn}


PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s-]{8,}\d")


def legality_gate(robots_txt, url, agent, tos_forbids_scraping, needs_login, sample_text):
    rp = robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    checks = {"robots_allowed": rp.can_fetch(agent, url), "tos_ok": not tos_forbids_scraping,
              "public": not needs_login}
    delay = rp.crawl_delay(agent)
    rate = 1.0 / delay if delay else 1.0  # polite default: 1 request per second
    flags = []
    if PII.search(sample_text):
        flags.append("PII")
    if "©" in sample_text or "all rights reserved" in sample_text.lower():
        flags.append("copyright")
    passed = all(checks.values())
    return {"checks": checks, "rate_per_s": rate, "flags": flags, "passed": passed,
            "strategy": ("static fetch" if passed else None)}


def cohen_kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe)


CAUSAL = re.compile(r"\b(causes?|leads? to|results? in|because of|drives?)\b", re.I)


def ft_route(mb=None, kind=None, has_eval=True, pretrain_lr=None):
    if not has_eval:
        return {"route": "build eval harness first"}
    if kind == "volatile facts":
        return {"route": "RAG"}
    if kind == "unsettled behavior":
        return {"route": "prompting"}
    if kind in ("demonstrations", "preference pairs", "verifiable reward"):
        return {"route": {"demonstrations": "SFT", "preference pairs": "DPO/ORPO/KTO",
                          "verifiable reward": "GRPO/RLVR"}[kind]}
    if mb < 10:
        r = "RAG"
    elif mb <= 500:
        r = "RAG+FT"
    elif mb <= 10000:
        r = "CPT then SFT"
    else:
        r = "CPT"
    out = {"route": r}
    if "CPT" in r and pretrain_lr:
        out["cpt_lr"] = pretrain_lr * 0.10
    return out


def n_means(d, alpha=0.05, power=0.8):
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil(2 * z * z / (d * d))


def n_props(p1, p2, alpha=0.05, power=0.8):
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    pb = (p1 + p2) / 2
    n = (za * math.sqrt(2 * pb * (1 - pb)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return math.ceil(n)


def schoenfeld_events(hr, alpha=0.05, power=0.8, p=0.5):
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil(z * z / (p * (1 - p) * math.log(hr) ** 2))


def endpoint_select(eps, weights):
    out = []
    for e in eps:
        s = sum(weights[k] * e[k] for k in weights)
        cls = "primary" if s >= 4 else "key-secondary" if s >= 3 else "exploratory"
        out.append({"name": e["name"], "score": round(s, 2), "class": cls, "surrogate": e.get("surrogate", False)})
    return out


def phase_gate(score):
    return "GO" if score >= 80 else "GO-WITH-CONDITIONS" if score >= 65 else "REDESIGN" if score >= 40 else "NO-GO"


CRED = re.compile(r"\b(MD|DO|NP|PA-C|DDS|PhD|RN)\b")


def extract_providers(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select(".provider"):
        name = card.select_one(".name").get_text(strip=True)
        creds = CRED.findall(name + " " + card.get_text(" "))
        clean = CRED.sub("", name).strip(" ,")
        spec = card.select_one(".specialty")
        rows.append({"name": clean, "credentials": sorted(set(creds)),
                     "specialty": spec.get_text(strip=True) if spec else None})
    gaps = [r["name"] for r in rows if not r["specialty"]]
    return rows, gaps


SUBCASES = ("novelty", "freedom-to-operate", "landscape", "invalidity", "due diligence")


JURIS = {"US", "EP", "CN", "JP", "KR", "PCT"}


VAGUE = re.compile(r"^(something|an app|a device|an idea|a thing)\b|\b(etc|stuff|things)\b", re.I)


STOP = set("a an the of for and with to in that which by on is are using uses from".split())


def patent_intake(answers):
    log, rejected_once = [], False
    for q1 in answers["q1"]:
        if (VAGUE.search(q1) or len(q1.split()) < 8) and not rejected_once:
            rejected_once = True
            log.append("Q1 rejected as vague: " + q1)
            continue
        desc = q1
        break
    else:
        desc = answers["q1"][-1]
    if answers["q2"] not in SUBCASES:
        raise ValueError("pick one of five sub-use-cases")
    bad = [j for j in answers["q3"] if j not in JURIS]
    if bad:
        raise ValueError(f"unknown jurisdictions {bad}")
    kw = [w for w in words(desc) if w not in STOP and len(w) > 3]
    return {"description": desc, "purpose": answers["q2"], "jurisdictions": answers["q3"], "log": log,
            "keywords": sorted(set(kw)), "caveat": "search report, not legal advice"}


def validate_base(text):
    data = yaml.safe_load(text)
    defined = set((data.get("formulas") or {}).keys())
    used = set(re.findall(r"formula\.(\w+)", text))
    missing = sorted(used - defined)
    views_ok = all("type" in v and "name" in v for v in data.get("views", []))
    return {"ok": not missing and views_ok, "missing_formulas": missing, "views": len(data.get("views", []))}


def combobox(options, typed, recents):
    t = typed.lower()
    m = [o for o in options if t in o.lower()]
    return sorted(m, key=lambda o: (o not in recents, recents.index(o) if o in recents else 0, o))


def audit_fields(fields):
    issues = []
    for f in fields:
        if f["kind"] == "password" or f["kind"] == "free text":
            continue
        if f["kind"] == "choice" and not f.get("options_shown"):
            issues.append((f["name"], "options hidden: user must recall"))
        if f.get("placeholder", "").lower() in ("enter value", "enter value..."):
            issues.append((f["name"], "placeholder should show an example value"))
    return issues
