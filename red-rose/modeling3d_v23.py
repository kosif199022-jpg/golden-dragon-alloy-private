"""Red Rose V23: small, bounded, deterministic 3D modelling helpers (topics 18.01-18.10).

Pure standard-library Python (math, json, hashlib, struct, base64). No file I/O,
no subprocess, no network, no printing, no GPU and no Blender: every mesh,
simulation, projection and export is computed on the CPU in plain Python and
returned as data (OBJ/MTL text and glTF JSON come back as strings/dicts and are
never written anywhere).

Every op validates its inputs strictly (ValueError on bools-as-numbers,
non-finite values, unknown parameter names, missing companion inputs and
out-of-range values) and caps its work (<= 50k vertices, bounded steps and
samples). These are previz/teaching-grade models, not CAD, FEM or production
renderers: each op returns the assumptions it makes and the limits it enforces
next to its result. Units are metres / seconds / kilograms unless stated.
Coordinate convention: right-handed, +y up.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import struct

MAX_PARAMS = 24
MAX_VERTICES = 50_000
MAX_FACES = 100_000
MAX_POINTS = 10_000
COORD_LIMIT = 1e4

TOPICS = {
    '18.01': 'machine_mesh',
    '18.02': 'car_rig',
    '18.03': 'cloth3d',
    '18.04': 'camera3d',
    '18.05': 'skinning',
    '18.06': 'uv_atlas',
    '18.07': 'area_lighting',
    '18.08': 'export_mesh',
    '18.09': 'lod_budget',
    '18.10': 'cutaway',
}

TOPIC_NAMES_AR = {
    '18.01': 'نمذجة آلة ميكانيكية',
    '18.02': 'هيكل سيارة متحرك',
    '18.03': 'ملابس ثلاثية الأبعاد',
    '18.04': 'إعداد كاميرا ثلاثية الأبعاد',
    '18.05': 'تحريك عظام مع skinning',
    '18.06': 'خريطة UV للخامات',
    '18.07': 'إضاءة منطقة ومصادر',
    '18.08': 'تحويل OBJ وGLTF',
    '18.09': 'رندر تدريجي قليل الموارد',
    '18.10': 'عرض آلة مقطعية للتفسير',
}

NO_GPU = 'CPU-only pure Python: no GPU, no Blender, no external renderer or DCC tool is used'

_NAME_CHARS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.')


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name, *, low_open=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high or (low_open and value <= low):
        bracket = '(' if low_open else '['
        raise ValueError(f'{name} must be in {bracket}{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _vec(value, sizes, name, low=-COORD_LIMIT, high=COORD_LIMIT):
    if isinstance(sizes, int):
        sizes = (sizes,)
    if not isinstance(value, (list, tuple)) or len(value) not in sizes:
        raise ValueError(f'{name} must be a list of {" or ".join(map(str, sizes))} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _unit(value, name):
    v = _vec(value, 3, name)
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        raise ValueError(f'{name} must not be the zero vector')
    return [c / n for c in v]


def _list(value, name, low, high):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low} to {high} items')
    return list(value)


def _name(value, name):
    if (not isinstance(value, str) or not 1 <= len(value) <= 64
            or any(ch not in _NAME_CHARS for ch in value)):
        raise ValueError(f'{name} must be 1-64 characters from [A-Za-z0-9_.-]')
    return value


def _obj(value, allowed, required, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    bad = set(value) - set(allowed)
    if bad:
        raise ValueError(f'{name} has unknown key(s): ' + ', '.join(sorted(bad)))
    missing = set(required) - set(value)
    if missing:
        raise ValueError(f'{name} is missing required key(s): ' + ', '.join(sorted(missing)))
    return value


def _mesh(value, name, max_vertices=MAX_VERTICES):
    d = _obj(value, {'vertices', 'faces'}, {'vertices', 'faces'}, name)
    raw = _list(d['vertices'], f'{name}.vertices', 3, max_vertices)
    verts = [_vec(v, 3, f'{name}.vertices[{i}]') for i, v in enumerate(raw)]
    raw_faces = _list(d['faces'], f'{name}.faces', 1, MAX_FACES)
    n = len(verts)
    faces = []
    for i, f in enumerate(raw_faces):
        if not isinstance(f, (list, tuple)) or len(f) != 3:
            raise ValueError(f'{name}.faces[{i}] must be a triangle [a, b, c]')
        a, b, c = (_int(x, 0, n - 1, f'{name}.faces[{i}]') for x in f)
        if a == b or b == c or a == c:
            raise ValueError(f'{name}.faces[{i}] repeats a vertex index')
        faces.append([a, b, c])
    return {'vertices': verts, 'faces': faces}


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _decimate(seq, max_points):
    n = len(seq)
    if n <= max_points:
        return list(seq)
    idx = sorted({round(i * (n - 1) / (max_points - 1)) for i in range(max_points)})
    return [seq[i] for i in idx]


# --------------------------------------------------------------------------- vector / matrix math

def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _length(a):
    return math.sqrt(_dot(a, a))


def _normalize(a):
    n = _length(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-15 else [0.0, 0.0, 0.0]


def _m3mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _m3v(m, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]


def _rot3(deg):
    """Euler XYZ in degrees: R = Rz @ Ry @ Rx (x applied first)."""
    rx, ry, rz = (math.radians(d) for d in deg)
    cx, sx, cy, sy, cz, sz = (math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry),
                              math.cos(rz), math.sin(rz))
    mx = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    my = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]
    mz = [[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]]
    return _m3mul(mz, _m3mul(my, mx))


def _m4mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _m4_trs(t, r3, s):
    return [[r3[i][0] * s[0], r3[i][1] * s[1], r3[i][2] * s[2], t[i]] for i in range(3)] + \
        [[0.0, 0.0, 0.0, 1.0]]


def _m4_translate(t):
    return _m4_trs(t, [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], [1.0, 1.0, 1.0])


def _m4pt(m, p):
    return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3)]


def _m4v4(m, v):
    return [sum(m[i][k] * v[k] for k in range(4)) for i in range(4)]


def _quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw]


def _quat_from_euler(deg):
    """Quaternion (w, x, y, z) for R = Rz @ Ry @ Rx."""
    def axis_q(angle, axis):
        h = math.radians(angle) / 2
        q = [math.cos(h), 0.0, 0.0, 0.0]
        q[1 + axis] = math.sin(h)
        return q
    return _quat_mul(axis_q(deg[2], 2), _quat_mul(axis_q(deg[1], 1), axis_q(deg[0], 0)))


def _rot3_from_quat_xyzw(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def _bbox(points):
    lo = [min(p[k] for p in points) for k in range(3)]
    hi = [max(p[k] for p in points) for k in range(3)]
    return lo, hi


def _aabb_gap(a, b):
    """Largest separation along any axis (negative = overlap depth on the least-overlapping axis)."""
    return max(max(b[0][k] - a[1][k], a[0][k] - b[1][k]) for k in range(3))


def _volume(verts, faces):
    return sum(_dot(verts[a], _cross(verts[b], verts[c])) for a, b, c in faces) / 6.0


def _edges_of(faces):
    edges = set()
    for f in faces:
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            edges.add((a, b) if a < b else (b, a))
    return sorted(edges)


# --------------------------------------------------------------------------- mesh builders

def _box_mesh(size):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    verts = [[x, y, z] for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    faces = [[0, 1, 3], [0, 3, 2], [4, 7, 5], [4, 6, 7], [0, 4, 5], [0, 5, 1],
             [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return {'vertices': verts, 'faces': faces}


def _prism_mesh(radii, height):
    """Closed star-shaped prism along y: outline radii at equal angles, caps fan from centre."""
    n = len(radii)
    h = height / 2
    verts = []
    for y in (-h, h):
        for i, r in enumerate(radii):
            a = 2 * math.pi * i / n
            verts.append([r * math.cos(a), y, r * math.sin(a)])
    cb, ct = 2 * n, 2 * n + 1
    verts += [[0.0, -h, 0.0], [0.0, h, 0.0]]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces += [[i, n + i, j], [j, n + i, n + j], [ct, n + j, n + i], [cb, i, j]]
    return {'vertices': verts, 'faces': faces}


def _cylinder_mesh(radius, height, segments):
    return _prism_mesh([radius] * segments, height)


def _gear_mesh(teeth, outer_radius, root_radius, thickness):
    radii = []
    for _ in range(teeth):
        radii += [root_radius, outer_radius, outer_radius, root_radius]
    return _prism_mesh(radii, thickness)


def _uv_sphere(radius, segments, rings):
    verts = [[0.0, radius, 0.0]]
    for r in range(1, rings):
        phi = math.pi * r / rings
        for s in range(segments):
            th = 2 * math.pi * s / segments
            verts.append([radius * math.sin(phi) * math.cos(th), radius * math.cos(phi),
                          radius * math.sin(phi) * math.sin(th)])
    verts.append([0.0, -radius, 0.0])
    bottom = len(verts) - 1
    faces = []

    def ring(r, s):
        return 1 + (r - 1) * segments + (s % segments)
    for s in range(segments):
        faces.append([0, ring(1, s + 1), ring(1, s)])
        faces.append([bottom, ring(rings - 1, s), ring(rings - 1, s + 1)])
    for r in range(1, rings - 1):
        for s in range(segments):
            a, b = ring(r, s), ring(r, s + 1)
            c, d = ring(r + 1, s), ring(r + 1, s + 1)
            faces += [[a, b, d], [a, d, c]]
    return {'vertices': verts, 'faces': faces}


_SHAPE_KEYS = {
    'box': {'size'},
    'cylinder': {'radius', 'height', 'segments'},
    'gear': {'teeth', 'outer_radius', 'root_radius', 'thickness'},
    'mesh': {'mesh'},
}
_ALL_SHAPE_KEYS = set().union(*_SHAPE_KEYS.values())


def _build_part(spec, label, extra_keys=()):
    allowed = {'name', 'shape', 'position', 'rotation_deg'} | _ALL_SHAPE_KEYS | set(extra_keys)
    d = _obj(spec, allowed, {'name'}, label)
    name = _name(d['name'], f'{label}.name')
    shape = _choice(d.get('shape', 'mesh' if 'mesh' in d else 'box'), set(_SHAPE_KEYS),
                    f'{label}.shape')
    stray = (set(d) & _ALL_SHAPE_KEYS) - _SHAPE_KEYS[shape]
    if stray:
        raise ValueError(f'{label}: key(s) {sorted(stray)} do not apply to shape {shape!r}')
    if shape == 'box':
        size = _vec(d.get('size', [1.0, 1.0, 1.0]), 3, f'{label}.size', 1e-6, 1e3)
        mesh = _box_mesh(size)
    elif shape == 'cylinder':
        radius = _num(d.get('radius', 0.5), 1e-6, 1e3, f'{label}.radius')
        height = _num(d.get('height', 1.0), 1e-6, 1e3, f'{label}.height')
        segments = _int(d.get('segments', 24), 3, 256, f'{label}.segments')
        mesh = _cylinder_mesh(radius, height, segments)
    elif shape == 'gear':
        teeth = _int(d.get('teeth', 12), 3, 200, f'{label}.teeth')
        outer = _num(d.get('outer_radius', 0.5), 1e-6, 1e3, f'{label}.outer_radius')
        root = _num(d.get('root_radius', 0.4), 1e-6, 1e3, f'{label}.root_radius')
        if root >= outer:
            raise ValueError(f'{label}.root_radius must be smaller than outer_radius')
        thickness = _num(d.get('thickness', 0.2), 1e-6, 1e3, f'{label}.thickness')
        mesh = _gear_mesh(teeth, outer, root, thickness)
    else:
        if 'mesh' not in d:
            raise ValueError(f'{label}.mesh is required for shape "mesh"')
        mesh = _mesh(d['mesh'], f'{label}.mesh')
    position = _vec(d.get('position', [0.0, 0.0, 0.0]), 3, f'{label}.position')
    rotation = _vec(d.get('rotation_deg', [0.0, 0.0, 0.0]), 3, f'{label}.rotation_deg', -720, 720)
    rot = _rot3(rotation)
    world = [_add(_m3v(rot, v), position) for v in mesh['vertices']]
    llo, lhi = _bbox(mesh['vertices'])
    lc = [(llo[k] + lhi[k]) / 2 for k in range(3)]
    obb = {'center': _add(_m3v(rot, lc), position),
           'axes': [[rot[0][k], rot[1][k], rot[2][k]] for k in range(3)],
           'half': [(lhi[k] - llo[k]) / 2 for k in range(3)]}
    return {'name': name, 'shape': shape, 'local': mesh, 'world': world,
            'faces': mesh['faces'], 'position': position, 'rotation_deg': rotation,
            'obb': obb, 'aabb': _bbox(world), 'spec': d}


def _build_parts(parts, label, extra_keys=()):
    parts = _list(parts, label, 1, 64)
    built, names, total = [], set(), 0
    for i, spec in enumerate(parts):
        p = _build_part(spec, f'{label}[{i}]', extra_keys)
        if p['name'] in names:
            raise ValueError(f'duplicate part name {p["name"]!r}')
        names.add(p['name'])
        total += len(p['world'])
        if total > MAX_VERTICES:
            raise ValueError(f'parts exceed {MAX_VERTICES} vertices in total')
        built.append(p)
    return built


def _obb_sat(a, b):
    """Separating-axis test for two oriented boxes. Returns the minimum overlap over the
    15 candidate axes: > 0 penetration depth, <= 0 separated by that gap."""
    d = _sub(b['center'], a['center'])
    axes = list(a['axes']) + list(b['axes']) + [_cross(x, y) for x in a['axes'] for y in b['axes']]
    best = math.inf
    for axis in axes:
        n = _length(axis)
        if n < 1e-9:
            continue
        axis = [c / n for c in axis]
        ra = sum(e * abs(_dot(ax, axis)) for e, ax in zip(a['half'], a['axes']))
        rb = sum(e * abs(_dot(ax, axis)) for e, ax in zip(b['half'], b['axes']))
        best = min(best, ra + rb - abs(_dot(d, axis)))
    return best


# --------------------------------------------------------------------------- 18.01 machine_mesh

def _default_machine():
    parts = [
        {'name': 'base', 'shape': 'box', 'size': [0.6, 0.1, 0.4], 'position': [0.0, 0.05, 0.0]},
        {'name': 'column', 'shape': 'box', 'size': [0.1, 0.4, 0.1], 'position': [0.0, 0.3, 0.0]},
        {'name': 'shaft', 'shape': 'cylinder', 'radius': 0.02, 'height': 0.3, 'segments': 24,
         'position': [0.2, 0.4, 0.0], 'rotation_deg': [0.0, 0.0, 90.0]},
        {'name': 'gear', 'shape': 'gear', 'teeth': 12, 'outer_radius': 0.08, 'root_radius': 0.065,
         'thickness': 0.03, 'position': [0.3, 0.4, 0.0], 'rotation_deg': [0.0, 0.0, 90.0]},
    ]
    joints = [
        {'name': 'base_column', 'type': 'fixed', 'parent': 'base', 'child': 'column',
         'origin': [0.0, 0.1, 0.0]},
        {'name': 'column_shaft', 'type': 'revolute', 'parent': 'column', 'child': 'shaft',
         'axis': [1.0, 0.0, 0.0], 'origin': [0.05, 0.4, 0.0], 'limits': [-360.0, 360.0]},
        {'name': 'shaft_gear', 'type': 'fixed', 'parent': 'shaft', 'child': 'gear',
         'origin': [0.3, 0.4, 0.0]},
    ]
    return parts, joints


def machine_mesh(*, parts=None, joints=None, tolerance=1e-6, include_meshes=False, **extra):
    """Build box / cylinder / gear-prism parts with declared dimensions and joints, then check
    every pair for interference: world AABB first, then the separating-axis test (SAT) on the
    parts' oriented bounding boxes. For box parts the OBB *is* the part, so SAT is exact; for
    cylinders and gears the OBB is a conservative hull (may report contact a true cylinder
    would not). Status per pair: 'clear' (gap > tolerance), 'touching' (|overlap| <= tolerance)
    or 'interfering' (penetration depth > tolerance). Joints: fixed / revolute / prismatic with
    parent, child, axis, origin and optional limits; each child may have one parent joint and
    the joint graph must be acyclic.
    """
    _no_extra(extra)
    tolerance = _num(tolerance, 0, 1, 'tolerance')
    include_meshes = _bool(include_meshes, 'include_meshes')
    if parts is None:
        parts, default_joints = _default_machine()
        if joints is None:
            joints = default_joints
    elif joints is None:
        joints = []
    built = _build_parts(parts, 'parts')
    names = {p['name']: i for i, p in enumerate(built)}

    joints = _list(joints, 'joints', 0, 128)
    jout, jnames, parent_of = [], set(), {}
    for i, j in enumerate(joints):
        label = f'joints[{i}]'
        d = _obj(j, {'name', 'type', 'parent', 'child', 'axis', 'origin', 'limits'},
                 {'name', 'type', 'parent', 'child'}, label)
        jname = _name(d['name'], f'{label}.name')
        if jname in jnames:
            raise ValueError(f'duplicate joint name {jname!r}')
        jnames.add(jname)
        jtype = _choice(d['type'], {'fixed', 'revolute', 'prismatic'}, f'{label}.type')
        parent, child = d['parent'], d['child']
        if parent not in names or child not in names:
            raise ValueError(f'{label}: parent and child must name existing parts')
        if parent == child:
            raise ValueError(f'{label}: parent and child must differ')
        if child in parent_of:
            raise ValueError(f'{label}: part {child!r} already has a parent joint')
        parent_of[child] = parent
        if jtype != 'fixed' and 'axis' not in d:
            raise ValueError(f'{label}.axis is required for {jtype} joints')
        axis = _unit(d['axis'], f'{label}.axis') if 'axis' in d else None
        origin = _vec(d.get('origin', built[names[child]]['position']), 3, f'{label}.origin')
        limits = None
        if 'limits' in d:
            span = 360.0 if jtype == 'revolute' else COORD_LIMIT
            limits = _vec(d['limits'], 2, f'{label}.limits', -span, span)
            if limits[0] > limits[1]:
                raise ValueError(f'{label}.limits must be [low, high] with low <= high')
            if jtype == 'fixed':
                raise ValueError(f'{label}: fixed joints take no limits')
        jout.append({'name': jname, 'type': jtype, 'parent': parent, 'child': child,
                     'axis': axis, 'origin': origin, 'limits': limits,
                     'dof': 0 if jtype == 'fixed' else 1})
    for start in parent_of:
        seen, node = set(), start
        while node in parent_of:
            if node in seen:
                raise ValueError('joint graph contains a cycle')
            seen.add(node)
            node = parent_of[node]
    joint_pairs = {frozenset((j['parent'], j['child'])) for j in jout}

    pairs, interferences, touching = [], [], []
    for i in range(len(built)):
        for k in range(i + 1, len(built)):
            a, b = built[i], built[k]
            gap = _aabb_gap(a['aabb'], b['aabb'])
            if gap > tolerance:
                status, depth, method = 'clear', -gap, 'aabb'
            else:
                depth = _obb_sat(a['obb'], b['obb'])
                method = 'sat_obb'
                status = ('interfering' if depth > tolerance else
                          'touching' if depth >= -tolerance else 'clear')
            row = {'a': a['name'], 'b': b['name'], 'status': status, 'method': method,
                   'overlap_depth': depth,
                   'joint_pair': frozenset((a['name'], b['name'])) in joint_pairs,
                   'exact_for_shapes': a['shape'] == 'box' and b['shape'] == 'box'}
            pairs.append(row)
            if status == 'interfering':
                interferences.append(row)
            elif status == 'touching':
                touching.append(row)
    part_rows = []
    for p in built:
        row = {'name': p['name'], 'shape': p['shape'], 'vertex_count': len(p['world']),
               'face_count': len(p['faces']), 'volume': _volume(p['local']['vertices'], p['faces']),
               'position': p['position'], 'rotation_deg': p['rotation_deg'],
               'aabb': {'min': p['aabb'][0], 'max': p['aabb'][1]},
               'obb': {'center': p['obb']['center'], 'half_extents': p['obb']['half']}}
        if include_meshes:
            row['mesh'] = {'vertices': [v[:] for v in p['world']], 'faces': [f[:] for f in p['faces']]}
        part_rows.append(row)
    result = {
        'parts': part_rows, 'joints': jout,
        'roots': [p['name'] for p in built if p['name'] not in parent_of],
        'degrees_of_freedom': sum(j['dof'] for j in jout),
        'pairs': pairs, 'interferences': interferences, 'touching': touching,
        'interference_free': not interferences, 'tolerance': tolerance,
    }
    return _pack('machine_mesh', result,
                 ['parts are rigid closed triangle meshes centred on their local origin; '
                  'rotation is Euler XYZ in degrees (R = Rz Ry Rx)',
                  'interference = AABB broad phase then 15-axis SAT on oriented bounding boxes; '
                  'exact for boxes, conservative (hull) for cylinders and gears',
                  'gear is a straight-tooth prism outline, not an involute profile; bores are not modelled',
                  'joints are declared metadata (no motion solve); the default gear/shaft press-fit is '
                  'deliberately reported as interfering with joint_pair = true',
                  NO_GPU],
                 ['<= 64 parts, <= 128 joints, <= 50000 vertices in total',
                  'segments <= 256, teeth <= 200, coordinates within +-1e4 m'])


# --------------------------------------------------------------------------- 18.02 car_rig

def car_rig(*, wheelbase=2.7, track=1.6, steering_deg=20.0, wheel_radius=0.33, distance=10.0,
            speed=5.0, samples=11, **extra):
    """Kinematic bicycle model + Ackermann geometry for a car rig.

    The bicycle (centre-line) front wheel angle delta gives the rear-axle-centre turning
    radius R = L / tan(delta). Ackermann wheel angles: inner = atan(L / (R - T/2)),
    outer = atan(L / (R + T/2)), so inner > |delta| > outer. Each wheel's path radius gives
    the distance it rolls while the rear-axle centre travels `distance`, and its spin
    = rolled distance / wheel_radius. Positive steering turns left (+y); the car starts at
    the origin heading +x. steering_deg = 0 drives straight (R reported as null).
    """
    _no_extra(extra)
    L = _num(wheelbase, 0.2, 20, 'wheelbase')
    T = _num(track, 0.2, 5, 'track')
    delta_deg = _num(steering_deg, -60, 60, 'steering_deg')
    r_w = _num(wheel_radius, 0.01, 3, 'wheel_radius')
    distance = _num(distance, 0, 1e5, 'distance')
    speed = _num(speed, 0, 200, 'speed')
    samples = _int(samples, 2, 1001, 'samples')
    sign = 1.0 if delta_deg >= 0 else -1.0
    delta = math.radians(abs(delta_deg))
    straight = delta < 1e-9
    if straight:
        R = None
        wheels = {k: {'path_radius': None, 'distance': distance} for k in
                  ('rear_inner', 'rear_outer', 'front_inner', 'front_outer')}
        inner_deg = outer_deg = 0.0
        yaw_rate = 0.0
    else:
        R = L / math.tan(delta)
        if R <= T / 2 + 1e-9:
            raise ValueError('steering too tight: turning radius must exceed half the track')
        inner = math.atan(L / (R - T / 2))
        outer = math.atan(L / (R + T / 2))
        inner_deg, outer_deg = math.degrees(inner), math.degrees(outer)
        radii = {'rear_inner': R - T / 2, 'rear_outer': R + T / 2,
                 'front_inner': math.hypot(L, R - T / 2), 'front_outer': math.hypot(L, R + T / 2)}
        wheels = {k: {'path_radius': v, 'distance': distance * v / R} for k, v in radii.items()}
        yaw_rate = speed / R * sign
    for w in wheels.values():
        w['spin_deg'] = math.degrees(w['distance'] / r_w)
        w['revolutions'] = w['distance'] / (2 * math.pi * r_w)
    side = 'left' if sign > 0 else 'right'
    steer = {'front_inner_deg': inner_deg * sign, 'front_outer_deg': outer_deg * sign,
             'inner_side': None if straight else side}
    poses = []
    for i in range(samples):
        s = distance * i / (samples - 1)
        if straight:
            x, y, psi = s, 0.0, 0.0
        else:
            a = s / R
            x, y, psi = R * math.sin(a), sign * R * (1 - math.cos(a)), sign * a
        poses.append({'s': s, 't': s / speed if speed > 0 else None, 'x': x, 'y': y,
                      'heading_deg': math.degrees(psi),
                      'wheel_spin_deg': {k: w['spin_deg'] * i / (samples - 1) for k, w in wheels.items()}})
    result = {
        'wheelbase': L, 'track': T, 'bicycle_steering_deg': delta_deg,
        'turning_radius_rear_axle': R,
        'turning_radius_formula': 'R = L / tan(delta)',
        'turning_circle_diameter_outer_front': None if straight else 2 * math.hypot(L, R + T / 2),
        'ackermann': steer, 'inner_gt_outer': straight or inner_deg > outer_deg,
        'wheel_rotation_per_metre_deg': math.degrees(1.0 / r_w),
        'wheels': wheels, 'yaw_rate_deg_s': math.degrees(yaw_rate), 'speed': speed,
        'lateral_accel': 0.0 if straight else speed * speed / R,
        'poses': poses,
    }
    return _pack('car_rig', result,
                 ['kinematic bicycle model at low speed: no tyre slip, no slip angles, no suspension',
                  'ideal Ackermann linkage; turning centre on the rear-axle line',
                  'wheels roll without slipping: spin = distance / wheel_radius',
                  NO_GPU],
                 ['|steering| <= 60 deg, wheelbase 0.2-20 m, track 0.2-5 m',
                  'turning radius must exceed half the track', 'samples <= 1001'])


# --------------------------------------------------------------------------- 18.03 cloth3d

CLOTH_WORK_BUDGET = 3_000_000


def cloth3d(*, cols=10, rows=10, spacing=0.1, density=0.2, k_struct=300.0, k_shear=150.0,
            k_bend=30.0, damping=0.002, gravity=9.81, wind=(0.0, 0.0, 0.0), frames=60, fps=60.0,
            substeps=16, pin='corners', start='vertical', **extra):
    """3D mass-spring cloth (structural + shear + bend springs) with position Verlet.

    Particle mass = density * area / particle count. Each substep: spring forces
    k (|d| - rest) d/|d|, gravity (-y) and a uniform wind acceleration, then
    x_new = x + (x - x_prev)(1 - damping) + a dt^2. Pinned particles (the two top corners or
    the whole top row) never move. The substep dt must be <= 0.9 * dt_crit, with
    dt_crit = 2 sqrt(m / k_sum_max) (explicit stability bound), otherwise ValueError.
    Stability report: max structural stretch over all frames, finiteness, and mechanical
    energy (kinetic + spring + gravity) which must not grow beyond 5 % of m g h.
    """
    _no_extra(extra)
    cols = _int(cols, 2, 30, 'cols')
    rows = _int(rows, 2, 30, 'rows')
    spacing = _num(spacing, 1e-3, 10, 'spacing')
    density = _num(density, 1e-3, 100, 'density')
    k_struct = _num(k_struct, 0, 1e6, 'k_struct', low_open=True)
    k_shear = _num(k_shear, 0, 1e6, 'k_shear')
    k_bend = _num(k_bend, 0, 1e6, 'k_bend')
    damping = _num(damping, 0, 0.5, 'damping')
    gravity = _num(gravity, 0, 100, 'gravity')
    wind = _vec(wind, 3, 'wind', -100, 100)
    frames = _int(frames, 1, 600, 'frames')
    fps = _num(fps, 1, 240, 'fps')
    substeps = _int(substeps, 1, 200, 'substeps')
    pin = _choice(pin, {'corners', 'top_row'}, 'pin')
    start = _choice(start, {'vertical', 'horizontal'}, 'start')

    n = rows * cols

    def idx(r, c):
        return r * cols + c
    px, py, pz = [], [], []
    for r in range(rows):
        for c in range(cols):
            px.append(c * spacing)
            if start == 'vertical':
                py.append(-r * spacing)
                pz.append(0.0)
            else:
                py.append(0.0)
                pz.append(r * spacing)
    qx, qy, qz = px[:], py[:], pz[:]
    pinned = [idx(0, 0), idx(0, cols - 1)] if pin == 'corners' else [idx(0, c) for c in range(cols)]
    pinned_set = set(pinned)
    free = [i for i in range(n) if i not in pinned_set]
    springs, structural = [], []
    diag = spacing * math.sqrt(2)
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                structural.append((idx(r, c), idx(r, c + 1), spacing, k_struct))
            if r + 1 < rows:
                structural.append((idx(r, c), idx(r + 1, c), spacing, k_struct))
    springs += structural
    shear = []
    if k_shear > 0:
        for r in range(rows - 1):
            for c in range(cols - 1):
                shear.append((idx(r, c), idx(r + 1, c + 1), diag, k_shear))
                shear.append((idx(r, c + 1), idx(r + 1, c), diag, k_shear))
    bend = []
    if k_bend > 0:
        for r in range(rows):
            for c in range(cols):
                if c + 2 < cols:
                    bend.append((idx(r, c), idx(r, c + 2), 2 * spacing, k_bend))
                if r + 2 < rows:
                    bend.append((idx(r, c), idx(r + 2, c), 2 * spacing, k_bend))
    springs = structural + shear + bend
    work = frames * substeps * (len(springs) + n)
    if work > CLOTH_WORK_BUDGET:
        raise ValueError(f'cloth work {work} exceeds budget {CLOTH_WORK_BUDGET}; '
                         'reduce grid, frames or substeps')
    area = (cols - 1) * (rows - 1) * spacing * spacing
    m = density * area / n
    k_sum = [0.0] * n
    for a, b, _, k in springs:
        k_sum[a] += k
        k_sum[b] += k
    dt_crit = 2 * math.sqrt(m / max(k_sum))
    dt = 1.0 / (fps * substeps)
    if dt > 0.9 * dt_crit:
        raise ValueError(f'substep dt {dt:.3g} s exceeds 0.9 x stability limit {dt_crit:.3g} s; '
                         'raise substeps or lower stiffness')
    dt2 = dt * dt
    keep = 1.0 - damping
    ax_w, ay_w, az_w = wind[0], wind[1] - gravity, wind[2]
    pinned_start = [(px[i], py[i], pz[i]) for i in pinned]
    total_mass = m * n

    def energy():
        ke = 0.0
        for i in range(n):
            vx, vy, vz = (px[i] - qx[i]) / dt, (py[i] - qy[i]) / dt, (pz[i] - qz[i]) / dt
            ke += 0.5 * m * (vx * vx + vy * vy + vz * vz)
        pe = sum(m * gravity * y for y in py)
        for a, b, rest, k in springs:
            ln = math.sqrt((px[b] - px[a]) ** 2 + (py[b] - py[a]) ** 2 + (pz[b] - pz[a]) ** 2)
            pe += 0.5 * k * (ln - rest) ** 2
        return ke + pe

    def stretch():
        hi, lo = 0.0, math.inf
        for a, b, rest, _ in structural:
            ratio = math.sqrt((px[b] - px[a]) ** 2 + (py[b] - py[a]) ** 2
                              + (pz[b] - pz[a]) ** 2) / rest
            hi, lo = max(hi, ratio), min(lo, ratio)
        return hi, lo

    e0 = energy()
    energies = [e0]
    worst_hi, worst_lo = 1.0, 1.0
    for _ in range(frames):
        for _ in range(substeps):
            fx = [0.0] * n
            fy = [0.0] * n
            fz = [0.0] * n
            for a, b, rest, k in springs:
                dx, dy, dz = px[b] - px[a], py[b] - py[a], pz[b] - pz[a]
                ln = math.sqrt(dx * dx + dy * dy + dz * dz)
                if ln < 1e-12:
                    continue
                s = k * (ln - rest) / ln
                fx[a] += s * dx
                fy[a] += s * dy
                fz[a] += s * dz
                fx[b] -= s * dx
                fy[b] -= s * dy
                fz[b] -= s * dz
            for i in free:
                nx = px[i] + (px[i] - qx[i]) * keep + (fx[i] / m + ax_w) * dt2
                ny = py[i] + (py[i] - qy[i]) * keep + (fy[i] / m + ay_w) * dt2
                nz = pz[i] + (pz[i] - qz[i]) * keep + (fz[i] / m + az_w) * dt2
                qx[i], qy[i], qz[i] = px[i], py[i], pz[i]
                px[i], py[i], pz[i] = nx, ny, nz
        hi, lo = stretch()
        worst_hi, worst_lo = max(worst_hi, hi), min(worst_lo, lo)
        energies.append(energy())
    finite = all(math.isfinite(v) for v in px + py + pz) and all(math.isfinite(e) for e in energies)
    if not finite:
        raise RuntimeError('cloth simulation produced non-finite values')
    extent = max(rows, cols) * spacing
    e_scale = total_mass * max(gravity, 1e-9) * extent
    wind_allowance = total_mass * _length(wind) * 2 * extent * math.sqrt(2)
    growth = max(energies) - e0
    result = {
        'cols': cols, 'rows': rows, 'particles': n, 'particle_mass': m, 'total_mass': total_mass,
        'springs': {'structural': len(structural), 'shear': len(shear), 'bend': len(bend)},
        'dt_substep': dt, 'dt_critical': dt_crit, 'dt_ratio': dt / dt_crit,
        'frames': frames, 'substeps': substeps,
        'positions': [[px[i], py[i], pz[i]] for i in range(n)],
        'pinned_indices': pinned,
        'pinned_fixed': all((px[i], py[i], pz[i]) == s for i, s in zip(pinned, pinned_start)),
        'max_stretch_ratio': worst_hi, 'min_stretch_ratio': worst_lo,
        'final_max_stretch_ratio': stretch()[0],
        'energy_initial': e0, 'energy_final': energies[-1], 'energy_max_growth': growth,
        'energy_scale_mgh': e_scale,
        'energy_bounded': growth <= 0.05 * e_scale + wind_allowance,
        'energy_samples': _decimate(energies, 61), 'finite': finite,
    }
    result['stable'] = result['finite'] and result['energy_bounded'] and worst_hi <= 1.5
    return _pack('cloth3d', result,
                 ['linear (Hookean) springs; structural, shear (diagonal) and bend (skip-one) springs',
                  'position Verlet with per-substep velocity damping; equal particle masses from density',
                  'stretch and energy are sampled once per frame, not every substep',
                  'wind is a uniform acceleration (no aerodynamic pressure); no self-collision, '
                  'no collision with bodies, no tearing',
                  NO_GPU],
                 ['grid <= 30 x 30, frames <= 600, substeps <= 200',
                  f'frames * substeps * (springs + particles) <= {CLOTH_WORK_BUDGET}',
                  'substep dt <= 0.9 x 2 sqrt(m / k_sum_max) or ValueError'])


# --------------------------------------------------------------------------- 18.04 camera3d

def camera3d(*, position=(0.0, 1.6, 5.0), target=(0.0, 1.0, 0.0), up=(0.0, 1.0, 0.0),
             focal_mm=50.0, sensor_width_mm=36.0, image_width=1920, image_height=1080,
             near=0.1, far=100.0, f_number=2.8, coc_mm=0.03, focus_distance=None, points=None,
             **extra):
    """Pinhole camera from position / target / up with a physical lens.

    FOV (horizontal sensor fit): hfov = 2 atan(sensor_width / (2 f)); vfov from the image
    aspect. View matrix = right-handed look-at (camera looks down -z); projection = OpenGL
    perspective (clip z in [-w, w]). Points are clip-tested: visible when w > 0 and
    |x|, |y|, |z| <= w. Depth of field: hyperfocal H = f^2 / (N c) + f; near limit
    s (H - f) / (H + s - 2f); far limit s (H - f) / (H - s) (infinite when s >= H).
    Matrices are row-major 4x4 lists.
    """
    _no_extra(extra)
    eye = _vec(position, 3, 'position')
    tgt = _vec(target, 3, 'target')
    up_v = _unit(up, 'up')
    f_mm = _num(focal_mm, 1, 2000, 'focal_mm')
    sw = _num(sensor_width_mm, 1, 100, 'sensor_width_mm')
    iw = _int(image_width, 1, 16384, 'image_width')
    ih = _int(image_height, 1, 16384, 'image_height')
    near = _num(near, 1e-4, 1e5, 'near')
    far = _num(far, 1e-3, 1e7, 'far')
    if far <= near:
        raise ValueError('far must be greater than near')
    n_stop = _num(f_number, 0.5, 64, 'f_number')
    coc = _num(coc_mm, 1e-4, 1, 'coc_mm')
    fwd = _sub(tgt, eye)
    dist_target = _length(fwd)
    if dist_target < 1e-9:
        raise ValueError('position and target must differ')
    fwd = _mul(fwd, 1 / dist_target)
    side = _cross(fwd, up_v)
    if _length(side) < 1e-6:
        raise ValueError('up must not be parallel to the view direction')
    side = _normalize(side)
    up_c = _cross(side, fwd)
    s_focus = dist_target if focus_distance is None else _num(focus_distance, 1e-3, 1e6,
                                                              'focus_distance')
    if points is None:
        points = [tgt, _add(eye, _mul(fwd, near * 0.5)), _add(eye, _mul(fwd, -1.0)),
                  _add(eye, _mul(fwd, far * 1.5)), _add(tgt, _mul(side, dist_target * 10))]
    points = _list(points, 'points', 0, MAX_POINTS)
    points = [_vec(p, 3, f'points[{i}]', -1e7, 1e7) for i, p in enumerate(points)]

    aspect = iw / ih
    hfov = 2 * math.atan(sw / (2 * f_mm))
    vfov = 2 * math.atan(math.tan(hfov / 2) / aspect)
    view = [side + [-_dot(side, eye)], up_c + [-_dot(up_c, eye)],
            _mul(fwd, -1) + [_dot(fwd, eye)], [0.0, 0.0, 0.0, 1.0]]
    fy = 1 / math.tan(vfov / 2)
    proj = [[fy / aspect, 0.0, 0.0, 0.0], [0.0, fy, 0.0, 0.0],
            [0.0, 0.0, (far + near) / (near - far), 2 * far * near / (near - far)],
            [0.0, 0.0, -1.0, 0.0]]
    view_proj = _m4mul(proj, view)
    eps = 1e-9
    rows_out = []
    for p in points:
        vp = _m4v4(view, p + [1.0])
        depth = -vp[2]
        clip = _m4v4(proj, vp)
        w = clip[3]
        inside = (w > 0 and all(abs(clip[k]) <= w * (1 + eps) for k in range(3)))
        if depth <= 0:
            reason = 'behind_camera'
        elif depth < near:
            reason = 'clipped_near'
        elif depth > far:
            reason = 'clipped_far'
        elif not inside:
            reason = 'outside_frustum'
        else:
            reason = 'visible'
        row = {'point': p, 'view_depth': depth, 'visible': reason == 'visible', 'reason': reason}
        if w > 0:
            ndc = [clip[k] / w for k in range(3)]
            row['ndc'] = ndc
            row['pixel'] = [(ndc[0] + 1) / 2 * iw, (1 - ndc[1]) / 2 * ih]
        rows_out.append(row)
    f_m = f_mm / 1000
    H = (f_mm * f_mm / (n_stop * coc) + f_mm) / 1000
    dof_near = s_focus * (H - f_m) / (H + s_focus - 2 * f_m)
    dof_far = s_focus * (H - f_m) / (H - s_focus) if s_focus < H else None
    result = {
        'hfov_deg': math.degrees(hfov), 'vfov_deg': math.degrees(vfov),
        'aspect': aspect, 'focal_mm': f_mm, 'sensor_width_mm': sw,
        'sensor_height_mm_implied': sw / aspect,
        'basis': {'right': side, 'up': up_c, 'forward': fwd},
        'view_matrix': view, 'projection_matrix': proj, 'view_projection_matrix': view_proj,
        'near': near, 'far': far,
        'depth_of_field': {'f_number': n_stop, 'coc_mm': coc, 'focus_distance': s_focus,
                           'hyperfocal_m': H, 'near_limit_m': dof_near, 'far_limit_m': dof_far,
                           'total_m': None if dof_far is None else dof_far - dof_near},
        'points': rows_out,
        'visible_count': sum(r['visible'] for r in rows_out),
    }
    return _pack('camera3d', result,
                 ['ideal thin-lens / pinhole camera, horizontal sensor fit, square pixels',
                  'right-handed look-at (camera looks down -z), OpenGL clip space z in [-w, w]',
                  'depth of field uses the classic hyperfocal approximation with a fixed circle of confusion',
                  'no lens distortion, no sensor shift, no motion blur',
                  NO_GPU],
                 [f'<= {MAX_POINTS} points', 'focal 1-2000 mm, sensor width 1-100 mm, f/0.5-f/64',
                  'far > near > 0'])


# --------------------------------------------------------------------------- 18.05 skinning

def _default_tube():
    verts, weights = [], []
    n = 21
    for i in range(n):
        x = 2.0 * i / (n - 1)
        t = min(1.0, max(0.0, (x - 0.8) / 0.4))
        w1 = t * t * (3 - 2 * t)
        for y, z in ((-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)):
            verts.append([x, y, z])
            weights.append([1.0 - w1, w1])
    faces = []
    for i in range(n - 1):
        for k in range(4):
            a, b = 4 * i + k, 4 * i + (k + 1) % 4
            c, d = a + 4, b + 4
            faces += [[a, b, d], [a, d, c]]
    bones = [{'name': 'upper', 'parent': None, 'head': [0.0, 0.0, 0.0]},
             {'name': 'lower', 'parent': 0, 'head': [1.0, 0.0, 0.0],
              'pose_rotation_deg': [0.0, 0.0, 90.0]}]
    return verts, faces, weights, bones


def _skin_matrices(bones, posed):
    world, skin = [], []
    for b in bones:
        head = b['head']
        if b['parent'] is None:
            offset = head
            parent_m = None
        else:
            offset = _sub(head, bones[b['parent']]['head'])
            parent_m = world[b['parent']]
        rot = _rot3(b['rot']) if posed else _rot3([0.0, 0.0, 0.0])
        trans = b['trans'] if posed else [0.0, 0.0, 0.0]
        local = _m4mul(_m4_translate(_add(offset, trans)), _m4_trs([0.0, 0.0, 0.0], rot, [1.0] * 3))
        m = local if parent_m is None else _m4mul(parent_m, local)
        world.append(m)
        skin.append(_m4mul(m, _m4_translate(_mul(head, -1.0))))
    return world, skin


def _lbs(verts, weights, skin):
    out = []
    for v, w in zip(verts, weights):
        acc = [0.0, 0.0, 0.0]
        for wi, s in zip(w, skin):
            if wi:
                p = _m4pt(s, v)
                acc = [acc[0] + wi * p[0], acc[1] + wi * p[1], acc[2] + wi * p[2]]
        out.append(acc)
    return out


def skinning(*, vertices=None, faces=None, weights=None, bones=None, weight_tolerance=1e-3,
             include_vertices=True, **extra):
    """Linear blend skinning: v' = sum_i w_i M_i B_i^-1 v.

    Bones: [{'name', 'parent' (None or an earlier index), 'head' [x,y,z],
    'pose_rotation_deg' [rx,ry,rz] (Euler XYZ about the head), 'pose_translation'}]; bind
    pose = identity orientation at `head`. Per-vertex weights must have one entry per bone,
    be >= 0, and sum to 1 within weight_tolerance (then they are renormalised exactly);
    otherwise ValueError. Reports rest-pose displacement (should be ~0) and skin distortion
    = max relative edge-length change of the posed mesh. With no inputs, a 2 m square tube
    with two bones bent 90 deg at x = 1 is used.
    """
    _no_extra(extra)
    weight_tolerance = _num(weight_tolerance, 0, 0.1, 'weight_tolerance')
    include_vertices = _bool(include_vertices, 'include_vertices')
    given = [x is not None for x in (vertices, faces, weights)]
    if not any(given):
        vertices, faces, weights, default_bones = _default_tube()
        if bones is None:
            bones = default_bones
    elif not all(given):
        raise ValueError('vertices, faces and weights must be given together')
    elif bones is None:
        raise ValueError('bones are required when a custom mesh is given')
    mesh = _mesh({'vertices': vertices, 'faces': faces}, 'mesh')
    verts, faces = mesh['vertices'], mesh['faces']
    bones = _list(bones, 'bones', 1, 64)
    bl = []
    for i, b in enumerate(bones):
        label = f'bones[{i}]'
        d = _obj(b, {'name', 'parent', 'head', 'pose_rotation_deg', 'pose_translation'},
                 {'name', 'head'}, label)
        parent = d.get('parent')
        if parent is not None:
            parent = _int(parent, 0, i - 1 if i else -1, f'{label}.parent') if i else None
            if parent is None:
                raise ValueError('the first bone must be a root (parent None)')
        bl.append({'name': _name(d['name'], f'{label}.name'), 'parent': parent,
                   'head': _vec(d['head'], 3, f'{label}.head'),
                   'rot': _vec(d.get('pose_rotation_deg', [0.0, 0.0, 0.0]), 3,
                               f'{label}.pose_rotation_deg', -720, 720),
                   'trans': _vec(d.get('pose_translation', [0.0, 0.0, 0.0]), 3,
                                 f'{label}.pose_translation')})
    if len({b['name'] for b in bl}) != len(bl):
        raise ValueError('bone names must be unique')
    weights = _list(weights, 'weights', len(verts), len(verts))
    norm_w, max_err = [], 0.0
    for i, w in enumerate(weights):
        w = _vec(w, len(bl), f'weights[{i}]', 0, 1 + weight_tolerance)
        s = sum(w)
        err = abs(s - 1.0)
        if err > weight_tolerance:
            raise ValueError(f'weights[{i}] sum to {s:.6g}; must be 1 within {weight_tolerance}')
        max_err = max(max_err, err)
        norm_w.append([x / s for x in w])
    _, rest_skin = _skin_matrices(bl, posed=False)
    rest = _lbs(verts, norm_w, rest_skin)
    rest_disp = max(_length(_sub(a, b)) for a, b in zip(rest, verts))
    world, skin = _skin_matrices(bl, posed=True)
    posed = _lbs(verts, norm_w, skin)
    worst, worst_edge, total, count = 0.0, None, 0.0, 0
    for a, b in _edges_of(faces):
        l0 = _length(_sub(verts[b], verts[a]))
        if l0 < 1e-12:
            continue
        rel = abs(_length(_sub(posed[b], posed[a])) - l0) / l0
        total += rel
        count += 1
        if rel > worst:
            worst, worst_edge = rel, [a, b]
    vol_rest = _volume(verts, faces)
    vol_posed = _volume(posed, faces)
    result = {
        'vertex_count': len(verts), 'bone_count': len(bl),
        'input_weight_sum_max_error': max_err,
        'normalised_weight_sum_max_error': max(abs(sum(w) - 1.0) for w in norm_w),
        'rest_max_displacement': rest_disp,
        'max_skin_distortion': worst, 'mean_skin_distortion': total / count if count else 0.0,
        'worst_edge': worst_edge,
        'volume_rest': vol_rest, 'volume_posed': vol_posed,
        'volume_change_ratio': (vol_posed / vol_rest) if abs(vol_rest) > 1e-12 else None,
        'bone_heads_posed': [[m[0][3], m[1][3], m[2][3]] for m in world],
    }
    if include_vertices and len(posed) <= 5000:
        result['posed_vertices'] = posed
    return _pack('skinning', result,
                 ['linear blend skinning (no dual-quaternion): volume loss / candy-wrapper at '
                  'strong bends is expected and is what max_skin_distortion measures',
                  'bind pose = identity bone orientation at each head; pose rotation is Euler XYZ about the head',
                  'weights within tolerance are renormalised to sum exactly to 1',
                  NO_GPU],
                 ['<= 64 bones, <= 50000 vertices', 'weight_tolerance <= 0.1',
                  'posed_vertices returned only when <= 5000 vertices'])


# --------------------------------------------------------------------------- 18.06 uv_atlas

_BOX_DIRS = {(0, 1): '+x', (0, -1): '-x', (1, 1): '+y', (1, -1): '-y', (2, 1): '+z', (2, -1): '-z'}


def _project(v, direction):
    x, y, z = v
    return {'+x': (-z, y), '-x': (z, y), '+y': (x, -z), '-y': (x, z),
            '+z': (x, y), '-z': (-x, y)}[direction]


def _tri_area2(t):
    (ax, ay), (bx, by), (cx, cy) = t
    return (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)


def _tri_overlap_2d(t1, t2, eps=1e-9):
    """True when the interiors of two 2D triangles overlap by more than eps (SAT)."""
    for tri in (t1, t2):
        for k in range(3):
            ax, ay = tri[k]
            bx, by = tri[(k + 1) % 3]
            nx, ny = by - ay, ax - bx
            ln = math.hypot(nx, ny)
            if ln < 1e-15:
                continue
            nx, ny = nx / ln, ny / ln
            p1 = [nx * x + ny * y for x, y in t1]
            p2 = [nx * x + ny * y for x, y in t2]
            if min(max(p1), max(p2)) - max(min(p1), min(p2)) <= eps:
                return False
    return True


def _shelf_pack(sizes, scale, pad):
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], i))
    x, y, shelf = pad, pad, 0.0
    places = [None] * len(sizes)
    for i in order:
        w, h = sizes[i][0] * scale, sizes[i][1] * scale
        if w + 2 * pad > 1 + 1e-12:
            return None
        if x + w + pad > 1 + 1e-12:
            y += shelf + pad
            x, shelf = pad, 0.0
        places[i] = (x, y)
        x += w + pad
        shelf = max(shelf, h)
    if y + shelf + pad > 1 + 1e-12:
        return None
    return places


def uv_atlas(*, mesh=None, projection='box', planar_axis='z', padding=0.02, include_uvs=False,
             **extra):
    """Planar or box UV projection, island detection, shelf-packed atlas with padding.

    Box: each face is projected along its dominant normal direction (6 directions);
    islands = edge-connected faces with the same direction. Planar: every face is projected
    along `planar_axis`; islands = edge-connected components. Seams = mesh edges whose
    faces fall in different islands. Islands keep their relative size (one uniform scale
    found by bisection) and are shelf-packed into [0,1]^2 with `padding` between islands and
    from the border. Overlap checks: packed island rectangles pairwise, and triangle-level
    folds inside each island (e.g. planar projection of front and back faces).
    """
    _no_extra(extra)
    if mesh is None:
        mesh = _box_mesh([1.0, 1.0, 1.0])
    mesh = _mesh(mesh, 'mesh')
    projection = _choice(projection, {'box', 'planar'}, 'projection')
    planar_axis = _choice(planar_axis, {'x', 'y', 'z'}, 'planar_axis')
    padding = _num(padding, 0, 0.2, 'padding')
    include_uvs = _bool(include_uvs, 'include_uvs')
    verts, faces = mesh['vertices'], mesh['faces']
    if len(faces) > 20_000:
        raise ValueError('uv_atlas accepts at most 20000 faces')
    dirs = []
    for f in faces:
        nrm = _cross(_sub(verts[f[1]], verts[f[0]]), _sub(verts[f[2]], verts[f[0]]))
        if projection == 'planar':
            dirs.append('+' + planar_axis)
        else:
            k = max(range(3), key=lambda j: (abs(nrm[j]), -j))
            dirs.append(_BOX_DIRS[(k, 1 if nrm[k] >= 0 else -1)])
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edge_faces = {}
    for fi, f in enumerate(faces):
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)
    for fl in edge_faces.values():
        for g in fl[1:]:
            if dirs[g] == dirs[fl[0]]:
                ra, rb = find(fl[0]), find(g)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    roots = sorted({find(i) for i in range(len(faces))})
    island_of_root = {r: i for i, r in enumerate(roots)}
    island = [island_of_root[find(i)] for i in range(len(faces))]
    seams = sorted(e for e, fl in edge_faces.items() if len({island[f] for f in fl}) > 1)
    proj = [[_project(verts[v], dirs[fi]) for v in f] for fi, f in enumerate(faces)]
    members = [[] for _ in roots]
    for fi, isl in enumerate(island):
        members[isl].append(fi)
    sizes, mins = [], []
    for mem in members:
        us = [p[0] for fi in mem for p in proj[fi]]
        vs = [p[1] for fi in mem for p in proj[fi]]
        mins.append((min(us), min(vs)))
        sizes.append((max(us) - min(us), max(vs) - min(vs)))
    biggest = max(max(w, h) for w, h in sizes)
    if biggest <= 0:
        raise ValueError('mesh projects to zero area')
    hi = (1 - 2 * padding) / biggest
    best, best_s = None, 0.0
    lo_s = 0.0
    for _ in range(60):
        mid = (lo_s + hi) / 2
        places = _shelf_pack(sizes, mid, padding)
        if places is None:
            hi = mid
        else:
            lo_s, best, best_s = mid, places, mid
    if best is None or best_s <= 0:
        raise ValueError('padding too large for the number of islands')
    rects = []
    for (x, y), (w, h) in zip(best, sizes):
        rects.append([x, y, x + w * best_s, y + h * best_s])
    uvs = []
    for fi in range(len(faces)):
        isl = island[fi]
        mu, mv = mins[isl]
        ox, oy = best[isl]
        uvs.append([[ox + (u - mu) * best_s, oy + (v - mv) * best_s] for u, v in proj[fi]])
    all_uv = [c for tri in uvs for p in tri for c in p]
    within = min(all_uv) >= -1e-12 and max(all_uv) <= 1 + 1e-12
    min_gap, rect_overlaps = math.inf, 0
    for i in range(len(rects)):
        for k in range(i + 1, len(rects)):
            a, b = rects[i], rects[k]
            gap = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
            min_gap = min(min_gap, gap)
            if gap < -1e-12:
                rect_overlaps += 1
    border = min(min(r[0], r[1], 1 - r[2], 1 - r[3]) for r in rects)
    pair_budget = 200_000
    folds, checked, skipped = 0, 0, False
    for mem in members:
        live = [fi for fi in mem if abs(_tri_area2(uvs[fi])) > 1e-14]
        npairs = len(live) * (len(live) - 1) // 2
        if checked + npairs > pair_budget:
            skipped = True
            continue
        checked += npairs
        boxes = {fi: (min(p[0] for p in uvs[fi]), min(p[1] for p in uvs[fi]),
                      max(p[0] for p in uvs[fi]), max(p[1] for p in uvs[fi])) for fi in live}
        for x in range(len(live)):
            for y in range(x + 1, len(live)):
                ba, bb = boxes[live[x]], boxes[live[y]]
                if ba[2] <= bb[0] or bb[2] <= ba[0] or ba[3] <= bb[1] or bb[3] <= ba[1]:
                    continue
                if _tri_overlap_2d(uvs[live[x]], uvs[live[y]]):
                    folds += 1
    tol = 1e-9
    result = {
        'projection': projection, 'island_count': len(members),
        'islands': [{'faces': len(mem), 'direction': dirs[mem[0]], 'rect': rects[i]}
                    for i, mem in enumerate(members)],
        'texel_scale': best_s, 'padding': padding,
        'within_unit_square': within,
        'min_gap_between_islands': None if len(rects) < 2 else min_gap,
        'min_border': border,
        'padding_respected': border >= padding - tol and (len(rects) < 2 or min_gap >= padding - tol),
        'island_rect_overlaps': rect_overlaps,
        'overlapping_face_pairs_within_islands': folds,
        'overlap_check_complete': not skipped,
        'seam_edges': seams, 'seam_count': len(seams),
        'uv_coverage': sum(abs(_tri_area2(t)) / 2 for t in uvs),
    }
    if include_uvs and len(faces) <= 5000:
        result['face_uvs'] = uvs
    return _pack('uv_atlas', result,
                 ['box projection picks each face\'s dominant normal axis; planar projects along one axis',
                  'islands keep relative world size (one uniform texel scale) and are packed on shelves '
                  'sorted by height; not an optimal packer and islands are not rotated',
                  'per-face-corner UVs; vertices on seams are split implicitly',
                  'fold detection is triangle-vs-triangle SAT inside each island',
                  NO_GPU],
                 ['<= 20000 faces, padding <= 0.2',
                  'triangle overlap checks capped at 200000 pairs (overlap_check_complete says if skipped)'])


# --------------------------------------------------------------------------- 18.07 area_lighting

def _default_lighting():
    lights = [{'center': [0.0, 2.0, 0.0], 'u': [0.25, 0.0, 0.0], 'v': [0.0, 0.0, 0.25],
               'radiance': [10.0, 10.0, 10.0]}]
    occluders = [{'min': [-0.3, 0.4, -0.3], 'max': [0.3, 0.5, 0.3]}]
    points = [{'name': 'under_occluder', 'position': [0.0, 0.0, 0.0], 'normal': [0.0, 1.0, 0.0]},
              {'name': 'open_floor', 'position': [1.5, 0.0, 0.0], 'normal': [0.0, 1.0, 0.0]}]
    hdri = {'license': 'CC0 example summary (synthetic)', 'source': 'built-in example',
            'buckets': [
                {'direction': [0, 1, 0], 'radiance': [0.30, 0.40, 0.60]},
                {'direction': [0, -1, 0], 'radiance': [0.05, 0.04, 0.03]},
                {'direction': [1, 0, 0], 'radiance': [0.20, 0.20, 0.25]},
                {'direction': [-1, 0, 0], 'radiance': [0.20, 0.20, 0.25]},
                {'direction': [0, 0, 1], 'radiance': [0.20, 0.20, 0.25]},
                {'direction': [0, 0, -1], 'radiance': [0.20, 0.20, 0.25]}]}
    return lights, occluders, points, hdri


def _segment_blocked(p, q, boxes):
    d = _sub(q, p)
    for lo, hi in boxes:
        t0, t1 = 1e-6, 1 - 1e-6
        hit = True
        for k in range(3):
            if abs(d[k]) < 1e-15:
                if p[k] < lo[k] or p[k] > hi[k]:
                    hit = False
                    break
            else:
                a, b = (lo[k] - p[k]) / d[k], (hi[k] - p[k]) / d[k]
                if a > b:
                    a, b = b, a
                t0, t1 = max(t0, a), min(t1, b)
                if t0 > t1:
                    hit = False
                    break
        if hit:
            return True
    return False


def _luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def area_lighting(*, lights=None, occluders=None, points=None, hdri_summary=None, samples=8,
                  env_distance=100.0, use_default_hdri=True, **extra):
    """Irradiance from rectangular area lights (fixed midpoint grid, samples x samples) plus an
    environment term from a licensed HDRI *summary* (average radiance per direction bucket).

    Light: {'center', 'u', 'v' (half-edge vectors), 'radiance' [r,g,b] W/(m^2 sr)}; one-sided,
    emitting along normalize(u x v). E = sum L cos(theta_p) cos(theta_l) / r^2 dA * visibility.
    Environment: each of N buckets covers 4 pi / N sr: E += L_b max(0, n.d_b) 4 pi / N * vis.
    Occluders are axis-aligned boxes {'min', 'max'}; shadow rays are segment/slab tests.
    hdri_summary must be a dict with a non-empty 'license' string and 'buckets'; image files
    and paths are not accepted.
    """
    _no_extra(extra)
    samples = _int(samples, 1, 32, 'samples')
    env_distance = _num(env_distance, 1e-3, 1e6, 'env_distance')
    use_default_hdri = _bool(use_default_hdri, 'use_default_hdri')
    d_lights, d_occ, d_points, d_hdri = _default_lighting()
    lights = d_lights if lights is None else lights
    occluders = d_occ if occluders is None else occluders
    points = d_points if points is None else points
    if hdri_summary is None and use_default_hdri:
        hdri_summary = d_hdri
    lights = _list(lights, 'lights', 0, 8)
    ls = []
    for i, li in enumerate(lights):
        d = _obj(li, {'center', 'u', 'v', 'radiance'}, {'center', 'u', 'v', 'radiance'}, f'lights[{i}]')
        u = _vec(d['u'], 3, f'lights[{i}].u')
        v = _vec(d['v'], 3, f'lights[{i}].v')
        nrm = _cross(u, v)
        if _length(nrm) < 1e-12:
            raise ValueError(f'lights[{i}]: u and v must span an area')
        ls.append({'c': _vec(d['center'], 3, f'lights[{i}].center'), 'u': u, 'v': v,
                   'n': _normalize(nrm), 'area': 4 * _length(nrm),
                   'L': _vec(d['radiance'], 3, f'lights[{i}].radiance', 0, 1e6)})
    occluders = _list(occluders, 'occluders', 0, 32)
    boxes = []
    for i, o in enumerate(occluders):
        d = _obj(o, {'min', 'max'}, {'min', 'max'}, f'occluders[{i}]')
        lo, hi = _vec(d['min'], 3, f'occluders[{i}].min'), _vec(d['max'], 3, f'occluders[{i}].max')
        if any(lo[k] > hi[k] for k in range(3)):
            raise ValueError(f'occluders[{i}]: min must be <= max')
        boxes.append((lo, hi))
    points = _list(points, 'points', 1, 200)
    pts = []
    for i, p in enumerate(points):
        d = _obj(p, {'name', 'position', 'normal'}, {'position', 'normal'}, f'points[{i}]')
        pts.append({'name': _name(d.get('name', f'p{i}'), f'points[{i}].name'),
                    'p': _vec(d['position'], 3, f'points[{i}].position'),
                    'n': _unit(d['normal'], f'points[{i}].normal')})
    env = None
    if hdri_summary is not None:
        d = _obj(hdri_summary, {'license', 'source', 'buckets'}, {'license', 'buckets'},
                 'hdri_summary')
        if not isinstance(d['license'], str) or not d['license'].strip() or len(d['license']) > 200:
            raise ValueError('hdri_summary.license must be a non-empty string (<= 200 chars)')
        if 'source' in d and (not isinstance(d['source'], str) or len(d['source']) > 200):
            raise ValueError('hdri_summary.source must be a string (<= 200 chars)')
        buckets = _list(d['buckets'], 'hdri_summary.buckets', 1, 256)
        env = []
        for i, b in enumerate(buckets):
            bd = _obj(b, {'direction', 'radiance'}, {'direction', 'radiance'},
                      f'hdri_summary.buckets[{i}]')
            env.append((_unit(bd['direction'], f'hdri_summary.buckets[{i}].direction'),
                        _vec(bd['radiance'], 3, f'hdri_summary.buckets[{i}].radiance', 0, 1e6)))
        env_license = d['license']
    work = len(pts) * (len(ls) * samples * samples + (len(env) if env else 0)) * (len(boxes) + 1)
    if work > 3_000_000:
        raise ValueError('lighting work exceeds 3000000 ray-box tests; reduce samples or points')
    rows = []
    for pt in pts:
        p, n = pt['p'], pt['n']
        origin = _add(p, _mul(n, 1e-6))
        direct = [0.0, 0.0, 0.0]
        unshadowed = 0.0
        for L in ls:
            dA = L['area'] / (samples * samples)
            for i in range(samples):
                for j in range(samples):
                    a = 2 * (i + 0.5) / samples - 1
                    b = 2 * (j + 0.5) / samples - 1
                    q = _add(L['c'], _add(_mul(L['u'], a), _mul(L['v'], b)))
                    w = _sub(q, p)
                    r2 = _dot(w, w)
                    if r2 < 1e-12:
                        continue
                    r = math.sqrt(r2)
                    cos_p = _dot(n, w) / r
                    cos_l = -_dot(L['n'], w) / r
                    if cos_p <= 0 or cos_l <= 0:
                        continue
                    g = cos_p * cos_l / r2 * dA
                    lum = _luma(L['L']) * g
                    unshadowed += lum
                    if boxes and _segment_blocked(origin, q, boxes):
                        continue
                    direct = [direct[k] + L['L'][k] * g for k in range(3)]
        env_e = [0.0, 0.0, 0.0]
        if env:
            omega = 4 * math.pi / len(env)
            for dvec, rad in env:
                c = _dot(n, dvec)
                if c <= 0:
                    continue
                if boxes and _segment_blocked(origin, _add(p, _mul(dvec, env_distance)), boxes):
                    continue
                env_e = [env_e[k] + rad[k] * c * omega for k in range(3)]
        total = [direct[k] + env_e[k] for k in range(3)]
        shadow_fraction = (1 - _luma(direct) / unshadowed) if unshadowed > 0 else None
        rows.append({'name': pt['name'], 'position': p, 'normal': n,
                     'direct_irradiance': direct, 'environment_irradiance': env_e,
                     'irradiance': total, 'luminance': _luma(total),
                     'direct_unoccluded_luminance': unshadowed,
                     'shadow_fraction': shadow_fraction,
                     'region': 'shadowed' if shadow_fraction is not None and shadow_fraction >= 0.5
                     else 'lit'})
    lit = [r['luminance'] for r in rows if r['region'] == 'lit']
    shad = [r['luminance'] for r in rows if r['region'] == 'shadowed']
    lit_mean = sum(lit) / len(lit) if lit else None
    shad_mean = sum(shad) / len(shad) if shad else None
    result = {
        'points': rows, 'samples_per_light': samples * samples,
        'light_areas': [L['area'] for L in ls],
        'environment': None if env is None else {'buckets': len(env), 'license': env_license,
                                                 'solid_angle_per_bucket': 4 * math.pi / len(env)},
        'comparison': {'lit_count': len(lit), 'shadowed_count': len(shad),
                       'lit_mean_luminance': lit_mean, 'shadowed_mean_luminance': shad_mean,
                       'lit_to_shadow_ratio': (lit_mean / shad_mean) if lit_mean is not None
                       and shad_mean else None},
    }
    return _pack('area_lighting', result,
                 ['Lambertian receivers; one-sided rectangular emitters with uniform radiance',
                  'direct term integrated with a fixed midpoint grid (deterministic, no noise, '
                  'some bias for lights close to the receiver)',
                  'environment = per-bucket average radiance over equal solid angles; it is a coarse '
                  'summary of a licensed HDRI supplied by the caller, not an image lookup',
                  'occluders are axis-aligned boxes casting hard binary shadows per sample; no interreflection',
                  NO_GPU],
                 ['<= 8 lights, samples <= 32 per side, <= 32 occluders, <= 200 points, <= 256 buckets',
                  'points * (lights * samples^2 + buckets) * (occluders + 1) <= 3000000'])


# --------------------------------------------------------------------------- 18.08 export_mesh

def _default_scene():
    box = _box_mesh([0.6, 0.1, 0.4])
    cyl = _cylinder_mesh(0.02, 0.3, 16)
    gear = _gear_mesh(12, 0.08, 0.065, 0.03)
    meshes = {'base_box': dict(box, material='steel'), 'shaft_cyl': dict(cyl, material='steel'),
              'gear12': dict(gear, material='brass')}
    materials = {'steel': {'base_color': [0.62, 0.64, 0.66, 1.0], 'metallic': 1.0, 'roughness': 0.35},
                 'brass': {'base_color': [0.78, 0.6, 0.25, 1.0], 'metallic': 1.0, 'roughness': 0.3}}
    nodes = [
        {'name': 'machine'},
        {'name': 'base', 'parent': 'machine', 'mesh': 'base_box', 'translation': [0.0, 0.05, 0.0]},
        {'name': 'shaft', 'parent': 'base', 'mesh': 'shaft_cyl', 'translation': [0.0, 0.2, 0.0]},
        {'name': 'gear_a', 'parent': 'shaft', 'mesh': 'gear12', 'translation': [0.0, 0.1, 0.0],
         'rotation_deg': [0.0, 15.0, 0.0]},
        {'name': 'gear_b', 'parent': 'base', 'mesh': 'gear12', 'translation': [0.2, 0.3, 0.0],
         'rotation_deg': [0.0, 0.0, 90.0], 'scale': [1.0, 1.0, 1.0]},
    ]
    return nodes, meshes, materials


def _f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def _parse_obj(text):
    objects, order, parents, world = {}, [], {}, {}
    current = None
    for line in text.splitlines():
        if line.startswith('# node '):
            fields = dict(tok.split('=', 1) for tok in line[7:].split()[1:])
            name = line[7:].split()[0]
            parents[name] = None if fields.get('parent', '-') == '-' else fields['parent']
        elif line.startswith('o '):
            current = line[2:].strip()
            objects[current] = 0
            world[current] = []
            order.append(current)
        elif line.startswith('v '):
            if current is None:
                raise ValueError('OBJ vertex before any object')
            objects[current] += 1
            world[current].append([float(t) for t in line.split()[1:4]])
    return objects, order, parents, world


def _parse_gltf(text):
    g = json.loads(text)
    buf = g['buffers'][0]
    prefix = 'data:application/octet-stream;base64,'
    if not buf['uri'].startswith(prefix):
        raise ValueError('glTF buffer is not an embedded base64 data URI')
    data = base64.b64decode(buf['uri'][len(prefix):], validate=True)
    if len(data) != buf['byteLength']:
        raise ValueError('glTF buffer length mismatch')
    nodes = g['nodes']
    parents = {n['name']: None for n in nodes}
    for n in nodes:
        for c in n.get('children', []):
            parents[nodes[c]['name']] = n['name']
    mats = {}

    def local(n):
        r3 = _rot3_from_quat_xyzw(n.get('rotation', [0.0, 0.0, 0.0, 1.0]))
        return _m4_trs(n.get('translation', [0.0, 0.0, 0.0]), r3, n.get('scale', [1.0, 1.0, 1.0]))

    def world_m(i):
        if i not in mats:
            n = nodes[i]
            p = parents[n['name']]
            m = local(n)
            if p is not None:
                pi = next(k for k, x in enumerate(nodes) if x['name'] == p)
                m = _m4mul(world_m(pi), m)
            mats[i] = m
        return mats[i]
    objects, world = {}, {}
    for i, n in enumerate(nodes):
        if 'mesh' not in n:
            continue
        prim = g['meshes'][n['mesh']]['primitives'][0]
        acc = g['accessors'][prim['attributes']['POSITION']]
        view = g['bufferViews'][acc['bufferView']]
        off = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        flat = struct.unpack_from('<%df' % (3 * acc['count']), data, off)
        iacc = g['accessors'][prim['indices']]
        iview = g['bufferViews'][iacc['bufferView']]
        idx = struct.unpack_from('<%dI' % iacc['count'], data, iview.get('byteOffset', 0))
        if idx and max(idx) >= acc['count']:
            raise ValueError('glTF index out of range')
        m = world_m(i)
        objects[n['name']] = acc['count']
        world[n['name']] = [_m4pt(m, flat[3 * k:3 * k + 3]) for k in range(acc['count'])]
    return g, objects, parents, world


def export_mesh(*, nodes=None, meshes=None, materials=None, include_text=True, **extra):
    """Export a scene graph to OBJ (+MTL) text and to glTF 2.0 JSON with an embedded base64
    buffer, then re-import both and compare object count, vertex count, hierarchy and world
    positions.

    nodes: [{'name', 'parent' (earlier node name or omitted), 'translation', 'rotation_deg'
    (Euler XYZ), 'scale' (positive), 'mesh' (key into meshes)}]; meshes: {name: {'vertices',
    'faces', 'material'}}; materials: {name: {'base_color' [r,g,b,a], 'metallic',
    'roughness'}}. OBJ has no hierarchy: vertices are written in world space and the
    hierarchy is kept as '# node NAME parent=P mesh=M' comments. glTF keeps local TRS
    (rotation as a quaternion), shared meshes and PBR metallic-roughness materials.
    """
    _no_extra(extra)
    include_text = _bool(include_text, 'include_text')
    if nodes is None and meshes is None and materials is None:
        nodes, meshes, materials = _default_scene()
    elif nodes is None or meshes is None:
        raise ValueError('nodes and meshes must be given together')
    materials = {} if materials is None else materials
    if not isinstance(materials, dict) or len(materials) > 64:
        raise ValueError('materials must be an object with <= 64 entries')
    mats = {}
    for mname, md in materials.items():
        mname = _name(mname, 'materials key')
        d = _obj(md, {'base_color', 'metallic', 'roughness'}, set(), f'materials[{mname}]')
        mats[mname] = {'base_color': _vec(d.get('base_color', [0.8, 0.8, 0.8, 1.0]), 4,
                                          f'materials[{mname}].base_color', 0, 1),
                       'metallic': _num(d.get('metallic', 0.0), 0, 1, f'materials[{mname}].metallic'),
                       'roughness': _num(d.get('roughness', 0.5), 0, 1,
                                         f'materials[{mname}].roughness')}
    if not isinstance(meshes, dict) or not 1 <= len(meshes) <= 256:
        raise ValueError('meshes must be an object with 1 to 256 entries')
    mesh_data = {}
    for key, md in meshes.items():
        key = _name(key, 'meshes key')
        if not isinstance(md, dict):
            raise ValueError(f'meshes[{key}] must be an object')
        mat = md.get('material')
        if mat is not None and mat not in mats:
            raise ValueError(f'meshes[{key}].material {mat!r} is not defined in materials')
        core = {k: v for k, v in md.items() if k != 'material'}
        m = _mesh(core, f'meshes[{key}]')
        m['material'] = mat
        mesh_data[key] = m
    nodes = _list(nodes, 'nodes', 1, 512)
    nl, index = [], {}
    for i, nd in enumerate(nodes):
        label = f'nodes[{i}]'
        d = _obj(nd, {'name', 'parent', 'translation', 'rotation_deg', 'scale', 'mesh'}, {'name'}, label)
        name = _name(d['name'], f'{label}.name')
        if name in index:
            raise ValueError(f'duplicate node name {name!r}')
        parent = d.get('parent')
        if parent is not None and parent not in index:
            raise ValueError(f'{label}.parent must name an earlier node')
        mesh = d.get('mesh')
        if mesh is not None and mesh not in mesh_data:
            raise ValueError(f'{label}.mesh {mesh!r} is not defined in meshes')
        t = _vec(d.get('translation', [0.0, 0.0, 0.0]), 3, f'{label}.translation')
        r = _vec(d.get('rotation_deg', [0.0, 0.0, 0.0]), 3, f'{label}.rotation_deg', -720, 720)
        s = _vec(d.get('scale', [1.0, 1.0, 1.0]), 3, f'{label}.scale', 1e-3, 1e3)
        local = _m4_trs(t, _rot3(r), s)
        world = local if parent is None else _m4mul(nl[index[parent]]['world'], local)
        index[name] = i
        nl.append({'name': name, 'parent': parent, 't': t, 'r': r, 's': s, 'mesh': mesh,
                   'world': world})
    total_v = sum(len(mesh_data[n['mesh']]['vertices']) for n in nl if n['mesh'])
    if total_v > MAX_VERTICES:
        raise ValueError(f'scene exceeds {MAX_VERTICES} exported vertices')

    # ---- OBJ + MTL
    obj = ['# red-rose modeling3d_v23 OBJ export (world-space vertices)', 'mtllib scene.mtl']
    for n in nl:
        obj.append(f'# node {n["name"]} parent={n["parent"] or "-"} mesh={n["mesh"] or "-"}')
    base = 1
    world_expected = {}
    for n in nl:
        if not n['mesh']:
            continue
        m = mesh_data[n['mesh']]
        obj.append(f'o {n["name"]}')
        if m['material']:
            obj.append(f'usemtl {m["material"]}')
        wv = [_m4pt(n['world'], v) for v in m['vertices']]
        world_expected[n['name']] = wv
        obj += ['v %.6f %.6f %.6f' % tuple(v) for v in wv]
        obj += ['f %d %d %d' % (a + base, b + base, c + base) for a, b, c in m['faces']]
        base += len(wv)
    obj_text = '\n'.join(obj) + '\n'
    mtl = ['# red-rose modeling3d_v23 MTL export']
    for mname, md in mats.items():
        c = md['base_color']
        mtl += [f'newmtl {mname}', 'Kd %.6f %.6f %.6f' % (c[0], c[1], c[2]), 'd %.6f' % c[3],
                'Pm %.6f' % md['metallic'], 'Pr %.6f' % md['roughness'], '']
    mtl_text = '\n'.join(mtl) + '\n'

    # ---- glTF 2.0
    blob = bytearray()
    views, accessors, gl_meshes, mesh_index = [], [], [], {}
    mat_names = list(mats)
    for key in [n['mesh'] for n in nl if n['mesh']]:
        if key in mesh_index:
            continue
        m = mesh_data[key]
        flat = [_f32(c) for v in m['vertices'] for c in v]
        pos_bytes = struct.pack('<%df' % len(flat), *flat)
        views.append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(pos_bytes),
                      'target': 34962})
        blob += pos_bytes
        accessors.append({'bufferView': len(views) - 1, 'componentType': 5126,
                          'count': len(m['vertices']), 'type': 'VEC3',
                          'min': [min(flat[k::3]) for k in range(3)],
                          'max': [max(flat[k::3]) for k in range(3)]})
        idx = [i for f in m['faces'] for i in f]
        idx_bytes = struct.pack('<%dI' % len(idx), *idx)
        views.append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(idx_bytes),
                      'target': 34963})
        blob += idx_bytes
        accessors.append({'bufferView': len(views) - 1, 'componentType': 5125,
                          'count': len(idx), 'type': 'SCALAR'})
        prim = {'attributes': {'POSITION': len(accessors) - 2}, 'indices': len(accessors) - 1,
                'mode': 4}
        if m['material']:
            prim['material'] = mat_names.index(m['material'])
        mesh_index[key] = len(gl_meshes)
        gl_meshes.append({'name': key, 'primitives': [prim]})
    gl_nodes = []
    for n in nl:
        q = _quat_from_euler(n['r'])
        g = {'name': n['name']}
        if any(n['t']):
            g['translation'] = n['t']
        if any(n['r']):
            g['rotation'] = [q[1], q[2], q[3], q[0]]
        if n['s'] != [1.0, 1.0, 1.0]:
            g['scale'] = n['s']
        if n['mesh']:
            g['mesh'] = mesh_index[n['mesh']]
        kids = [k for k, c in enumerate(nl) if c['parent'] == n['name']]
        if kids:
            g['children'] = kids
        gl_nodes.append(g)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'red-rose modeling3d_v23'},
        'scene': 0,
        'scenes': [{'nodes': [k for k, n in enumerate(nl) if n['parent'] is None]}],
        'nodes': gl_nodes, 'meshes': gl_meshes,
        'materials': [{'name': k, 'pbrMetallicRoughness': {
            'baseColorFactor': v['base_color'], 'metallicFactor': v['metallic'],
            'roughnessFactor': v['roughness']}} for k, v in mats.items()],
        'accessors': accessors, 'bufferViews': views,
        'buffers': [{'byteLength': len(blob),
                     'uri': 'data:application/octet-stream;base64,' +
                            base64.b64encode(bytes(blob)).decode('ascii')}],
    }
    if not gltf['materials']:
        del gltf['materials']
    gltf_json = json.dumps(gltf, sort_keys=True, separators=(',', ':'))

    # ---- round trip
    o_objects, o_order, o_parents, o_world = _parse_obj(obj_text)
    _, g_objects, g_parents, g_world = _parse_gltf(gltf_json)
    exp_objects = {n['name']: len(mesh_data[n['mesh']]['vertices']) for n in nl if n['mesh']}
    exp_parents = {n['name']: n['parent'] for n in nl}
    max_diff_obj = max((abs(a - b) for k in world_expected
                        for p, q in zip(world_expected[k], o_world[k]) for a, b in zip(p, q)),
                       default=0.0)
    max_diff_gltf = max((abs(a - b) for k in world_expected
                         for p, q in zip(world_expected[k], g_world[k]) for a, b in zip(p, q)),
                        default=0.0)
    roundtrip = {
        'expected_object_count': len(exp_objects),
        'obj_object_count': len(o_objects), 'gltf_object_count': len(g_objects),
        'expected_vertex_count': sum(exp_objects.values()),
        'obj_vertex_count': sum(o_objects.values()), 'gltf_vertex_count': sum(g_objects.values()),
        'per_object_vertices_match': o_objects == exp_objects == g_objects,
        'obj_hierarchy_match': o_parents == exp_parents,
        'gltf_hierarchy_match': g_parents == exp_parents,
        'obj_max_world_position_error': max_diff_obj,
        'gltf_max_world_position_error': max_diff_gltf,
    }
    roundtrip['ok'] = (roundtrip['per_object_vertices_match'] and roundtrip['obj_hierarchy_match']
                       and roundtrip['gltf_hierarchy_match'] and max_diff_obj < 1e-4
                       and max_diff_gltf < 1e-4)
    result = {
        'node_count': len(nl), 'mesh_count': len(mesh_data), 'material_count': len(mats),
        'roundtrip': roundtrip,
        'obj_sha256': hashlib.sha256(obj_text.encode('utf-8')).hexdigest(),
        'mtl_sha256': hashlib.sha256(mtl_text.encode('utf-8')).hexdigest(),
        'gltf_sha256': hashlib.sha256(gltf_json.encode('utf-8')).hexdigest(),
        'gltf_buffer_bytes': len(blob),
        'gltf': gltf,
    }
    if include_text:
        result.update({'obj_text': obj_text, 'mtl_text': mtl_text, 'gltf_json': gltf_json})
    return _pack('export_mesh', result,
                 ['OBJ stores world-space positions only (no normals/UVs); hierarchy survives only as '
                  'comments this module writes and reads back',
                  'glTF 2.0: one embedded base64 buffer, float32 POSITION + uint32 indices, '
                  'PBR metallic-roughness factors only (no textures)',
                  'MTL uses Kd/d plus the PBR extension keys Pm/Pr',
                  'outputs are returned as strings/dicts; nothing is written to disk',
                  NO_GPU],
                 ['<= 512 nodes, <= 256 meshes, <= 64 materials, <= 50000 exported vertices',
                  'parents must be declared before children; scale must be positive'])


# --------------------------------------------------------------------------- 18.09 lod_budget

def _cluster(verts, faces, res, lo, ext):
    cells = [ext[k] / res if ext[k] > 0 else 1.0 for k in range(3)]
    keys, remap, sums, counts = {}, [], [], []
    for v in verts:
        key = tuple(min(res - 1, int((v[k] - lo[k]) / cells[k])) for k in range(3))
        ci = keys.get(key)
        if ci is None:
            ci = keys[key] = len(sums)
            sums.append([0.0, 0.0, 0.0])
            counts.append(0)
        s = sums[ci]
        s[0] += v[0]
        s[1] += v[1]
        s[2] += v[2]
        counts[ci] += 1
        remap.append(ci)
    reps = [[s[0] / c, s[1] / c, s[2] / c] for s, c in zip(sums, counts)]
    seen, nf = set(), []
    for a, b, c in faces:
        a, b, c = remap[a], remap[b], remap[c]
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            continue
        seen.add(key)
        nf.append([a, b, c])
    err = max(_length(_sub(v, reps[remap[i]])) for i, v in enumerate(verts))
    return reps, nf, err


def lod_budget(*, mesh=None, ratios=(1.0, 0.5, 0.25, 0.1), distances=(1.5, 3.0, 6.0, 12.0, 24.0, 48.0),
               viewport_height=1080, vfov_deg=50.0, max_error_px=1.0, budget_ms=0.5,
               ms_per_triangle=1e-4, ms_per_draw=0.01, min_screen_px=1.0, **extra):
    """Vertex-clustering LODs + screen-space LOD selection under a frame-time budget.

    For each target ratio, a uniform grid over the mesh bounding box is searched (bisection
    on cells per axis) for the finest grid whose cluster count <= ratio * vertices; each
    cluster collapses to its mean and degenerate/duplicate triangles are dropped. Error
    (Hausdorff-like, sampled on every original vertex) = max distance from an original
    vertex to its cluster representative. Selection: per instance the coarsest LOD whose
    error projects to <= max_error_px; if the summed cost (triangles * ms_per_triangle +
    ms_per_draw) exceeds budget_ms, instances are greedily coarsened by best cost saved per
    pixel of error added. Instances smaller than min_screen_px are culled.
    """
    _no_extra(extra)
    if mesh is None:
        mesh = _uv_sphere(1.0, 48, 24)
    mesh = _mesh(mesh, 'mesh')
    ratios = _list(ratios, 'ratios', 1, 8)
    ratios = [_num(r, 0, 1, f'ratios[{i}]', low_open=True) for i, r in enumerate(ratios)]
    if any(b >= a for a, b in zip(ratios, ratios[1:])):
        raise ValueError('ratios must be strictly decreasing')
    distances = _list(distances, 'distances', 1, 1000)
    distances = [_num(d, 1e-3, 1e6, f'distances[{i}]') for i, d in enumerate(distances)]
    vh = _int(viewport_height, 16, 16384, 'viewport_height')
    vfov = math.radians(_num(vfov_deg, 1, 170, 'vfov_deg'))
    max_error_px = _num(max_error_px, 0, 1e4, 'max_error_px')
    budget_ms = _num(budget_ms, 0, 1e4, 'budget_ms')
    ms_tri = _num(ms_per_triangle, 0, 1, 'ms_per_triangle')
    ms_draw = _num(ms_per_draw, 0, 100, 'ms_per_draw')
    min_px = _num(min_screen_px, 0, 1e4, 'min_screen_px')
    verts, faces = mesh['vertices'], mesh['faces']
    nv = len(verts)
    lo, hi = _bbox(verts)
    ext = [hi[k] - lo[k] for k in range(3)]
    center = [(lo[k] + hi[k]) / 2 for k in range(3)]
    radius = max(_length(_sub(v, center)) for v in verts)
    lods = []
    for ratio in ratios:
        target = max(3, round(ratio * nv))
        if target >= nv:
            lods.append({'ratio': ratio, 'grid': None, 'vertices': nv, 'triangles': len(faces),
                         'max_error': 0.0})
            continue
        a, b, best = 1, 1024, None
        while a <= b:
            mid = (a + b) // 2
            reps, nf, err = _cluster(verts, faces, mid, lo, ext)
            if len(reps) <= target:
                best = (mid, reps, nf, err)
                a = mid + 1
            else:
                b = mid - 1
        if best is None:
            best = (1,) + _cluster(verts, faces, 1, lo, ext)
        lods.append({'ratio': ratio, 'grid': best[0], 'vertices': len(best[1]),
                     'triangles': len(best[2]), 'max_error': best[3]})
    for L in lods:
        L['cost_ms'] = L['triangles'] * ms_tri + ms_draw
        L['quality'] = 1 - L['max_error'] / radius if radius > 0 else 1.0
    px_per_m = vh / (2 * math.tan(vfov / 2))
    inst = []
    for i, d in enumerate(distances):
        size_px = 2 * radius / d * px_per_m
        errs = [L['max_error'] / d * px_per_m for L in lods]
        if size_px < min_px:
            choice = None
        else:
            choice = 0
            for k in range(len(lods)):
                if errs[k] <= max_error_px:
                    choice = k
        inst.append({'index': i, 'distance': d, 'screen_px': size_px, 'error_px': errs,
                     'lod': choice})

    def cost(x):
        return 0.0 if x['lod'] is None else lods[x['lod']]['cost_ms']
    total = sum(cost(x) for x in inst)
    degraded = 0
    while total > budget_ms + 1e-12:
        best, best_score = None, None
        for x in inst:
            if x['lod'] is None or x['lod'] + 1 >= len(lods):
                continue
            k = x['lod']
            saving = lods[k]['cost_ms'] - lods[k + 1]['cost_ms']
            if saving <= 0:
                continue
            score = saving / (x['error_px'][k + 1] - x['error_px'][k] + 1e-9)
            if best_score is None or score > best_score:
                best, best_score = x, score
        if best is None:
            break
        best['lod'] += 1
        degraded += 1
        total = sum(cost(x) for x in inst)
    for x in inst:
        x['cost_ms'] = cost(x)
        x['selected_error_px'] = None if x['lod'] is None else x['error_px'][x['lod']]
    verts_seq = [L['vertices'] for L in lods]
    err_seq = [L['max_error'] for L in lods]
    result = {
        'source_vertices': nv, 'source_triangles': len(faces), 'bounding_radius': radius,
        'lods': lods,
        'vertex_count_monotonic': all(b < a for a, b in zip(verts_seq, verts_seq[1:])),
        'error_monotonic': all(b >= a for a, b in zip(err_seq, err_seq[1:])),
        'instances': inst, 'total_ms': total, 'budget_ms': budget_ms,
        'budget_met': total <= budget_ms + 1e-12, 'degrade_steps': degraded,
        'worst_selected_error_px': max((x['selected_error_px'] for x in inst
                                        if x['selected_error_px'] is not None), default=0.0),
    }
    return _pack('lod_budget', result,
                 ['vertex clustering on a uniform grid (Rossignac-Borrel style); cluster = mean position',
                  'error = max original-vertex to representative distance (one-sided, sampled on '
                  'vertices; not a full surface Hausdorff distance)',
                  'cost model is linear: triangles * ms_per_triangle + ms_per_draw; real GPU cost is '
                  'not measured',
                  'screen size from bounding-sphere diameter and vertical FOV',
                  NO_GPU],
                 ['<= 50000 vertices, <= 8 LOD ratios, <= 1000 instances, grid <= 1024 cells per axis',
                  'if every instance is already at the coarsest LOD the budget may stay unmet (budget_met false)'])


# --------------------------------------------------------------------------- 18.10 cutaway

def _clip_mesh(verts, faces, p0, n):
    d = [_dot(_sub(v, p0), n) for v in verts]
    out, vmap, emap, nf, crossings = [], {}, {}, [], 0

    def keep(i):
        if i not in vmap:
            vmap[i] = len(out)
            out.append(verts[i][:])
        return vmap[i]

    def cut(i, j):
        a, b = (i, j) if i < j else (j, i)
        if (a, b) not in emap:
            t = d[a] / (d[a] - d[b])
            q = _add(verts[a], _mul(_sub(verts[b], verts[a]), t))
            q = _sub(q, _mul(n, _dot(_sub(q, p0), n)))
            emap[(a, b)] = len(out)
            out.append(q)
        return emap[(a, b)]
    for f in faces:
        poly = []
        inside = [d[i] <= 0 for i in f]
        if not any(inside):
            continue
        if not all(inside):
            crossings += 1
        for k in range(3):
            i, j = f[k], f[(k + 1) % 3]
            if inside[k]:
                poly.append(keep(i))
            if inside[k] != inside[(k + 1) % 3]:
                poly.append(cut(i, j))
        for k in range(1, len(poly) - 1):
            tri = [poly[0], poly[k], poly[k + 1]]
            if len(set(tri)) == 3:
                nf.append(tri)
    return out, nf, crossings


def _default_assembly():
    return [
        {'name': 'housing', 'shape': 'box', 'size': [1.0, 0.6, 1.0], 'position': [0.0, 0.0, 0.0],
         'explode_axis': [0.0, -1.0, 0.0], 'explode_order': 1},
        {'name': 'shaft', 'shape': 'cylinder', 'radius': 0.05, 'height': 1.4, 'segments': 24,
         'position': [0.0, 0.0, 0.0], 'explode_axis': [0.0, 1.0, 0.0], 'explode_order': 2},
        {'name': 'gear', 'shape': 'gear', 'teeth': 12, 'outer_radius': 0.3, 'root_radius': 0.25,
         'thickness': 0.1, 'position': [0.0, 0.45, 0.0], 'explode_axis': [0.0, 1.0, 0.0],
         'explode_order': 1},
    ]


def cutaway(*, parts=None, plane_point=(0.0, 0.0, 0.0), plane_normal=(0.0, 0.0, 1.0),
            explode_distance=None, explode_step=0.02, min_gap=1e-3, include_meshes=False, **extra):
    """Cutaway + exploded view of a machine.

    Every part with cut = true (default) is clipped by the plane: triangles are clipped
    (Sutherland-Hodgman against one plane) and the side where (x - plane_point).normal > 0
    is removed; new vertices are snapped onto the plane. The section is left open (no cap).
    Exploded view: part i moves by explode_axis_i * explode_order_i * s (axis defaults to the
    direction from the assembly centre to the part, or +y). With explode_distance = None the
    smallest s (in explode_step increments, <= 500 steps) that separates every pair of part
    AABBs by >= min_gap is searched; AABB-disjoint parts cannot intersect.
    """
    _no_extra(extra)
    if parts is None:
        parts = _default_assembly()
    built = _build_parts(parts, 'parts', extra_keys=('explode_axis', 'explode_order', 'cut'))
    p0 = _vec(plane_point, 3, 'plane_point')
    n = _unit(plane_normal, 'plane_normal')
    step = _num(explode_step, 1e-4, 10, 'explode_step')
    min_gap = _num(min_gap, 0, 10, 'min_gap')
    include_meshes = _bool(include_meshes, 'include_meshes')
    if explode_distance is not None:
        explode_distance = _num(explode_distance, 0, 1e4, 'explode_distance')
    centre = [sum(p['obb']['center'][k] for p in built) / len(built) for k in range(3)]
    cut_parts = []
    for i, p in enumerate(built):
        spec = p['spec']
        do_cut = _bool(spec.get('cut', True), f'parts[{i}].cut')
        order = _int(spec.get('explode_order', 1), 0, 100, f'parts[{i}].explode_order')
        if 'explode_axis' in spec:
            axis = _unit(spec['explode_axis'], f'parts[{i}].explode_axis')
        else:
            axis = _normalize(_sub(p['obb']['center'], centre))
            if _length(axis) < 0.5:
                axis = [0.0, 1.0, 0.0]
        if do_cut:
            verts, faces, crossings = _clip_mesh(p['world'], p['faces'], p0, n)
        else:
            verts, faces, crossings = [v[:] for v in p['world']], [f[:] for f in p['faces']], 0
        max_side = max((_dot(_sub(v, p0), n) for v in verts), default=None)
        cut_parts.append({'name': p['name'], 'cut': do_cut, 'verts': verts, 'faces': faces,
                          'axis': axis, 'order': order, 'crossings': crossings,
                          'max_signed_distance': max_side,
                          'source_vertices': len(p['world']), 'source_faces': len(p['faces'])})
    live = [c for c in cut_parts if c['verts']]
    boxes = {c['name']: _bbox(c['verts']) for c in live}

    def overlaps(s):
        moved = {}
        for c in live:
            off = _mul(c['axis'], c['order'] * s)
            lo, hi = boxes[c['name']]
            moved[c['name']] = (_add(lo, off), _add(hi, off))
        bad = []
        names = [c['name'] for c in live]
        for i in range(len(names)):
            for k in range(i + 1, len(names)):
                if _aabb_gap(moved[names[i]], moved[names[k]]) < min_gap:
                    bad.append([names[i], names[k]])
        return bad, moved
    initial_bad, _ = overlaps(0.0)
    if explode_distance is None:
        s, searched = 0.0, 0
        bad, moved = initial_bad, None
        while bad and searched < 500:
            searched += 1
            s = searched * step
            bad, moved = overlaps(s)
        explode_distance = s
    bad, moved = overlaps(explode_distance)
    rows = []
    for c in cut_parts:
        row = {'name': c['name'], 'cut': c['cut'], 'source_vertices': c['source_vertices'],
               'source_faces': c['source_faces'], 'vertices': len(c['verts']),
               'faces': len(c['faces']), 'section_crossing_faces': c['crossings'],
               'max_signed_distance': c['max_signed_distance'],
               'no_vertices_on_removed_side': (c['max_signed_distance'] is None
                                               or c['max_signed_distance'] <= 1e-9),
               'explode_axis': c['axis'], 'explode_order': c['order'],
               'explode_offset': _mul(c['axis'], c['order'] * explode_distance)}
        if c['name'] in moved:
            row['exploded_aabb'] = {'min': moved[c['name']][0], 'max': moved[c['name']][1]}
        if include_meshes:
            off = row['explode_offset']
            row['mesh'] = {'vertices': [_add(v, off) for v in c['verts']], 'faces': c['faces']}
        rows.append(row)
    result = {
        'plane': {'point': p0, 'normal': n, 'removed_side': 'positive'},
        'parts': rows,
        'all_cut_parts_clean': all(r['no_vertices_on_removed_side'] for r in rows if r['cut']),
        'assembled_overlapping_pairs': initial_bad,
        'explode_distance': explode_distance,
        'exploded_overlapping_pairs': bad,
        'exploded_parts_separated': not bad,
        'fully_removed_parts': [c['name'] for c in cut_parts if not c['verts']],
    }
    return _pack('cutaway', result,
                 ['single cutting plane; triangles clipped Sutherland-Hodgman style, new vertices '
                  'snapped onto the plane; the section is left open (no cap faces)',
                  'explode separation is checked with world AABBs (sufficient, conservative): '
                  'disjoint AABBs guarantee no intersection, overlapping AABBs are reported as possible contact',
                  'parts are rigid; explode moves along fixed per-part axes, scaled by explode_order',
                  NO_GPU],
                 ['<= 64 parts, <= 50000 vertices in total',
                  'auto explode search <= 500 steps of explode_step'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'machine_mesh': machine_mesh, 'car_rig': car_rig, 'cloth3d': cloth3d, 'camera3d': camera3d,
    'skinning': skinning, 'uv_atlas': uv_atlas, 'area_lighting': area_lighting,
    'export_mesh': export_mesh, 'lod_budget': lod_budget, 'cutaway': cutaway,
}


def run(op, params=None):
    """Validate and dispatch: run('car_rig', {'steering_deg': 25}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
