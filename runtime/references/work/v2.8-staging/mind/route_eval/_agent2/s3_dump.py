import json, os
from common import *
d = json.load(open(os.path.join(R, "_agent2", "freq.json"), encoding="utf-8"))
f = d["freq"]
ws = sorted((w for w in f if len(w) >= 3), key=lambda w: w[::1])
print(" ".join(w if f[w] == 1 else f"{w}:{f[w]}" for w in ws))
