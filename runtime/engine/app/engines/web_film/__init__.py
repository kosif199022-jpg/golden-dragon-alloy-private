"""Web Film («التنين الأسود»): motion films built as seek-driven web pages and rendered to video by engines/render/render.cjs.

Two modes:
  page  -- plan -> scaffold -> check -> render: one <section> per shot, a seek(t) engine (assets/scaffold.js).
  world -- one world, one continuous camera over it, drawn on a canvas (assets/engine.js + assets/camera.cjs).
"""
from .page import RATIOS, KINDS, TRANSITIONS, default_plan, check_plan, check_html, check, scaffold, write_scaffold
from .render import render_page
from . import world

__all__ = ["RATIOS", "KINDS", "TRANSITIONS", "default_plan", "check_plan", "check_html", "check", "scaffold",
           "write_scaffold", "render_page", "world"]
