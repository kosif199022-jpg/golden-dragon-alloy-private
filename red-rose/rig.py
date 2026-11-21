"""Procedural 2D character rig using analytical two-bone inverse kinematics.

Original artwork, deterministic, no external or legacy dragon skills.
Units are stylized local SVG coordinates relative to the character's hips.
"""
from __future__ import annotations
import math
from camera import _color
from motion_tracks import scalar
from visemes import sample_viseme


def two_bone(start, target, upper, lower, bend=1):
    """Return joint and end for a two-link chain; gracefully clamp unreachable goals.

    bend controls which side of the start->target axis to place the joint.
    """
    if upper <= 0 or lower <= 0 or bend not in (-1, 1):
        raise ValueError('invalid limb geometry')
    values = (*start, *target, upper, lower)
    if not all(isinstance(z, (int, float)) and math.isfinite(z) for z in values):
        raise ValueError('limb coordinates must be finite')
    sx, sy = start
    dx, dy = target[0] - sx, target[1] - sy
    distance = math.hypot(dx, dy)
    if distance < 1e-8:
        dx, dy, distance = 0.0, 1.0, 1.0
    ux, uy = dx / distance, dy / distance
    min_d = abs(upper - lower) + 1e-6
    max_d = upper + lower - 1e-6
    d = max(min_d, min(max_d, distance))
    ex, ey = sx + ux * d, sy + uy * d
    projection = (d * d + upper * upper - lower * lower) / (2 * d)
    altitude = math.sqrt(max(0.0, upper * upper - projection * projection))
    joint = (sx + ux * projection - bend * uy * altitude,
             sy + uy * projection + bend * ux * altitude)
    return joint, (ex, ey)


def rig_character(x: float, y: float, k: float, phase: float, recipe: dict) -> str:
    """Return original illustrated SVG figure with IK legs, bent arms and keyed face."""
    if not isinstance(recipe, dict):
        raise ValueError('recipe must be object')
    vals = (x, y, k, phase)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        raise ValueError('rig numeric inputs must be finite')
    if not .05 <= k <= 8:
        raise ValueError('rig scale outside limits')
    gait = float(recipe.get('gait', 1.0))
    if not math.isfinite(gait) or not 0 <= gait <= 4:
        raise ValueError('invalid gait')
    skin = _color(recipe.get('skin', '#e5b98e'))
    coat = _color(recipe.get('coat', '#c14f64'))
    hair = _color(recipe.get('hair', '#282331'))
    trousers = _color(recipe.get('trousers', '#21283f'))
    eyes = scalar(recipe.get('blink_keys'), phase, 0.0, 0.0, 1.0)
    mouth = scalar(recipe.get('mouth_keys'), phase, 0.15, 0.0, 1.0)
    expression = recipe.get('expression', 'smile')
    if expression not in ('smile', 'serious', 'surprised'):
        raise ValueError('invalid expression')
    angle = 2 * math.pi * phase * gait
    lean = 1.7 * math.sin(angle)
    bob = 1.9 * (1 - math.cos(angle * 2)) * .5

    out = [f'<g transform="translate({x:.2f} {y+bob*k:.2f}) scale({k:.5f})" stroke-linecap="round" stroke-linejoin="round">',
           '<ellipse cx="0" cy="89" rx="40" ry="6.8" fill="#080e19" opacity=".25"/>']
    for side in (-1, 1):
        a = angle + (math.pi if side == 1 else 0)
        sx = 11 * side
        hip = (sx, 13.0)
        swing = math.cos(a) * 20
        foot_lift = max(0.0, math.sin(a)) * 11
        foot_target = (sx + swing, 79.0 - foot_lift)
        knee, foot = two_bone(hip, foot_target, 38, 35, bend=-side)
        out.append(f'<path d="M {hip[0]:.2f} {hip[1]:.2f} L {knee[0]:.2f} {knee[1]:.2f} L {foot[0]:.2f} {foot[1]:.2f}" fill="none" stroke="{trousers}" stroke-width="14"/>')
        out.append(f'<path d="M {foot[0]-5:.2f} {foot[1]+2:.2f} Q {foot[0]+side*9:.2f} {foot[1]+10:.2f} {foot[0]+side*19:.2f} {foot[1]+7:.2f}" fill="none" stroke="#0c1628" stroke-width="8"/>')

    out.append(f'<path d="M -17 -53 Q {lean:.2f} -65 18 -53 L 22 21 Q 0 29 -22 21 Z" fill="{coat}"/>')
    out.append('<path d="M -7 -52 L 0 -19 L 8 -52" fill="none" stroke="#ffdfa6" stroke-width="2.1"/>')
    for side in (-1,1):
        shoulder=(15*side,-46)
        a=angle + (math.pi if side == -1 else 0)
        hand_target=(34*side+8*math.sin(a),7 + 4 * math.sin(a))
        elbow,hand=two_bone(shoulder,hand_target,30,29,bend=side)
        out.append(f'<path d="M {shoulder[0]:.2f} {shoulder[1]:.2f} L {elbow[0]:.2f} {elbow[1]:.2f} L {hand[0]:.2f} {hand[1]:.2f}" fill="none" stroke="{coat}" stroke-width="13"/>')
        out.append(f'<circle cx="{hand[0]:.2f}" cy="{hand[1]:.2f}" r="5.5" fill="{skin}"/>')

    out.append(f'<rect x="-7" y="-70" width="14" height="19" rx="5" fill="{skin}"/>')
    out.append(f'<ellipse cx="{lean:.2f}" cy="-89" rx="24" ry="30" fill="{skin}"/>')
    out.append(f'<path d="M {lean-25:.2f} -92 Q {lean-29:.2f} -127 {lean+5:.2f} -120 Q {lean+29:.2f} -116 {lean+24:.2f} -90 Q {lean+7:.2f} -111 {lean-10:.2f} -103 Z" fill="{hair}"/>')
    eye_h=max(.6,3.0*(1-eyes))
    for eyex in (-7,9):
        out.append(f'<ellipse cx="{lean+eyex:.2f}" cy="-87" rx="2.2" ry="{eye_h:.2f}" fill="#30212d"/>')
    viseme_keys = recipe.get('viseme_keys')
    if viseme_keys is not None:
        pose=sample_viseme(viseme_keys, phase)
        # The energy track explicitly closes the lips during silence.
        if mouth <= .12 or pose == 'closed' or pose == 'neutral':
            out.append(f'<path d="M {lean-6:.2f} -76 L {lean+7:.2f} -76" fill="none" stroke="#744353" stroke-width="2.3"/>')
        elif pose == 'round':
            r=2.2+2.7*mouth
            out.append(f'<ellipse cx="{lean+1.2:.2f}" cy="-76" rx="{r*.8:.2f}" ry="{r:.2f}" fill="#743748"/>')
        elif pose == 'wide':
            out.append(f'<ellipse cx="{lean+1.2:.2f}" cy="-76" rx="{3+6*mouth:.2f}" ry="{1.8+2.1*mouth:.2f}" fill="#743748"/>')
        elif pose == 'teeth':
            out.append(f'<rect x="{lean-7:.2f}" y="-79" width="16" height="{2+3*mouth:.2f}" rx="1.8" fill="#f7e9d7" stroke="#8b5562" stroke-width=".65"/>')
        else:
            radius=2.0+6*mouth
            out.append(f'<ellipse cx="{lean+1.2:.2f}" cy="-76" rx="{radius*.55:.2f}" ry="{radius:.2f}" fill="#744353"/>')
    elif mouth>.32 or expression=='surprised':
        radius=2.0+6*max(mouth,.5 if expression=='surprised' else mouth)
        out.append(f'<ellipse cx="{lean+1.2:.2f}" cy="-76" rx="{radius*.55:.2f}" ry="{radius:.2f}" fill="#744353"/>')
    elif expression=='serious':
        out.append(f'<path d="M {lean-5:.2f} -76 L {lean+8:.2f} -76" fill="none" stroke="#744353" stroke-width="1.8"/>')
    else:
        out.append(f'<path d="M {lean-7:.2f} -78 Q {lean+1:.2f} -70 {lean+9:.2f} -78" fill="none" stroke="#744353" stroke-width="1.8"/>')
    out.append('</g>')
    return ''.join(out)
