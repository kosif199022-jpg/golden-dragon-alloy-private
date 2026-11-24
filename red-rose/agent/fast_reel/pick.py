#!/usr/bin/env python3
"""Fast lane step 2: choose one library clip per scene in seconds.
usage: pick.py library.json scenes.json hints.json > sel.txt
hints.json: list of theme lists, one per scene (e.g. [["sea_sunset","dawn"],["tea","coffee_dates"],...]).
Score = |luma - target|/40 + |warm - target|/40 + penalty if the text band is bright; never the same clip twice;
blacklist.txt holds clips that failed a check (people, logos, text, figurines)."""
import json, os, sys
L = json.load(open(sys.argv[1])); S = json.load(open(sys.argv[2]))['scenes']; H = json.load(open(sys.argv[3]))
bl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blacklist.txt')
bad = {l.split()[0] for l in open(bl_path) if l.strip() and not l.startswith('#')} if os.path.exists(bl_path) else set()
used = set()
for sc, hint in zip(S, H):
    need = sc['b'] - sc['a']
    c = [x for x in L if x['theme'] in hint and os.path.basename(x['f']) not in bad and x['f'] not in used and x['h'] >= x['w'] * 0.9]
    if not c: c = [x for x in L if x['theme'] in hint and x['f'] not in used]
    c.sort(key=lambda x: abs(x['luma'] - sc['luma']) / 40 + abs(x['warm'] - sc['warm']) / 40 + max(0, x['band'] - 140) / 30 + (0.5 if x['dur'] < need * 0.6 else 0))
    used.add(c[0]['f']); print(c[0]['f'])
