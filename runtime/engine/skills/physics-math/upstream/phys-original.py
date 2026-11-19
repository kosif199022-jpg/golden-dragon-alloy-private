#!/usr/bin/env python3
"""phys.py — حاسبة الرياضيات والفيزياء للمونتاج والموشن والـ 3D.

Pure Python (stdlib only). Every command prints JSON so Claude can read it.
Run `python phys.py <command> --help` for each command.

Commands:
  calc       safe math expression (math funcs + physics constants)
  convert    unit conversion (length, mass, speed, volume, force, energy, temp, data...)
  shape      area / volume / surface of shapes (+ mass & weight with --material)
  material   list densities
  motion     solve distance / speed / time (any two)
  fall       free fall: height <-> time, impact speed, per-frame keyframes
  projectile thrown object: range, apex, flight time, per-frame x/y keyframes
  bounce     bouncing ball: contact times/frames, bounce heights
  spring     damped spring (overshoot) keyframes for motion graphics
  ease       easing curve values per frame (Penner set + cubic-bezier)
  camera     fov | fit | dof | dolly | shutter | parallax
  tc         timecode <-> frames <-> seconds
  speed      retime / slow-motion factors + ffmpeg filters
  beats      BPM -> beat times and frames
  frame      fit/fill scaling, crop for aspect change, safe zones
  audio      dB <-> ratio, LUFS gain, sound delay, wavelength
  track      pixels moved -> real speed (m/s, km/h)
  scale      real-world size <-> pixels / Blender units, miniature (scale-model) fps
"""
import argparse
import json
import math
import sys

G = 9.80665
SOUND = 343.0  # m/s at 20 C

# ---------------------------------------------------------------- output

def out(obj):
    def clean(v):
        if isinstance(v, float):
            if math.isinf(v):
                return "inf"
            if math.isnan(v):
                return "nan"
            return round(v, 6)
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        return v
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(clean(obj), ensure_ascii=False, indent=2))


def save_keys(args, rows):
    """Optionally write per-frame rows to --out (.json or .csv)."""
    path = getattr(args, "out", None)
    if not path:
        return None
    if path.lower().endswith(".csv"):
        keys = list(rows[0].keys()) if rows else []
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(",".join(keys) + "\n")
            for r in rows:
                f.write(",".join(str(round(r[k], 6)) if isinstance(r[k], float) else str(r[k]) for k in keys) + "\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    return path

# ---------------------------------------------------------------- units

UNITS = {
    "length": {"m": 1, "cm": 0.01, "mm": 0.001, "um": 1e-6, "km": 1000, "in": 0.0254,
               "ft": 0.3048, "yd": 0.9144, "mi": 1609.344, "nmi": 1852},
    "mass": {"kg": 1, "g": 0.001, "mg": 1e-6, "t": 1000, "lb": 0.45359237, "oz": 0.028349523125},
    "time": {"s": 1, "ms": 0.001, "us": 1e-6, "min": 60, "h": 3600, "day": 86400, "week": 604800, "year": 31557600},
    "speed": {"m/s": 1, "km/h": 1 / 3.6, "kmh": 1 / 3.6, "mph": 0.44704, "kn": 1852 / 3600,
              "ft/s": 0.3048, "mach": SOUND, "c": 299792458},
    "accel": {"m/s2": 1, "g0": G, "ft/s2": 0.3048},
    "area": {"m2": 1, "cm2": 1e-4, "mm2": 1e-6, "km2": 1e6, "ha": 1e4, "ft2": 0.09290304,
             "in2": 0.00064516, "acre": 4046.8564224, "feddan": 4200.83},
    "volume": {"m3": 1, "l": 1e-3, "ml": 1e-6, "cm3": 1e-6, "mm3": 1e-9, "ft3": 0.028316846592,
               "in3": 1.6387064e-5, "gal": 0.003785411784, "ukgal": 0.00454609, "floz": 2.95735e-5, "bbl": 0.158987294928},
    "angle": {"deg": math.pi / 180, "rad": 1, "turn": 2 * math.pi, "grad": math.pi / 200},
    "force": {"N": 1, "kN": 1000, "kgf": G, "lbf": 4.4482216152605},
    "energy": {"J": 1, "kJ": 1000, "MJ": 1e6, "cal": 4.184, "kcal": 4184, "Wh": 3600, "kWh": 3.6e6, "eV": 1.602176634e-19},
    "power": {"W": 1, "kW": 1000, "MW": 1e6, "hp": 745.69987158227},
    "pressure": {"Pa": 1, "kPa": 1000, "MPa": 1e6, "bar": 1e5, "atm": 101325, "psi": 6894.757293168, "mmHg": 133.322387415},
    "density": {"kg/m3": 1, "g/cm3": 1000, "g/ml": 1000, "lb/ft3": 16.01846337},
    "data": {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12, "KiB": 1024, "MiB": 1024 ** 2,
             "GiB": 1024 ** 3, "TiB": 1024 ** 4, "bit": 1 / 8, "Kbit": 125, "Mbit": 125000, "Gbit": 1.25e8},
    "bitrate": {"bps": 1, "kbps": 1e3, "Mbps": 1e6, "Gbps": 1e9, "B/s": 8, "MB/s": 8e6},
    "freq": {"Hz": 1, "kHz": 1e3, "MHz": 1e6, "rpm": 1 / 60, "bpm": 1 / 60},
}
TEMPS = {"C", "F", "K"}


def find_unit(u):
    for dim, table in UNITS.items():
        if u in table:
            return dim, table[u]
    low = u.lower()
    for dim, table in UNITS.items():
        for k, v in table.items():
            if k.lower() == low:
                return dim, v
    raise SystemExit(f"unknown unit: {u}")


def to_kelvin(v, u):
    return {"C": v + 273.15, "F": (v - 32) * 5 / 9 + 273.15, "K": v}[u]


def from_kelvin(k, u):
    return {"C": k - 273.15, "F": (k - 273.15) * 9 / 5 + 32, "K": k}[u]


def cmd_convert(a):
    if a.src in TEMPS or a.dst in TEMPS:
        r = from_kelvin(to_kelvin(a.value, a.src), a.dst)
        return out({"value": a.value, "from": a.src, "to": a.dst, "result": r, "dimension": "temperature"})
    d1, f1 = find_unit(a.src)
    d2, f2 = find_unit(a.dst)
    if d1 != d2:
        raise SystemExit(f"cannot convert {d1} to {d2}")
    out({"value": a.value, "from": a.src, "to": a.dst, "result": a.value * f1 / f2, "dimension": d1})

# ---------------------------------------------------------------- calc

SAFE = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
SAFE.update({"abs": abs, "min": min, "max": max, "round": round, "sum": sum,
             "g": G, "c": 299792458.0, "sound": SOUND, "deg": math.pi / 180,
             "G_const": 6.67430e-11, "rho_water": 1000.0, "rho_air": 1.225})


def cmd_calc(a):
    expr = a.expr.replace("^", "**")
    code = compile(expr, "<calc>", "eval")
    for name in code.co_names:
        if name not in SAFE:
            raise SystemExit(f"name not allowed: {name}")
    out({"expr": a.expr, "result": eval(code, {"__builtins__": {}}, SAFE)})

# ---------------------------------------------------------------- materials

DENSITY = {  # kg/m3
    "water": 1000, "seawater": 1025, "ice": 917, "snow": 300, "air": 1.225, "helium": 0.1786,
    "steel": 7850, "iron": 7874, "aluminum": 2700, "copper": 8960, "brass": 8500, "gold": 19320,
    "silver": 10490, "lead": 11340, "titanium": 4506, "platinum": 21450,
    "glass": 2500, "concrete": 2400, "brick": 1900, "marble": 2700, "granite": 2750, "sand": 1600,
    "wet_sand": 1900, "soil": 1500, "clay": 1750, "stone": 2600,
    "wood_oak": 750, "wood_pine": 500, "wood_balsa": 160, "cork": 240, "paper": 800, "cardboard": 690,
    "plastic_abs": 1050, "plastic_pla": 1240, "pvc": 1380, "acrylic": 1180, "rubber": 1100,
    "foam": 30, "styrofoam": 50, "human_body": 985, "bone": 1900, "fat": 900, "muscle": 1060,
    "oil": 900, "gasoline": 745, "milk": 1030, "honey": 1420, "mercury": 13534,
    "chocolate": 1325, "bread": 250, "cotton": 1540, "diamond": 3510,
}


def cmd_material(a):
    items = sorted(DENSITY.items(), key=lambda kv: kv[1])
    out({"unit": "kg/m3", "materials": dict(items)})


def mass_info(volume_m3, material, density):
    rho = density if density else (DENSITY.get(material) if material else None)
    if material and rho is None:
        raise SystemExit(f"unknown material: {material} (see: material)")
    if rho is None:
        return {}
    m = rho * volume_m3
    return {"density_kg_m3": rho, "mass_kg": m, "weight_N": m * G, "weight_kgf": m,
            "floats_in_water": rho < 1000}

# ---------------------------------------------------------------- shapes

def cmd_shape(a):
    f = UNITS["length"][a.unit]
    p = {k: (v * f if v is not None else None) for k, v in
         dict(a=a.a, b=a.b, c=a.c, r=a.r, r2=a.r2, h=a.h).items()}
    s = a.shape
    A = V = S = P = None
    if s == "square":
        A, P = p["a"] ** 2, 4 * p["a"]
    elif s == "rect":
        A, P = p["a"] * p["b"], 2 * (p["a"] + p["b"])
    elif s == "circle":
        A, P = math.pi * p["r"] ** 2, 2 * math.pi * p["r"]
    elif s == "ellipse":
        x, y = p["a"], p["b"]
        A = math.pi * x * y
        hh = ((x - y) / (x + y)) ** 2
        P = math.pi * (x + y) * (1 + 3 * hh / (10 + math.sqrt(4 - 3 * hh)))
    elif s == "triangle":  # sides a b c (Heron)
        x, y, z = p["a"], p["b"], p["c"]
        sp = (x + y + z) / 2
        A, P = math.sqrt(max(sp * (sp - x) * (sp - y) * (sp - z), 0)), x + y + z
    elif s == "cube":
        V, S = p["a"] ** 3, 6 * p["a"] ** 2
    elif s == "box":
        x, y, z = p["a"], p["b"], p["c"]
        V, S = x * y * z, 2 * (x * y + y * z + x * z)
    elif s == "sphere":
        V, S = 4 / 3 * math.pi * p["r"] ** 3, 4 * math.pi * p["r"] ** 2
    elif s == "hemisphere":
        V, S = 2 / 3 * math.pi * p["r"] ** 3, 3 * math.pi * p["r"] ** 2
    elif s == "cylinder":
        V, S = math.pi * p["r"] ** 2 * p["h"], 2 * math.pi * p["r"] * (p["r"] + p["h"])
    elif s == "tube":  # outer r, inner r2
        V = math.pi * (p["r"] ** 2 - p["r2"] ** 2) * p["h"]
        S = 2 * math.pi * (p["r"] + p["r2"]) * p["h"] + 2 * math.pi * (p["r"] ** 2 - p["r2"] ** 2)
    elif s == "cone":
        sl = math.hypot(p["r"], p["h"])
        V, S = math.pi * p["r"] ** 2 * p["h"] / 3, math.pi * p["r"] * (p["r"] + sl)
    elif s == "frustum":  # r bottom, r2 top
        r1, r2, h = p["r"], p["r2"], p["h"]
        sl = math.hypot(r1 - r2, h)
        V = math.pi * h * (r1 * r1 + r1 * r2 + r2 * r2) / 3
        S = math.pi * (r1 + r2) * sl + math.pi * (r1 * r1 + r2 * r2)
    elif s == "pyramid":  # square base a, height h
        sl = math.hypot(p["a"] / 2, p["h"])
        V, S = p["a"] ** 2 * p["h"] / 3, p["a"] ** 2 + 2 * p["a"] * sl
    elif s == "torus":  # r major, r2 minor
        V, S = 2 * math.pi ** 2 * p["r"] * p["r2"] ** 2, 4 * math.pi ** 2 * p["r"] * p["r2"]
    elif s == "ellipsoid":
        x, y, z = p["a"], p["b"], p["c"]
        V = 4 / 3 * math.pi * x * y * z
        pp = 1.6075
        S = 4 * math.pi * (((x * y) ** pp + (x * z) ** pp + (y * z) ** pp) / 3) ** (1 / pp)
    else:
        raise SystemExit("unknown shape")
    res = {"shape": s, "input_unit": a.unit}
    if A is not None:
        res.update({"area_m2": A, "area_cm2": A * 1e4, "perimeter_m": P})
    if V is not None:
        res.update({"volume_m3": V, "volume_liters": V * 1000, "surface_m2": S})
        res.update(mass_info(V * a.fill, a.material, a.density))
        if a.fill != 1:
            res["fill_fraction"] = a.fill
    out(res)

# ---------------------------------------------------------------- motion

def cmd_motion(a):
    d, v, t = a.distance, a.speed, a.time
    if [d, v, t].count(None) != 1:
        raise SystemExit("give exactly two of --distance (m) --speed (m/s) --time (s)")
    if d is None:
        d = v * t
    elif v is None:
        v = d / t
    else:
        t = d / v
    res = {"distance_m": d, "speed_m_s": v, "speed_km_h": v * 3.6, "time_s": t}
    if a.fps:
        res["frames"] = t * a.fps
        res["meters_per_frame"] = d / (t * a.fps)
    out(res)


def cmd_fall(a):
    g = a.g
    if a.height is not None:
        h = a.height
        t = math.sqrt(2 * h / g)
    elif a.time is not None:
        t = a.time
        h = 0.5 * g * t * t
    else:
        raise SystemExit("give --height or --time")
    v = g * t
    res = {"height_m": h, "time_s": t, "impact_speed_m_s": v, "impact_speed_km_h": v * 3.6,
           "frames": t * a.fps, "fps": a.fps, "gravity": g,
           "note": "vacuum; real objects slow down with air drag (use --drag)"}
    if a.mass:
        res["impact_energy_J"] = 0.5 * a.mass * v * v
    rows = []
    n = int(math.ceil(t * a.fps))
    if a.drag:  # quadratic drag: terminal velocity vt
        vt = a.drag
        tt = vt / g * math.acosh(math.exp(h * g / (vt * vt)))
        res.update({"terminal_velocity_m_s": vt, "time_with_drag_s": tt,
                    "impact_speed_with_drag_m_s": vt * math.tanh(g * tt / vt), "frames_with_drag": tt * a.fps})
        n = int(math.ceil(tt * a.fps))
        for i in range(n + 1):
            ti = min(i / a.fps, tt)
            y = vt * vt / g * math.log(math.cosh(g * ti / vt))
            rows.append({"frame": i, "t": ti, "fallen_m": y, "height_m": h - y})
    else:
        for i in range(n + 1):
            ti = min(i / a.fps, t)
            y = 0.5 * g * ti * ti
            rows.append({"frame": i, "t": ti, "fallen_m": y, "height_m": h - y})
    p = save_keys(a, rows)
    if p:
        res["keyframes_file"] = p
    elif a.keys:
        res["keyframes"] = rows
    out(res)


def cmd_projectile(a):
    g, v, th, h0 = a.g, a.speed, math.radians(a.angle), a.h0
    vx, vy = v * math.cos(th), v * math.sin(th)
    t = (vy + math.sqrt(vy * vy + 2 * g * h0)) / g
    apex_t = max(vy / g, 0)
    res = {"flight_time_s": t, "range_m": vx * t, "apex_height_m": h0 + vy * apex_t - 0.5 * g * apex_t ** 2,
           "apex_time_s": apex_t, "apex_frame": apex_t * a.fps, "landing_frame": t * a.fps,
           "impact_speed_m_s": math.hypot(vx, vy - g * t), "fps": a.fps}
    if a.angle_best:
        res["max_range_angle_deg"] = 45.0 if h0 == 0 else math.degrees(math.atan(v / math.sqrt(v * v + 2 * g * h0)))
    rows = []
    for i in range(int(math.ceil(t * a.fps)) + 1):
        ti = min(i / a.fps, t)
        rows.append({"frame": i, "t": ti, "x_m": vx * ti, "y_m": h0 + vy * ti - 0.5 * g * ti * ti})
    p = save_keys(a, rows)
    if p:
        res["keyframes_file"] = p
    elif a.keys:
        res["keyframes"] = rows
    out(res)


def cmd_bounce(a):
    g, h, e = a.g, a.height, a.restitution
    t = math.sqrt(2 * h / g)
    contacts = [{"bounce": 0, "t": t, "frame": t * a.fps, "next_height_m": h * e * e}]
    hn = h
    for n in range(1, a.count + 1):
        hn = hn * e * e
        if hn < a.min_height:
            break
        air = 2 * math.sqrt(2 * hn / g)
        t += air
        contacts.append({"bounce": n, "apex_height_m": hn, "airtime_s": air, "t": t, "frame": t * a.fps})
    total = t
    res = {"drop_height_m": h, "restitution": e, "fps": a.fps, "contacts": contacts, "total_time_s": total,
           "total_frames": total * a.fps,
           "tip": "e: rubber ball 0.8, basketball 0.75, tennis 0.7, wood 0.5, clay ~0"}
    if a.keys or a.out:
        rows = []
        times = [0.0] + [c["t"] for c in contacts]
        heights = [h] + [c.get("apex_height_m") for c in contacts[1:]]
        for i in range(int(math.ceil(total * a.fps)) + 1):
            ti = min(i / a.fps, total)
            if ti <= times[1]:
                y = h - 0.5 * g * ti * ti
            else:
                k = max(j for j in range(1, len(times)) if times[j] <= ti)
                if k >= len(heights):
                    y = 0.0
                else:
                    hk = heights[k]
                    v0 = math.sqrt(2 * g * hk)
                    dt = ti - times[k]
                    y = max(v0 * dt - 0.5 * g * dt * dt, 0.0)
            rows.append({"frame": i, "t": ti, "y_m": y})
        p = save_keys(a, rows)
        if p:
            res["keyframes_file"] = p
        else:
            res["keyframes"] = rows
    out(res)


def cmd_spring(a):
    m, k, c = a.mass, a.stiffness, a.damping
    w0 = math.sqrt(k / m)
    zeta = c / (2 * math.sqrt(k * m))
    x, v = a.start - a.end, a.velocity
    dt = 1.0 / (a.fps * 50)
    rows, settle, peak = [], None, None
    total_frames = int(a.seconds * a.fps)
    sub = 50
    for i in range(total_frames + 1):
        val = a.end + x
        rows.append({"frame": i, "t": i / a.fps, "value": val})
        tol = (abs(a.start - a.end) or 1) * a.tolerance
        if abs(x) > tol or abs(v) > tol * a.fps:
            settle = None
        elif settle is None:
            settle = i
        for _ in range(sub):
            acc = (-k * x - c * v) / m
            v += acc * dt
            x += v * dt
    span = a.end - a.start
    if span:
        over = max(((r["value"] - a.end) / span for r in rows), default=0)
        peak = over * 100
    res = {"natural_freq_hz": w0 / (2 * math.pi), "damping_ratio": zeta,
           "type": "underdamped (bouncy)" if zeta < 1 else ("critical" if abs(zeta - 1) < 1e-9 else "overdamped"),
           "overshoot_percent": peak, "settle_frame": settle if settle is not None else "not settled - raise --seconds", "fps": a.fps,
           "tip": "zeta 0.3-0.5 = playful pop, 0.7 = smooth UI, 1 = no bounce"}
    p = save_keys(a, rows)
    if p:
        res["keyframes_file"] = p
    elif a.keys:
        res["keyframes"] = rows
    out(res)

# ---------------------------------------------------------------- easing

def _bounce_out(t):
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


BASE_IN = {
    "linear": lambda t: t,
    "sine": lambda t: 1 - math.cos(t * math.pi / 2),
    "quad": lambda t: t ** 2, "cubic": lambda t: t ** 3, "quart": lambda t: t ** 4, "quint": lambda t: t ** 5,
    "expo": lambda t: 0 if t == 0 else 2 ** (10 * t - 10),
    "circ": lambda t: 1 - math.sqrt(1 - t * t),
    "back": lambda t: 2.70158 * t ** 3 - 1.70158 * t ** 2,
    "elastic": lambda t: t if t in (0, 1) else -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * 2 * math.pi / 3),
    "bounce": lambda t: 1 - _bounce_out(1 - t),
}


def easing(name):
    """name like easeInOutCubic / in-out-cubic / cubic-bezier(.4,0,.2,1)."""
    n = name.replace("-", "").replace("_", "").lower()
    if n.startswith("cubicbezier"):
        x1, y1, x2, y2 = [float(v) for v in name[name.index("(") + 1:name.index(")")].split(",")]
        return bezier(x1, y1, x2, y2)
    if n == "linear":
        return BASE_IN["linear"]
    n = n.replace("ease", "")
    for mode in ("inout", "in", "out"):
        if n.startswith(mode):
            base = BASE_IN.get(n[len(mode):])
            if base is None:
                break
            if mode == "in":
                return base
            if mode == "out":
                return lambda t, f=base: 1 - f(1 - t)
            return lambda t, f=base: f(2 * t) / 2 if t < 0.5 else 1 - f(2 - 2 * t) / 2
    raise SystemExit(f"unknown easing: {name}. use e.g. easeInOutCubic, easeOutBack, cubic-bezier(.25,.1,.25,1)")


def bezier(x1, y1, x2, y2):
    def bx(s): return 3 * x1 * s * (1 - s) ** 2 + 3 * x2 * s * s * (1 - s) + s ** 3
    def by(s): return 3 * y1 * s * (1 - s) ** 2 + 3 * y2 * s * s * (1 - s) + s ** 3

    def f(t):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if bx(mid) < t:
                lo = mid
            else:
                hi = mid
        return by((lo + hi) / 2)
    return f


def cmd_ease(a):
    f = easing(a.curve)
    frames = a.frames if a.frames else int(round(a.seconds * a.fps))
    rows = []
    for i in range(frames + 1):
        t = i / frames if frames else 1
        p = f(t)
        rows.append({"frame": a.start_frame + i, "progress": p, "value": a.start + (a.end - a.start) * p})
    res = {"curve": a.curve, "frames": frames, "fps": a.fps, "from": a.start, "to": a.end}
    pth = save_keys(a, rows)
    if pth:
        res["keyframes_file"] = pth
    else:
        res["keyframes"] = rows
    out(res)

# ---------------------------------------------------------------- camera

SENSORS = {  # width, height mm
    "ff": (36, 24), "aps-c": (23.5, 15.6), "canon-apsc": (22.3, 14.9), "s35": (24.89, 18.66),
    "mft": (17.3, 13), "1in": (13.2, 8.8), "iphone": (9.8, 7.3), "blender": (36, 24), "65mm": (54.12, 25.58),
}


def sensor_dims(a):
    if a.sensor_w:
        return a.sensor_w, a.sensor_h or a.sensor_w * 2 / 3
    return SENSORS[a.sensor]


def cmd_camera(a):
    sw, sh = sensor_dims(a)
    m = a.mode
    if m == "fov":
        f = a.focal
        hf = 2 * math.degrees(math.atan(sw / (2 * f)))
        vf = 2 * math.degrees(math.atan(sh / (2 * f)))
        df = 2 * math.degrees(math.atan(math.hypot(sw, sh) / (2 * f)))
        res = {"focal_mm": f, "sensor_mm": [sw, sh], "hfov_deg": hf, "vfov_deg": vf, "dfov_deg": df,
               "crop_factor": 43.2666 / math.hypot(sw, sh), "ff_equiv_focal_mm": f * 43.2666 / math.hypot(sw, sh)}
        if a.distance:
            res["frame_width_at_distance_m"] = a.distance * sw / f
            res["frame_height_at_distance_m"] = a.distance * sh / f
        if a.fov:
            res["focal_for_hfov_mm"] = sw / (2 * math.tan(math.radians(a.fov) / 2))
        return out(res)
    if m == "fit":  # distance so object fills fraction of frame
        dim = sh if a.axis == "h" else sw
        d = a.object * a.focal / (dim * a.fill) / 1.0
        return out({"object_m": a.object, "focal_mm": a.focal, "axis": a.axis, "fill": a.fill,
                    "camera_distance_m": d, "tip": "subject distance from lens; add half the object depth for its center"})
    if m == "dof":
        f, N, s = a.focal, a.fstop, a.distance * 1000
        coc = a.coc or math.hypot(sw, sh) / 1442
        H = f * f / (N * coc) + f
        near = s * (H - f) / (H + s - 2 * f)
        far = s * (H - f) / (H - s) if s < H else math.inf
        return out({"focal_mm": f, "fstop": N, "focus_m": a.distance, "coc_mm": coc,
                    "hyperfocal_m": H / 1000, "near_m": near / 1000, "far_m": far / 1000 if far != math.inf else "inf",
                    "dof_total_m": (far - near) / 1000 if far != math.inf else "inf"})
    if m == "dolly":  # vertigo: keep subject size while focal changes
        d2 = a.distance * a.focal2 / a.focal
        return out({"start_focal_mm": a.focal, "end_focal_mm": a.focal2, "start_distance_m": a.distance,
                    "end_distance_m": d2, "camera_travel_m": d2 - a.distance,
                    "rule": "distance / focal stays constant"})
    if m == "shutter":
        exp = a.angle / 360 / a.fps
        res = {"fps": a.fps, "shutter_angle_deg": a.angle, "exposure_s": exp, "shutter_fraction": f"1/{round(1 / exp)}",
               "ffmpeg_tmix_frames_hint": max(1, round(a.angle / 360 * (a.source_fps or a.fps) / a.fps))}
        if a.px_per_frame:
            res["motion_blur_px"] = a.px_per_frame * a.angle / 360
        return out(res)
    if m == "parallax":  # how much a layer moves relative to the camera move
        res = {"camera_move_m": a.move, "layers": []}
        for depth in a.depths:
            px = a.move * a.focal / sw * a.width / depth
            res["layers"].append({"depth_m": depth, "screen_shift_px": px, "relative_to_nearest": None})
        base = res["layers"][0]["screen_shift_px"] if res["layers"] else 1
        for L in res["layers"]:
            L["relative_to_nearest"] = L["screen_shift_px"] / base
        return out(res)

# ---------------------------------------------------------------- time

def parse_tc(tc, fps):
    parts = tc.replace(";", ":").split(":")
    if len(parts) == 4:
        h, m, s, f = map(float, parts)
        return (h * 3600 + m * 60 + s) * fps + f
    if len(parts) == 3:
        h, m, s = map(float, parts)
        return (h * 3600 + m * 60 + s) * fps
    if len(parts) == 2:
        m, s = map(float, parts)
        return (m * 60 + s) * fps
    return float(parts[0]) * fps


def fmt_tc(frames, fps):
    fr = int(round(frames))
    ifps = int(round(fps))
    f = fr % ifps
    s_total = fr // ifps
    return f"{s_total // 3600:02d}:{s_total // 60 % 60:02d}:{s_total % 60:02d}:{f:02d}"


def cmd_tc(a):
    if a.timecode:
        fr = parse_tc(a.timecode, a.fps)
    elif a.frames is not None:
        fr = a.frames
    elif a.seconds is not None:
        fr = a.seconds * a.fps
    else:
        raise SystemExit("give --timecode, --frames or --seconds")
    sec = fr / a.fps
    res = {"fps": a.fps, "frames": fr, "seconds": sec, "timecode": fmt_tc(fr, a.fps),
           "ffmpeg_time": f"{int(sec // 3600):02d}:{int(sec // 60 % 60):02d}:{sec % 60:06.3f}"}
    if a.to_fps:
        res[f"frames_at_{a.to_fps}fps"] = sec * a.to_fps
        res[f"timecode_at_{a.to_fps}fps"] = fmt_tc(sec * a.to_fps, a.to_fps)
    out(res)


def atempo_chain(r):
    parts = []
    while r > 2.0:
        parts.append(2.0)
        r /= 2.0
    while r < 0.5:
        parts.append(0.5)
        r /= 0.5
    parts.append(r)
    return ",".join(f"atempo={p:.6g}" for p in parts)


def cmd_speed(a):
    if a.shot_fps:
        speed = a.timeline_fps / a.shot_fps
        res = {"shot_fps": a.shot_fps, "timeline_fps": a.timeline_fps, "speed": speed,
               "slowmo_factor": 1 / speed, "note": "conform: play every frame -> real slow motion, no interpolation"}
        if a.duration:
            res["real_seconds"] = a.duration
            res["on_timeline_seconds"] = a.duration / speed
    elif a.duration and a.target:
        speed = a.duration / a.target
        res = {"source_s": a.duration, "target_s": a.target, "speed": speed}
    elif a.factor:
        speed = a.factor
        res = {"speed": speed}
        if a.duration:
            res["new_duration_s"] = a.duration / speed
    else:
        raise SystemExit("give --shot-fps, or --duration with --target, or --factor")
    res.update({"percent": speed * 100, "ffmpeg_video": f"setpts={1 / speed:.6g}*PTS",
                "ffmpeg_audio": atempo_chain(speed)})
    if speed < 1 and not a.shot_fps:
        res["warn"] = "slowing normal-fps footage duplicates frames; use minterpolate/RIFE for smooth slow-mo"
    out(res)


def cmd_beats(a):
    spb = 60 / a.bpm * a.every
    n = a.count or int((a.duration - a.offset) / spb) + 1
    rows = []
    for i in range(n):
        t = a.offset + i * spb
        rows.append({"beat": i + 1, "bar": i // a.per_bar + 1, "t": t, "frame": round(t * a.fps), "timecode": fmt_tc(t * a.fps, a.fps)})
    res = {"bpm": a.bpm, "seconds_per_beat": 60 / a.bpm, "frames_per_beat": 60 / a.bpm * a.fps,
           "seconds_per_bar": 60 / a.bpm * a.per_bar, "fps": a.fps}
    p = save_keys(a, rows)
    if p:
        res["beats_file"] = p
    else:
        res["beats"] = rows
    out(res)

# ---------------------------------------------------------------- frame

def wh(s):
    w, h = s.lower().split("x")
    return float(w), float(h)


def cmd_frame(a):
    sw, sh = wh(a.src)
    dw, dh = wh(a.dst)
    fit = min(dw / sw, dh / sh)
    fill = max(dw / sw, dh / sh)
    g = math.gcd(int(sw), int(sh))
    res = {"src": a.src, "dst": a.dst, "src_aspect": f"{int(sw) // g}:{int(sh) // g}", "src_ratio": sw / sh,
           "dst_ratio": dw / dh,
           "fit": {"scale": fit, "size": [sw * fit, sh * fit], "pad": [(dw - sw * fit) / 2, (dh - sh * fit) / 2],
                   "ffmpeg": f"scale={int(dw)}:{int(dh)}:force_original_aspect_ratio=decrease,pad={int(dw)}:{int(dh)}:(ow-iw)/2:(oh-ih)/2"},
           "fill": {"scale": fill, "size": [sw * fill, sh * fill],
                    "crop_in_source": {"w": dw / fill, "h": dh / fill, "x": (sw - dw / fill) / 2, "y": (sh - dh / fill) / 2},
                    "kept_percent_of_source": 100 * (dw / fill) * (dh / fill) / (sw * sh),
                    "ffmpeg": f"scale={int(dw)}:{int(dh)}:force_original_aspect_ratio=increase,crop={int(dw)}:{int(dh)}"},
           "safe_zones_dst": {"action_safe_90": [dw * 0.05, dh * 0.05, dw * 0.95, dh * 0.95],
                              "title_safe_80": [dw * 0.1, dh * 0.1, dw * 0.9, dh * 0.9]}}
    if dh > dw:  # vertical social
        res["safe_zones_dst"]["reels_ui_safe"] = {"top_px": dh * 0.11, "bottom_px": dh * 0.21, "right_px": dw * 0.13,
                                                  "note": "keep text out of these margins (TikTok/Reels UI)"}
    out(res)

# ---------------------------------------------------------------- audio

def cmd_audio(a):
    res = {}
    if a.db is not None:
        res.update({"db": a.db, "amplitude_ratio": 10 ** (a.db / 20), "power_ratio": 10 ** (a.db / 10)})
    if a.ratio is not None:
        res.update({"amplitude_ratio": a.ratio, "db": 20 * math.log10(a.ratio)})
    if a.from_lufs is not None:
        gain = a.to_lufs - a.from_lufs
        res.update({"from_lufs": a.from_lufs, "to_lufs": a.to_lufs, "gain_db": gain,
                    "ffmpeg": f"volume={gain:+.2f}dB", "targets": {"youtube": -14, "instagram/tiktok": -14,
                                                                   "spotify": -14, "apple": -16, "broadcast_EBU_R128": -23}})
        if a.peak is not None:
            res["new_peak_dbtp"] = a.peak + gain
            res["clips"] = a.peak + gain > -1
    if a.distance is not None:
        dly = a.distance / SOUND
        res.update({"distance_m": a.distance, "sound_delay_ms": dly * 1000,
                    "delay_frames_at_fps": dly * a.fps, "inverse_square_drop_db_vs_1m": 20 * math.log10(a.distance) if a.distance > 0 else 0})
    if a.freq is not None:
        res.update({"freq_hz": a.freq, "wavelength_m": SOUND / a.freq, "period_ms": 1000 / a.freq,
                    "note": note_name(a.freq)})
    if not res:
        raise SystemExit("give --db, --ratio, --from-lufs, --distance or --freq")
    out(res)


def note_name(f):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    n = round(12 * math.log2(f / 440)) + 57
    return f"{names[n % 12]}{n // 12}"

# ---------------------------------------------------------------- tracking & scale

def cmd_track(a):
    if a.px_per_m:
        ppm = a.px_per_m
    elif a.ref_px and a.ref_m:
        ppm = a.ref_px / a.ref_m
    else:
        raise SystemExit("give --px-per-m or --ref-px with --ref-m (e.g. person 1.75 m = 420 px)")
    px = a.px / a.frames if a.frames else a.px
    v = px / ppm * a.fps
    out({"px_per_frame": px, "px_per_m": ppm, "fps": a.fps, "speed_m_s": v, "speed_km_h": v * 3.6,
         "note": "only valid for motion across the frame at the reference depth"})


def cmd_scale(a):
    res = {}
    if a.real is not None and a.px_per_m:
        res["pixels"] = a.real * a.px_per_m
    if a.model_scale:  # miniature: shoot faster so it looks real-size
        k = a.model_scale  # e.g. 12 for 1:12 model
        res.update({"model_scale": f"1:{k}", "time_factor": math.sqrt(k),
                    "shoot_fps_for_real_look": a.fps * math.sqrt(k),
                    "or_slow_down_to_percent": 100 / math.sqrt(k),
                    "rule": "Froude scaling: time scales with sqrt(length)"})
        if a.real is not None:
            res["model_size_m"] = a.real / k
    if a.blender_unit:
        res["blender"] = {"unit_scale": a.blender_unit,
                          "gravity_to_set_m_s2": G * a.blender_unit,
                          "note": "keep objects at real size in metres for correct physics"}
    if not res:
        raise SystemExit("give --model-scale, --real with --px-per-m, or --blender-unit")
    out(res)

# ---------------------------------------------------------------- cli

def main():
    P = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = P.add_subparsers(dest="cmd", required=True)

    def fpsarg(p, d=30.0):
        p.add_argument("--fps", type=float, default=d)

    def keyargs(p):
        p.add_argument("--keys", action="store_true", help="include per-frame keyframes in output")
        p.add_argument("--out", help="write per-frame rows to .json or .csv")

    p = sp.add_parser("calc"); p.add_argument("expr"); p.set_defaults(fn=cmd_calc)
    p = sp.add_parser("convert"); p.add_argument("value", type=float); p.add_argument("src"); p.add_argument("dst"); p.set_defaults(fn=cmd_convert)
    p = sp.add_parser("material"); p.set_defaults(fn=cmd_material)

    p = sp.add_parser("shape")
    p.add_argument("shape", choices=["square", "rect", "circle", "ellipse", "triangle", "cube", "box", "sphere", "hemisphere",
                                     "cylinder", "tube", "cone", "frustum", "pyramid", "torus", "ellipsoid"])
    for k in ("a", "b", "c", "r", "r2", "h"):
        p.add_argument(f"--{k}", type=float)
    p.add_argument("--unit", default="m", choices=list(UNITS["length"]))
    p.add_argument("--material"); p.add_argument("--density", type=float, help="kg/m3")
    p.add_argument("--fill", type=float, default=1.0, help="fraction filled (for liquids in a container)")
    p.set_defaults(fn=cmd_shape)

    p = sp.add_parser("motion"); p.add_argument("--distance", type=float); p.add_argument("--speed", type=float)
    p.add_argument("--time", type=float); p.add_argument("--fps", type=float); p.set_defaults(fn=cmd_motion)

    p = sp.add_parser("fall"); p.add_argument("--height", type=float); p.add_argument("--time", type=float)
    p.add_argument("--g", type=float, default=G); p.add_argument("--mass", type=float)
    p.add_argument("--drag", type=float, help="terminal velocity m/s (skydiver 55, ball 20, feather 1)")
    fpsarg(p); keyargs(p); p.set_defaults(fn=cmd_fall)

    p = sp.add_parser("projectile"); p.add_argument("--speed", type=float, required=True)
    p.add_argument("--angle", type=float, default=45); p.add_argument("--h0", type=float, default=0)
    p.add_argument("--g", type=float, default=G); p.add_argument("--angle-best", action="store_true")
    fpsarg(p); keyargs(p); p.set_defaults(fn=cmd_projectile)

    p = sp.add_parser("bounce"); p.add_argument("--height", type=float, required=True)
    p.add_argument("--restitution", type=float, default=0.7); p.add_argument("--count", type=int, default=8)
    p.add_argument("--min-height", type=float, default=0.005); p.add_argument("--g", type=float, default=G)
    fpsarg(p); keyargs(p); p.set_defaults(fn=cmd_bounce)

    p = sp.add_parser("spring"); p.add_argument("--start", type=float, default=0); p.add_argument("--end", type=float, default=1)
    p.add_argument("--mass", type=float, default=1); p.add_argument("--stiffness", type=float, default=170)
    p.add_argument("--damping", type=float, default=26); p.add_argument("--velocity", type=float, default=0)
    p.add_argument("--seconds", type=float, default=1.5); p.add_argument("--tolerance", type=float, default=0.001)
    fpsarg(p); keyargs(p); p.set_defaults(fn=cmd_spring)

    p = sp.add_parser("ease"); p.add_argument("curve"); p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=1); p.add_argument("--frames", type=int)
    p.add_argument("--seconds", type=float, default=1); p.add_argument("--start-frame", type=int, default=0)
    fpsarg(p); p.add_argument("--out"); p.set_defaults(fn=cmd_ease)

    p = sp.add_parser("camera"); p.add_argument("mode", choices=["fov", "fit", "dof", "dolly", "shutter", "parallax"])
    p.add_argument("--focal", type=float, default=50); p.add_argument("--focal2", type=float)
    p.add_argument("--sensor", default="ff", choices=list(SENSORS)); p.add_argument("--sensor-w", type=float)
    p.add_argument("--sensor-h", type=float); p.add_argument("--distance", type=float)
    p.add_argument("--fov", type=float, help="wanted horizontal FOV -> focal")
    p.add_argument("--object", type=float, help="object size m"); p.add_argument("--axis", choices=["w", "h"], default="h")
    p.add_argument("--fill", type=float, default=1.0); p.add_argument("--fstop", type=float, default=2.8)
    p.add_argument("--coc", type=float); p.add_argument("--angle", type=float, default=180)
    p.add_argument("--source-fps", type=float); p.add_argument("--px-per-frame", type=float)
    p.add_argument("--move", type=float, default=1.0); p.add_argument("--depths", type=float, nargs="*", default=[2, 5, 20])
    p.add_argument("--width", type=float, default=1920, help="frame width px for parallax")
    fpsarg(p, 24); p.set_defaults(fn=cmd_camera)

    p = sp.add_parser("tc"); p.add_argument("--timecode"); p.add_argument("--frames", type=float)
    p.add_argument("--seconds", type=float); p.add_argument("--to-fps", type=float); fpsarg(p); p.set_defaults(fn=cmd_tc)

    p = sp.add_parser("speed"); p.add_argument("--shot-fps", type=float); p.add_argument("--timeline-fps", type=float, default=30)
    p.add_argument("--duration", type=float); p.add_argument("--target", type=float); p.add_argument("--factor", type=float)
    p.set_defaults(fn=cmd_speed)

    p = sp.add_parser("beats"); p.add_argument("--bpm", type=float, required=True); p.add_argument("--count", type=int)
    p.add_argument("--duration", type=float, default=30); p.add_argument("--offset", type=float, default=0)
    p.add_argument("--every", type=float, default=1, help="1=every beat, 2=every 2 beats, 0.5=8th notes")
    p.add_argument("--per-bar", type=int, default=4); fpsarg(p); p.add_argument("--out"); p.set_defaults(fn=cmd_beats)

    p = sp.add_parser("frame"); p.add_argument("--src", required=True); p.add_argument("--dst", required=True); p.set_defaults(fn=cmd_frame)

    p = sp.add_parser("audio"); p.add_argument("--db", type=float); p.add_argument("--ratio", type=float)
    p.add_argument("--from-lufs", type=float); p.add_argument("--to-lufs", type=float, default=-14)
    p.add_argument("--peak", type=float, help="current true peak dBTP"); p.add_argument("--distance", type=float)
    p.add_argument("--freq", type=float); fpsarg(p); p.set_defaults(fn=cmd_audio)

    p = sp.add_parser("track"); p.add_argument("--px", type=float, required=True, help="pixels moved")
    p.add_argument("--frames", type=float, help="over how many frames (default 1)")
    p.add_argument("--px-per-m", type=float); p.add_argument("--ref-px", type=float); p.add_argument("--ref-m", type=float)
    fpsarg(p); p.set_defaults(fn=cmd_track)

    p = sp.add_parser("scale"); p.add_argument("--real", type=float, help="real size m"); p.add_argument("--px-per-m", type=float)
    p.add_argument("--model-scale", type=float, help="12 means a 1:12 miniature"); p.add_argument("--blender-unit", type=float)
    fpsarg(p, 24); p.set_defaults(fn=cmd_scale)

    a = P.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
