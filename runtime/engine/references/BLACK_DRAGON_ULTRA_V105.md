# Black Dragon Ultra — source study

The uploaded `kosif-black-dragon-ultra` includes a front door that routes to 21 KOSIF modules and calls `route`, `cycle`, `doctor`, `needs`, `exec`, `verify`, `learn`. This v10.5 package **does not execute its original `dragon.py`**, which assumes a separate local KOSIF repo root and includes package-install commands; the existing Black Dragon front door is retained.

Adopted patterns: route before execution, identify missing dependencies, prefer explicit project-local outputs, compare verified outputs with declared acceptance criteria, and report whether external programs and actual agents ran. `learn` requires user-confirmed outcomes; don't treat a recorded heuristic as retraining model weights.

This note is derived from the provided skill, not proof the 21 listed modules are all installed or working.
