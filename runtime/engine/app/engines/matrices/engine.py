"""Glass-memory engine: recipe -> deterministic simulation -> metrics (+ the numeric probe and the idea generator).

A recipe (kosif.matrices.recipe.v1) names three parents (structure / dynamics / finish), the six bricks and its
counterfactual conditions; a condition overrides recipe fields with dotted keys ({"coupling.gain": 0}).
Every number the scene draws is computed here, so what is measured is exactly what is drawn. Stdlib only.
"""
import copy, hashlib, json, math, random
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SCHEMA = "kosif.matrices.recipe.v1"
BRICKS = ("state", "operation", "law", "time", "memory", "feedback")
ROLES = ("structure", "dynamics", "finish")
_MISSING = object()


# ------------------------------------------------------------------ recipes
def load_recipe(path):
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    errs = validate_recipe(rec)
    if errs:
        raise ValueError("invalid recipe: " + "; ".join(errs))
    return rec


def validate_recipe(rec, catalog=None):
    """List of problems (empty = valid). With a catalog, parents must exist in it with the named operator."""
    errs = []
    if rec.get("schema") != SCHEMA:
        errs.append("schema must be " + SCHEMA)
    errs += [k + " is required" for k in ("id", "slug", "title_en", "title_ar") if not isinstance(rec.get(k), str) or not rec[k].strip()]
    bricks = rec.get("bricks") or {}
    errs += ["bricks.%s must describe the %s brick" % (b, b) for b in BRICKS
             if not isinstance(bricks.get(b), str) or len(bricks[b].strip()) < 12]
    parents = rec.get("parents") or []
    if [p.get("role") for p in parents] != list(ROLES):
        errs.append("parents must be exactly structure, dynamics, finish (in that order)")
    if len({p.get("style_id") for p in parents}) != len(parents):
        errs.append("parent styles must be distinct")
    if len({p.get("family") for p in parents}) != len(parents):
        errs.append("parent families must be distinct (no same-family blending)")
    if catalog is not None:
        known = {s["style_id"]: s for s in catalog}
        for p in parents:
            s = known.get(p.get("style_id"))
            if s is None:
                errs.append("parent %s is not in the 86-card index" % p.get("style_id"))
            elif p.get("operator") not in s["operator_tags"]:
                errs.append("operator %s is not tagged on %s" % (p.get("operator"), p["style_id"]))
    conds = rec.get("conditions") or {}
    if "A_full" not in conds or len(conds) < 2:
        errs.append("conditions need A_full plus at least one counterfactual")
    errs += ["condition %s overrides unknown field %s" % (n, k) for n, c in conds.items() for k in (c.get("set") or {})
             if _get(rec, k, _MISSING) is _MISSING]
    g = rec.get("grid") or {}
    if not (8 <= g.get("w", 0) <= 256 and 8 <= g.get("h", 0) <= 256):
        errs.append("grid w/h must be 8..256")
    if not (1 <= rec.get("fps", 0) <= 60) or not (0.5 <= rec.get("duration", 0) <= 120):
        errs.append("fps 1..60 and duration 0.5..120 s")
    if not (1 <= rec.get("particles", 0) <= 2000):
        errs.append("particles 1..2000")
    return errs


def _get(d, dotted, default=None):
    for part in dotted.split("."):
        if not isinstance(d, dict) or part not in d:
            return default
        d = d[part]
    return d


def _set(d, dotted, value):
    *head, last = dotted.split(".")
    for part in head:
        d = d[part]
    d[last] = value


def apply_condition(rec, condition, extra=None):
    out = copy.deepcopy(rec)
    for k, v in [*(rec["conditions"][condition].get("set") or {}).items(), *(extra or {}).items()]:
        _set(out, k, v)
    return out


def recipe_hash(rec):
    """Content hash of everything that changes the numbers (labels and prose excluded)."""
    keep = {k: rec[k] for k in ("grid", "fps", "duration", "particles", "seed", "stimulus", "structure", "memory", "coupling", "parents") if k in rec}
    keep["parents"] = [(p["role"], p["style_id"], p["operator"]) for p in rec.get("parents", [])]
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


# ------------------------------------------------------------------ structure, stimulus
def tile_sites(rec):
    """Voronoi sites (grid units) and absorption per tile, from the recipe seed."""
    W, H, st = rec["grid"]["w"], rec["grid"]["h"], rec["structure"]
    r = random.Random("tiles:%s" % rec["seed"])
    sites = [(r.uniform(0, W), r.uniform(0, H)) for _ in range(st["tiles"])]
    return sites, [r.uniform(st["absorb_min"], st["absorb_max"]) for _ in sites]


def build_tiles(rec):
    """Stained-glass tessellation: (tile id grid, absorption grid)."""
    W, H = rec["grid"]["w"], rec["grid"]["h"]
    sites, absorb_of = tile_sites(rec)
    tile = [min(range(len(sites)), key=lambda i: (sites[i][0] - cx) ** 2 + (sites[i][1] - cy) ** 2)
            for cy in (y + 0.5 for y in range(H)) for cx in (x + 0.5 for x in range(W))]
    return tile, [absorb_of[t] for t in tile]


def beam_position(rec, t):
    s = rec["stimulus"]
    u = 2 * math.pi * t / s["period"]  # Gerono lemniscate: a figure-eight once per period
    return s["center"][0] + s["radius"][0] * math.sin(u), s["center"][1] + s["radius"][1] * math.sin(u) * math.cos(u) * 2.0


def beam_on(rec, t):
    a, b = rec["stimulus"]["on"]
    return a <= t < b


def light_field(rec, t):
    W, H = rec["grid"]["w"], rec["grid"]["h"]
    if not beam_on(rec, t):
        return None
    bx, by = beam_position(rec, t)
    s2 = 2 * rec["stimulus"]["spot_sigma"] ** 2
    L = [0.0] * (W * H)
    for y in range(max(0, int(by) - 6), min(H, int(by) + 7)):
        for x in range(max(0, int(bx) - 6), min(W, int(bx) + 7)):
            L[y * W + x] = math.exp(-((x + 0.5 - bx) ** 2 + (y + 0.5 - by) ** 2) / s2)
    return L


# ------------------------------------------------------------------ memory law, dynamics law
def memory_frames(rec, tiles=None):
    """Material memory M for every frame. Independent of particles (one-directional chain)."""
    W, H = rec["grid"]["w"], rec["grid"]["h"]
    tile, absorb = tiles or build_tiles(rec)
    m, dt = rec["memory"], 1.0 / rec["fps"]
    M, frames = [0.0] * (W * H), []
    for f in range(int(round(rec["duration"] * rec["fps"]))):
        L = light_field(rec, f * dt)
        if m["mode"] == "instant":  # ablation: only the live light, no history
            M = [min(m["cap"], v) for v in L] if L else [0.0] * (W * H)
        elif m["mode"] == "persistent":
            new = [0.0] * (W * H)
            for y in range(H):
                for x in range(W):
                    i = y * W + x
                    v, lap = M[i], 0.0
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if 0 <= nx < W and 0 <= ny < H and tile[ny * W + nx] == tile[i]:  # lead lines block diffusion
                            lap += M[ny * W + nx] - v
                    nv = v + dt * (absorb[i] * m["write"] * (L[i] if L else 0.0) - m["decay"] * v) + dt * m["diffusion"] * lap
                    new[i] = 0.0 if nv < 0 else (m["cap"] if nv > m["cap"] else nv)
            M = new
        else:
            raise ValueError("memory.mode must be persistent or instant")
        frames.append(M)
    return frames


def _sample(M, W, H, x, y):
    x, y = min(max(x - 0.5, 0.0), W - 1.001), min(max(y - 0.5, 0.0), H - 1.001)
    x0, y0 = int(x), int(y)
    fx, fy = x - x0, y - y0
    a, b, c, d = M[y0 * W + x0], M[y0 * W + x0 + 1], M[(y0 + 1) * W + x0], M[(y0 + 1) * W + x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _grad(M, W, H, x, y, h=0.75):
    return ((_sample(M, W, H, x + h, y) - _sample(M, W, H, x - h, y)) / (2 * h),
            (_sample(M, W, H, x, y + h) - _sample(M, W, H, x, y - h)) / (2 * h))


def particle_frames(rec, mem):
    W, H, c, dt = rec["grid"]["w"], rec["grid"]["h"], rec["coupling"], 1.0 / rec["fps"]
    r = random.Random("particles:%s" % rec["seed"])
    P = [[r.uniform(1, W - 1), r.uniform(1, H - 1)] for _ in range(rec["particles"])]
    V = [[0.0, 0.0] for _ in P]
    out = []
    for f, M in enumerate(mem):
        jr = random.Random("jitter:%s:%d" % (rec["seed"], f))  # same jitter in every condition
        for p, v in zip(P, V):
            gx, gy = _grad(M, W, H, p[0], p[1]) if c["gain"] else (0.0, 0.0)
            jx, jy = jr.gauss(0, 1) * c["jitter"], jr.gauss(0, 1) * c["jitter"]
            v[0] = (1 - c["drag"]) * v[0] + dt * (c["gain"] * gx + c["flow"][0] + jx * 30 * dt)
            v[1] = (1 - c["drag"]) * v[1] + dt * (c["gain"] * gy + c["flow"][1] + jy * 30 * dt)
            sp = math.hypot(v[0], v[1])
            if sp > c["vmax"]:
                v[0] *= c["vmax"] / sp; v[1] *= c["vmax"] / sp
            for k, hi in ((0, W), (1, H)):
                p[k] += dt * v[k]
                if p[k] < 0.5:
                    p[k] = 1.0 - p[k]; v[k] = -v[k]
                elif p[k] > hi - 0.5:
                    p[k] = 2 * (hi - 0.5) - p[k]; v[k] = -v[k]
        out.append([(p[0], p[1]) for p in P])
    return out


def simulate(rec, condition="A_full", extra=None, tiles=None):
    run = apply_condition(rec, condition, extra)
    tiles = tiles or build_tiles(run)
    mem = memory_frames(run, tiles)
    return {"condition": condition, "recipe": run, "tiles": tiles, "memory": mem, "particles": particle_frames(run, mem)}


# ------------------------------------------------------------------ metrics, experiment
def trace_map(rec, tiles=None):
    """Where the light was remembered: persistent memory at the moment the beam switches off."""
    base = copy.deepcopy(rec)
    base["memory"]["mode"] = "persistent"
    mem = memory_frames(base, tiles)
    return mem[min(len(mem) - 1, int(round(rec["stimulus"]["on"][1] * rec["fps"])) - 1)]


def capture(points, ref, W, H, thr):
    top = max(ref) or 1.0
    return sum(1 for x, y in points if _sample(ref, W, H, x, y) >= thr * top) / max(1, len(points))


def chance_level(ref, thr):
    top = max(ref) or 1.0
    return sum(1 for v in ref if v >= thr * top) / len(ref)


def measure(runs, rec, ref):
    W, H, thr, fps = rec["grid"]["w"], rec["grid"]["h"], rec["metrics"]["trace_threshold"], rec["fps"]
    off = int(round(rec["stimulus"]["on"][1] * fps))
    settle = off + int(round(rec["metrics"]["settle_after_off"] * fps))
    res = {}
    for name, run in runs.items():
        curve = [capture(pts, ref, W, H, thr) for pts in run["particles"]]
        after = curve[settle:] or curve[-1:]
        res[name] = {"capture_final": round(curve[-1], 4), "capture_mean_after_off": round(sum(after) / len(after), 4),
                     "memory_after_off": round(sum(sum(M) for M in run["memory"][off:]) / max(1, len(run["memory"]) - off), 4),
                     "capture_curve": [round(v, 4) for v in curve]}
    if "A_full" in runs:
        A = runs["A_full"]
        for name, run in runs.items():
            if name != "A_full":
                a, b = A["particles"][-1], run["particles"][-1]
                res[name]["mean_end_distance_to_A"] = round(sum(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(a, b)) / len(a), 4)
                res[name]["same_memory_as_A"] = all(abs(x - y) < 1e-12 for M1, M2 in zip(A["memory"], run["memory"]) for x, y in zip(M1, M2))
    res.update(_chance_level=round(chance_level(ref, thr), 4), _light_off_frame=off, _settle_frame=settle)
    return res


def run_conditions(rec, extra=None):
    tiles = build_tiles(rec)
    runs = {c: simulate(rec, c, extra, tiles) for c in rec["conditions"]}
    ref = trace_map(apply_condition(rec, "A_full", extra), tiles)
    return runs, ref, measure(runs, rec, ref)


def spearman(xs, ys):
    def ranks(v):
        order, r, i = sorted(range(len(v)), key=lambda i: v[i]), [0.0] * len(v), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def experiment(rec, seeds=None, dose=None):
    """Full causal test: A/B/C on the recipe seed, replication over seeds, dose-response on gain."""
    acc = rec["acceptance"]
    seeds = acc["seeds"] if seeds is None else seeds
    dose = acc["dose_gains"] if dose is None else dose
    runs, ref, main = run_conditions(rec)
    reps = []
    for s in seeds:
        m = run_conditions(rec, {"seed": s})[2]
        reps.append({"seed": s, **{n: m[n]["capture_mean_after_off"] for n in rec["conditions"]}})
    gain0 = rec["coupling"]["gain"]
    dose_rows = [{"gain_factor": g, "capture_A": run_conditions(rec, {"coupling.gain": gain0 * g})[2]["A_full"]["capture_mean_after_off"]}
                 for g in dose]
    diffs = {c: [r["A_full"] - r[c] for r in reps] for c in rec["conditions"] if c != "A_full"}
    summary = {}
    for c, d in diffs.items():
        mean = sum(d) / len(d)
        pos = sum(1 for x in d if x > 0)
        summary[c] = {"mean_capture_gain_A_minus": round(mean, 4),
                      "sd": round(math.sqrt(sum((x - mean) ** 2 for x in d) / max(1, len(d) - 1)), 4),
                      "positive_in": "%d/%d" % (pos, len(d)),
                      "sign_test_p_one_sided": round(0.5 ** len(d), 6) if pos == len(d) else None, "min": round(min(d), 4)}
    rho = spearman([r["gain_factor"] for r in dose_rows], [r["capture_A"] for r in dose_rows])
    checks = {"B_same_memory_as_A": bool(main.get("B_no_coupling", {}).get("same_memory_as_A")),
              "C_has_no_memory_after_off": main.get("C_no_memory", {}).get("memory_after_off", 1) == 0,
              "A_beats_B_every_seed": all(x >= acc["min_capture_gain_vs_B"] for x in diffs.get("B_no_coupling", [0])),
              "A_beats_C_every_seed": all(x >= acc["min_capture_gain_vs_C"] for x in diffs.get("C_no_memory", [0])),
              "dose_response_monotone": rho > 0.9}
    return {"recipe_id": rec["id"], "recipe_hash": recipe_hash(rec), "seed": rec["seed"], "kind": "NUMERIC_COUNTERFACTUAL",
            "main": {k: ({kk: vv for kk, vv in v.items() if kk != "capture_curve"} if isinstance(v, dict) else v) for k, v in main.items()},
            "curves": {k: v["capture_curve"] for k, v in main.items() if isinstance(v, dict)},
            "replication": reps, "effect": summary, "dose_response": {"rows": dose_rows, "spearman_rho": round(rho, 4)},
            "checks": checks, "verdict": "CONFIRMED_IN_MODEL" if all(checks.values()) else "NOT_CONFIRMED",
            "claim_scope": "Causal inside this numerical model only: same stimulus, same seed, one factor changed per condition. Not a claim about real glass physics or global novelty.",
            }, runs, ref


# ------------------------------------------------------------------ original numeric probe (1-D, no renderer)
def probe_simulate(coupled, steps=56):
    mem, p, speed = [0.0] * 28, [3.5, 7.5, 11.5, 17.5, 23.5], [.11, -.06, .08, -.09, -.10]
    for t in range(steps):
        center = 10 + 3.2 * math.sin(t / 4.0)
        mem = [min(9., .966 * v + (0.46 * math.exp(-((j - center) / 4.5) ** 2) if t < 16 else 0.)) for j, v in enumerate(mem)]
        new = []
        for i, y in enumerate(p):
            j = max(1, min(26, round(y)))
            slope = (mem[j + 1] - mem[j - 1]) * .5
            new.append(max(1., min(26., y + speed[i] + (.060 * slope if coupled else 0.))))
        p = new
    return p, sum(mem)


def probe():
    (control, mc), (trial, mt) = probe_simulate(False), probe_simulate(True)
    d = sum(abs(a - b) for a, b in zip(control, trial)) / len(control)
    return {"kind": "NUMERIC_COUNTERFACTUAL_NOT_VISUAL_RENDER", "light_off_step": 16, "same_initial_values": True,
            "mean_absolute_position_difference": round(d, 7), "same_material_memory": abs(mc - mt) < 1e-10,
            "causal_difference_detected": d > .001}


# ------------------------------------------------------------------ idea generator (parent triples, not renders)
def load_catalog(path=DATA / "86_style_research_database.json"):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["styles"]
    if len(rows) != 86 or len({s["style_id"] for s in rows}) != 86:
        raise ValueError("Exactly 86 distinct style cards required. No claim without audited source.")
    if any("operator_tags" not in s or "card_family" not in s for s in rows):
        raise ValueError("Incomplete source card")
    return rows


def generate(rows, count, seed):
    roles = json.loads((DATA / "tables.json").read_text(encoding="utf-8"))["roles"]
    groups = [set(roles[r]) for r in ROLES]
    rng = random.Random(seed)
    choices = [[s for s in rows if set(s["operator_tags"]) & g] for g in groups]
    if not all(choices):
        raise ValueError("No style adapters for at least one requested role")
    result, seen, attempts = [], set(), 0
    while len(result) < count and attempts < 300 * count:
        attempts += 1
        trio = [rng.choice(p) for p in choices]
        if len({x["style_id"] for x in trio}) != 3 or len({x["card_family"] for x in trio}) != 3:
            continue
        tags = [next(t for t in x["operator_tags"] if t in g) for x, g in zip(trio, groups)]
        hid = "KMX-" + hashlib.sha256("|".join([x["style_id"] for x in trio] + tags).encode()).hexdigest()[:16]
        if hid in seen:
            continue
        seen.add(hid)
        result.append({"id": hid, "status": "UNRENDERED_HYPOTHESIS", "parents": [x["style_id"] for x in trio],
                       "parent_families": [x["card_family"] for x in trio], "roles": dict(zip(ROLES, tags)),
                       "new_causal_law": "Sample dynamic signal u(t); use clamp(normalize(u(t)),0,1) to drive a structure parameter; render the result with finish. Typed adapter and coupling must be defined before rendering.",
                       "required_evidence": ["operator type compatibility", "controlled A/B render", "semantic check", "licence and originality review"]})
    if len(result) != count:
        raise RuntimeError("Insufficient diverse triples for requested count")
    return result
