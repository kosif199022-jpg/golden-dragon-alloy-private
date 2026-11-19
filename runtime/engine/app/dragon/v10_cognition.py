"""Decision-quality prompts inspired by the user's copy of Kahneman's Thinking, Fast and Slow.

This is a source-aware CHECKLIST, not a cognitive model trained on a copyrighted book.
It never invents option scores or proof of execution.
"""
from __future__ import annotations
import json
from pathlib import Path

CHECKS = [
    {"id":"fast-slow","chapter":"1-3, Two Systems","trigger":"complex","question_ar":"ما الانطباع الأول؟ وما الدليل المستقل الذي سيختبره؟","test":"Separate intuitive draft from deliberate factual review."},
    {"id":"small-n","chapter":"10, Law of Small Numbers","trigger":"data","question_ar":"هل حجم العينة كافٍ، وهل التفاوت محسوب؟","test":"Expose sample size; avoid treating a small clip/sample as a population."},
    {"id":"anchoring","chapter":"11, Anchors","trigger":"estimate","question_ar":"هل تأثر تقديرك برقم أولي غير مثبت؟","test":"Derive range from independent inputs before comparing any benchmark."},
    {"id":"availability","chapter":"12-13, Availability","trigger":"research","question_ar":"هل اخترنا المعلومة لأنها سهلة التذكر فقط؟","test":"Search for counterexamples and record sources, not just vivid examples."},
    {"id":"base-rate","chapter":"14-16, Base Rates / Causes","trigger":"decision","question_ar":"ما معدل الأساس قبل الحكم على الحالة الاستثنائية؟","test":"Compare inside-view story against actual base rates where measurable."},
    {"id":"regression","chapter":"17-18, Regression / Prediction","trigger":"metric","question_ar":"هل النتائج الاستثنائية قد ترجع للمتوسط؟","test":"Track baseline and uncertainty before promising improvement."},
    {"id":"overconfidence","chapter":"19-24, Overconfidence","trigger":"all","question_ar":"ما الذي قد يجعلنا مخطئين رغم ثقتنا؟","test":"List falsifiers, alternatives, outside view and calibrated confidence."},
    {"id":"loss-aversion","chapter":"26-34, Choices / Framing","trigger":"choice","question_ar":"هل صياغة المكسب أو الخسارة غيّرت الاختيار؟","test":"Evaluate reversible costs, worst case, and equivalent gain/loss framing."},
    {"id":"two-selves","chapter":"35-38, Two Selves","trigger":"video","question_ar":"هل ذروة التجربة ونهايتها تخدمان إحساس الجمهور دون تضليل؟","test":"Evaluate viewer experience across the whole timeline, not only the final thumbnail."},
]


def checklist(task: str, *, domain: str = "general") -> dict:
    if not task or not task.strip():
        raise ValueError("task cannot be empty")
    domain = domain.strip().lower()
    if domain not in {"general", "video", "data", "decision", "research"}:
        raise ValueError("domain must be general|video|data|decision|research")
    if domain == "video":
        ids = {"fast-slow", "availability", "base-rate", "overconfidence", "loss-aversion", "two-selves"}
    elif domain == "data":
        ids = {"small-n", "anchoring", "base-rate", "regression", "overconfidence", "loss-aversion"}
    elif domain == "research":
        ids = {"small-n", "availability", "base-rate", "overconfidence"}
    else:
        ids = {x["id"] for x in CHECKS}
    return {
        "kind":"black-dragon.v10/cognitive-checklist", "task":task, "domain":domain,
        "execution_performed":False,
        "methods":[x for x in CHECKS if x["id"] in ids],
        "decision_record": {"alternatives_required":3, "confidence_without_independent_evidence":"not_scored",
                            "counterargument_required":True, "approval_needed_for_spend_or_publish":True},
        "source_note":"Original paraphrases from the user-supplied Thinking, Fast and Slow, chapters shown. No book text included."
    }


def validate_decision(doc: dict) -> list[str]:
    errors=[]
    opts=doc.get("options")
    if not isinstance(opts,list) or len(opts)<3:
        return ["at least three genuinely different options are required"]
    identifiers=[]
    for i,o in enumerate(opts):
        if not isinstance(o,dict) or not all(str(o.get(k,"")).strip() for k in ("id","approach","evidence","risk")):
            errors.append(f"option {i}: missing id/approach/evidence/risk")
        else:
            identifiers.append(o["id"])
    if len(set(identifiers))!=len(identifiers): errors.append("duplicate option IDs")
    if doc.get("selected") not in identifiers: errors.append("selected must match an option ID")
    if not str(doc.get("falsifier","")).strip():errors.append("independent falsifier/counterexample required")
    if not str(doc.get("baseline","")).strip():errors.append("baseline or outside-view comparison required")
    return errors
