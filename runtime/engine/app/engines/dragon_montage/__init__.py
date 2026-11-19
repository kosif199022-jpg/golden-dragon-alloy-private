"""Dragon Montage «التنين الأسود، مونتاج»: footage + a task in the owner's words -> a reasoned, reviewed edit.

Stations (each reads and writes plain JSON in one job folder, every tool call leaves a line in receipts.jsonl):
  1 analyze   العين الأولى     analysis.json  shots, quality, faces, motion, colour, words, silences, energy, beats
  2 brief     يفهم المطلوب     brief.json     platform, aspect, seconds, feeling, content type, with evidence
  3 concepts  يفكر بإبداع      concepts.json  three different concepts, decision matrix, pre-mortem, council pack
  4 taste     يختار الذوق      look.json      style, grade, transitions, camera, captions
  5 direct    يكتب المونتاج    edl.json       kosif.dm.edl.v1, every event with a reason
  5b storyboard يوريك الشكل    preview/       storyboard.jpg, PLAN_AR.md (movement matrix), plan.json
  6 render    ينفّذ            render/final.mp4, captions, render.json (frame-exact events_out)
  7 review    يتفرج وينقد      review.json    checks, fixes, frames, verdict, score
  8 fix       يصلّح ويسلّم     direct.apply_review + re-render (max 3 rounds), report.md
Optional: generate (consent-gated proposals), mimic (copy a reference's rhythm), stock (open-licence footage).

Library use:
    from engines import dragon_montage as dm
    dm.plan("اعمل ريل حماسي", ["a.mp4"], job="out/job1", seconds=15)   # stops for the owner's yes
    dm.go("out/job1")                                                  # render -> review -> fix
"""
from .analyze import analyze
from .common import ContractError, read, write, validate, make_test_clip
from .direct import apply_review, direct
from .doctor import check_all as doctor
from .edl import reflow, record_words, to_timeline, from_timeline, from_cut_plan, to_pve, to_nle, check as check_edl
from .generate import attach, gaps
from .hooks import score_hook
from .mimic import mimic
from .pipeline import edit, go, plan
from .render import render
from .review import add_notes, review
from .storyboard import storyboard
from .taste import pick, rank
from .think import brief, concepts

__all__ = ["analyze", "brief", "concepts", "pick", "rank", "direct", "apply_review", "storyboard", "render", "review",
           "add_notes", "gaps", "attach", "mimic", "doctor", "edit", "plan", "go", "reflow", "record_words", "to_timeline",
           "from_timeline", "from_cut_plan", "to_pve", "to_nle", "check_edl", "score_hook", "read", "write", "validate",
           "ContractError", "make_test_clip"]
