#!/usr/bin/env python3
"""Print the Ultra Mind thinking checklist for a task type and depth level.

Usage: python scaffold.py <type> [level]
  type : math | code | analysis | decision | forecast | creative | writing | general
  level: L0 | L1 | L2 | L3   (default L2)
"""
import sys

CORE = {
    1: "UNDERSTAND (Polya): unknown? data? conditions? restate in one line; list every constraint; flag ambiguity.",
    2: "STEP BACK: what general principle / problem class is this? start from the base rate (outside view).",
    3: "DIVERGE: write 2-4 genuinely different approaches/hypotheses; what evidence DISCRIMINATES between them?",
    4: "EXECUTE: compute with code, not in your head; check units, signs, edge cases (0, 1, empty, max).",
    5: "BREAK IT (Popper / pre-mortem / inversion): assume the answer is wrong - most likely why? find one counterexample.",
    6: "VERIFY INDEPENDENTLY (CoVe): answer verification questions WITHOUT looking at the draft; prefer external checks (run, substitute, source).",
    7: "CALIBRATE & DELIVER: result first; separate verified / inferred / assumed; state confidence only when useful.",
}

LEVEL_STAGES = {"L0": [1], "L1": [1, 3, 6], "L2": [1, 2, 3, 4, 5, 6, 7], "L3": [1, 2, 3, 4, 5, 6, 7]}

TYPE_FOCUS = {
    "math": ["Read every condition literally - is this a MODIFIED famous puzzle?",
             "Compute in code; back-substitute the answer into the original conditions.",
             "Test a tiny case (n=1,2) and a magnitude sanity check."],
    "code": ["Reproduce the bug before fixing it.",
             "List competing root-cause hypotheses; bisect; change one variable at a time.",
             "Run the code/tests; search all call sites before editing."],
    "analysis": ["ACH matrix: hypotheses x evidence; seek disconfirming evidence.",
                 "Primary sources, check dates; never invent a citation.",
                 "Separate fact / inference / opinion; check correlation vs causation (Pearl)."],
    "decision": ["At least 3 options incl. 'do nothing'; weighted criteria scored separately (Noise).",
                 "Pre-mortem: top 3 failure causes + mitigation; worst case acceptable?",
                 "Reversible (move fast) or irreversible (slow down)? concrete first step."],
    "forecast": ["Outside view first (base rate), then adjust with case specifics.",
                 "Fermi-decompose; give a range or explicit probability.",
                 "Name the signals that would move the estimate."],
    "creative": ["Write the first 3 obvious ideas to clear them, then push further (6-10 total).",
                 "Apply 2 tools: bisociation (distant domain), assumption reversal, TRIZ contradiction, morphological matrix, constraint.",
                 "Select by novelty x fit x feasibility x impact; make the winner concrete; offer safe + bold."],
    "writing": ["Who is the reader? one core idea, stated in the first sentence.",
                "One concrete example for each hard idea.",
                "Cut filler; confirm every user request is covered."],
    "general": ["Is this the question that was actually asked?",
                "One alternative interpretation/approach before committing.",
                "Verify the key claim by an independent route."],
}

RULES = [
    "First idea = hypothesis, not conclusion.",
    "Discriminating evidence > confirming evidence.",
    "Calculate, don't guess.",
    "Verification must be independent of the original path.",
    "Don't flip a correct answer under pressure without new evidence.",
    "Precise 'I don't know' > confident error. Never fabricate sources.",
]


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    ttype = args[0].lower()
    level = (args[1] if len(args) > 1 else "L2").upper()
    if ttype not in TYPE_FOCUS or level not in LEVEL_STAGES:
        print(__doc__)
        return 1
    print(f"=== ULTRA MIND | type={ttype} | level={level} ===\n")
    print("Core loop:")
    for i in LEVEL_STAGES[level]:
        print(f"  {i}. {CORE[i]}")
    print("\nTask focus:")
    for line in TYPE_FOCUS[ttype]:
        print(f"  - {line}")
    if level == "L3":
        print("\nL3 extras:")
        print("  - 3+ branches; full adversarial review.")
        print("  - If agents exist: send the SAME problem to 2 independent agents without your opinion; compare.")
        print("  - Assign one agent as a hostile critic of your answer.")
    print("\nGolden rules:")
    for r in RULES:
        print(f"  * {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
