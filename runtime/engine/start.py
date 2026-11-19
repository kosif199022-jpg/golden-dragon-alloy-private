#!/usr/bin/env python3
"""Black Dragon start door. Run this first when the package reaches Claude:  python start.py
It prints what the package is and the one question to ask the owner (laptop or cloud?). Standard library only."""
import runpy, sys
from pathlib import Path
sys.argv = [str(Path(__file__).resolve().parent / "tools" / "machine" / "machine.py"), "start"] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
