"""Talking-head reels: one recording of a person talking to camera -> a vertical 9:16 editorial reel.

Pipeline (each step reads/writes the project folder):
  prepare -> transcribe | import_words -> cut_pauses -> master -> (write edl.json) -> validate -> stills -> render
The look, EDL vocabulary and pipeline settings live in data/*.json.
"""
from .project import (asr_from_words, check, clip_sheet, cut_pauses, energy_db, import_words, keep_segments, master, prepare,
                      retime, speech_regions, transcribe)
from .edl import build_plan, validate
from .render import render, stills

__all__ = ["prepare", "transcribe", "import_words", "asr_from_words", "cut_pauses", "energy_db", "speech_regions", "keep_segments",
           "retime", "master", "validate", "build_plan", "stills", "render", "clip_sheet", "check"]
