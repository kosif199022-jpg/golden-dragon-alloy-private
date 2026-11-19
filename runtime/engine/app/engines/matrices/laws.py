"""Four typed causal laws (from the owner's v0.2 causal studio, SRC-024), each one causal edge that arm B switches off:

  trajectory_memory  stored light -> velocity          material_memory  stored light -> material luminance
  elastic_memory     stored light -> displacement      self_imprinting  particle history -> memory field -> velocity
Arithmetic is identical to v0.2 so the owner's receipts reproduce byte for byte. A law is CONFIRMED_IN_MODEL only when
the effect is 0 at gain 0, positive at full gain and rises with the dose (gain x 0, .25, .5, 1; Spearman rho). Stdlib only.
"""
import hashlib, html, json, math
from pathlib import Path
from .engine import spearman

DATA = Path(__file__).resolve().parent / "data"
RECIPES = DATA / "recipes" / "laws"
ATOMS = DATA / "197_mechanism_atoms.json"
VERSION = "kmx-laws-1 (from causal_studio 0.2.0)"
LAWS = json.loads((DATA / "tables.json").read_text(encoding="utf-8"))["laws"]
GEOMETRIES = ("rings", "spiral", "lattice")
DOSE = (0.0, 0.25, 0.5, 1.0)
N = 35  # field resolution


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(data):
    return hashlib.sha256(canonical(data).encode("utf8")).hexdigest()


class P:  # particle
    __slots__ = ("x", "y", "material")

    def __init__(self, x, y, material=0.55):
        self.x, self.y, self.material = x, y, material


class Field:
    def __init__(self):
        self.a = [[0.0] * N for _ in range(N)]

    @staticmethod
    def coord(x, y):
        c = lambda v: max(0, min(N - 1, round((max(-.999, min(.999, v)) + 1) * (N - 1) / 2)))
        return c(x), c(y)

    def sample(self, x, y):
        i, j = self.coord(x, y)
        return self.a[j][i]

    def grad(self, x, y):
        h = 2 / (N - 1)
        return ((self.sample(x + h, y) - self.sample(x - h, y)) / (2 * h), (self.sample(x, y + h) - self.sample(x, y - h)) / (2 * h))

    def advance(self, t, light_steps, decay):
        cx, cy = 0.34 * math.sin(t * .31), 0.24 * math.cos(t * .27)
        for j in range(N):
            y = -1 + 2 * j / (N - 1)
            for i in range(N):
                x = -1 + 2 * i / (N - 1)
                excitation = 0.33 * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / .055) if t < light_steps else 0
                self.a[j][i] = min(4, decay * self.a[j][i] + excitation)

    def imprint(self, particles):
        for p in particles:
            i, j = self.coord(p.x, p.y)
            self.a[j][i] = min(4, self.a[j][i] + .035)


def initial(geometry, n=120):
    out = []
    for i in range(n):
        q = i / max(n - 1, 1)
        if geometry == "spiral":
            theta, radius = 6 * math.pi * q, .1 + .72 * math.sqrt(q)
            x, y = radius * math.cos(theta), radius * math.sin(theta)
        elif geometry == "lattice":
            k = math.ceil(math.sqrt(n))
            row, col = divmod(i, k)
            x, y = -.82 + 1.64 * col / (k - 1), -.82 + 1.64 * row / (k - 1)
        elif geometry == "rings":
            theta, radius = 2.3999632 * i, .10 + .75 * (i % 11) / 10
            x, y = radius * math.cos(theta), radius * math.sin(theta)
        else:
            raise ValueError("unsupported geometry " + geometry)
        out.append(P(x, y))
    return out


def validate_plan(plan):
    errs, law, par = [], plan.get("law"), plan.get("parameters") or {}
    if law not in LAWS:
        errs.append("law not registered: %r (known: %s)" % (law, ", ".join(LAWS)))
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if not num(par.get("gain")) or not 0 <= par["gain"] <= 1:
        errs.append("gain must be a number in 0..1")
    if not num(par.get("decay")) or not 0 < par["decay"] < 1:
        errs.append("decay must be a number in (0, 1)")
    if par.get("geometry") not in GEOMETRIES:
        errs.append("geometry must be one of %s" % (GEOMETRIES,))
    contract = plan.get("causal_contract")
    if law in LAWS and contract is not None and {k: contract.get(k) for k in ("input", "output", "edge")} != LAWS[law]:
        errs.append("causal_contract does not match the typed ports of law %s" % law)
    return errs


def simulate(plan, frames=32, n=120):
    """Arm A (edge on) and arm B (edge off) from identical inputs -> (histA, histB, metrics)."""
    errs = validate_plan(plan)
    if errs:
        raise ValueError("; ".join(errs))
    if not 8 <= frames <= 120 or not 16 <= n <= 300:
        raise ValueError("simulation outside safe bounds (frames 8..120, n 16..300)")
    law, par = plan["law"], plan["parameters"]
    gain, decay = par["gain"], par["decay"]
    lit = max(1, int(frames * .36))
    hist, fields, states, metrics = [[], []], [Field(), Field()], [initial(par["geometry"], n), initial(par["geometry"], n)], []
    for t in range(frames):
        for side in (0, 1):
            on, field = side == 0, fields[side]
            field.advance(t, lit, decay)
            if law == "self_imprinting" and on:  # only the particle -> field write differs; both arms keep field -> motion
                field.imprint(states[side])
            new = []
            for p in states[side]:
                x, y = p.x, p.y
                vx, vy = -.31 * y + .07 * math.sin(t * .14), .31 * x + .07 * math.cos(t * .16)
                gx, gy = field.grad(x, y)
                if (law == "trajectory_memory" and on) or law == "self_imprinting":
                    vx += gain * gx
                    vy += gain * gy
                if law == "elastic_memory" and on:
                    x += .012 * gain * gx
                    y += .012 * gain * gy
                base = min(1, .55 + .43 * gain * field.sample(x, y)) if law == "material_memory" and on else p.material
                new.append(P(max(-.97, min(.97, x + .10 * vx)), max(-.97, min(.97, y + .10 * vy)), base))
            states[side] = new
            hist[side].append(new)
        a, b = states
        metrics.append({"pos": sum(math.hypot(p.x - q.x, p.y - q.y) for p, q in zip(a, b)) / n,
                        "material": sum(abs(p.material - q.material) for p, q in zip(a, b)) / n})
    final, post = metrics[-1], metrics[lit:]
    return hist[0], hist[1], {
        "law": law, "coupling_edge": LAWS[law]["edge"], "frames": frames, "light_off_frame": lit,
        "same_exogenous_light": True, "same_initial_positions": True, "only_one_channel_disabled": True,
        "final_pos_difference": round(final["pos"], 9), "final_material_difference": round(final["material"], 9),
        "mean_post_light_effect": round(sum(x["pos"] + x["material"] for x in post) / len(post), 9),
        "effect_detected": (final["pos"] + final["material"]) > 1e-7,
        "metric": "mean particle position displacement + absolute normalized material difference"}


def experiment(plan, frames=32, n=120, dose=DOSE):
    """A/B run plus a dose sweep of the coupling gain."""
    main = simulate(plan, frames, n)[2]
    sweep = []
    for f in dose:
        p = json.loads(json.dumps(plan))
        p["parameters"]["gain"] = plan["parameters"]["gain"] * f
        sweep.append({"factor": f, "gain": round(p["parameters"]["gain"], 9), "mean_post_light_effect": simulate(p, frames, n)[2]["mean_post_light_effect"]})
    effects = [s["mean_post_light_effect"] for s in sweep]
    rho = spearman(list(dose), effects)
    checks = {"effect_at_full_gain": main["effect_detected"] and main["mean_post_light_effect"] > 0,
              "zero_gain_zero_effect": effects[0] == 0.0, "dose_monotonic": rho > 0.9}
    return {"schema": "kosif.matrices.law-experiment.v1", "engine": VERSION, "recipe_id": plan.get("id"), "recipe_sha256": digest(plan),
            "law": plan["law"], "contract": LAWS[plan["law"]], "metrics": main, "dose": sweep, "dose_spearman_rho": round(rho, 6),
            "checks": checks, "verdict": "CONFIRMED_IN_MODEL" if all(checks.values()) else "NOT_CONFIRMED", "status": "NUMERIC_TESTED",
            "limits": ["causal claim holds inside this toy particle model only",
                       "no visual or human review yet; a numeric pass is not a visual pass",
                       "the 197 mechanism atoms are concepts, not executors"]}


def frame_svg(history, frame, law, enabled):
    title = "KOSIF · %s · %s" % (law, "A: COUPLED" if enabled else "B: CONTROL")
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 740" width="740" height="740">',
           '<rect width="740" height="740" fill="#091525"/>',
           '<text x="36" y="48" fill="#f0f5ff" font-size="19" font-family="sans-serif">%s</text>' % html.escape(title),
           '<text x="36" y="72" fill="#a6bed4" font-size="12" font-family="monospace">FRAME %02d/%02d</text>' % (frame + 1, len(history)),
           '<rect x="25" y="94" width="690" height="604" rx="9" fill="none" stroke="#2c5668"/>']
    past = history[max(0, frame - 7):frame + 1]
    for i, p in enumerate(history[frame]):
        trail = " ".join("%.2f,%.2f" % (370 + s[i].x * 302, 397 + s[i].y * 259) for s in past)
        out.append('<polyline points="%s" fill="none" stroke="#56c8d0" stroke-width="1" opacity=".26"/>' % trail)
        out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" opacity="%.3f"/>' % (
            370 + 302 * p.x, 397 + 259 * p.y, 1.3 + 3 * p.material, "#efd4a0" if i % 7 == 0 else "#8aecf1", max(.1, min(1, p.material))))
    out.append("</svg>")
    return "\n".join(out)


def render(plan, dest, frames=32, n=120):
    """A/B SVG frame folders + plan.json + report.json with per-file sha256 (local output only)."""
    dest = Path(dest)
    a, b, _ = simulate(plan, frames, n)
    rep, files = experiment(plan, frames, n), {}
    for label, hist, flag in (("a_coupled", a, True), ("b_control", b, False)):
        (dest / label).mkdir(parents=True, exist_ok=True)
        files[label] = {}
        for k in range(len(hist)):
            data = frame_svg(hist, k, plan["law"], flag)
            (dest / label / ("%03d.svg" % k)).write_text(data, encoding="utf8", newline="\n")
            files[label]["%03d.svg" % k] = hashlib.sha256(data.encode("utf8")).hexdigest()
    rep.update(files_sha256=files, status="RENDER_TESTED_PENDING_REVIEW")
    (dest / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf8")
    (dest / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf8")
    return rep


def verify_render(report_path):
    base = Path(report_path).parent
    rep = json.loads(Path(report_path).read_text(encoding="utf8"))
    if digest(json.loads((base / "plan.json").read_text(encoding="utf8"))) != rep.get("recipe_sha256") or not rep.get("files_sha256"):
        return False
    return all((base / d / name).is_file() and hashlib.sha256((base / d / name).read_bytes()).hexdigest() == sha
               for d, entries in rep["files_sha256"].items() for name, sha in entries.items())


def load_plan(path):
    doc = json.loads(Path(path).read_text(encoding="utf8"))
    return doc["recipes"][0] if "recipes" in doc else doc


def atoms():
    return json.loads(ATOMS.read_text(encoding="utf8"))["atoms"]
