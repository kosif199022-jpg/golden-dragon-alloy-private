"""CPU rasterization of a swept line nib; deterministic coverage supersampling."""
import io
import math
import numpy as np
from PIL import Image, ImageDraw
from .strokes import Stroke
from .tools import Qalam


def rgb(value):
    if not isinstance(value, (tuple,list)) or len(value) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in value):
        raise ValueError("RGB must contain three integers in [0,255]")
    return tuple(value)


def render_strokes(strokes, width=1080, height=1080, background=(255,255,255), supersample=4):
    if (type(width) is not int or type(height) is not int or
            not 1 <= width <= 4096 or not 1 <= height <= 4096 or
            type(supersample) is not int or not 2 <= supersample <= 8 or
            width*height*supersample**2 > 100_000_000):
        raise ValueError("invalid canvas or supersample budget")
    bg = rgb(background)
    canvas = np.empty((height,width,3), dtype=np.uint8)
    canvas[:] = bg
    for stroke, nib in strokes:
        if not isinstance(stroke, Stroke) or not isinstance(nib, Qalam) or stroke.tool != "qalam":
            raise ValueError("Stage 1 requires qalam strokes")
        color = np.array(rgb(stroke.pigment), dtype=np.uint32)
        n = max(2, math.ceil(stroke.length*2)+1)
        if n > 200_000:
            raise ValueError("stroke exceeds sampling budget")
        xy, _, _, pressure, _ = stroke.at_distance(np.linspace(0, stroke.length, n))
        lo, hi = nib.endpoints(xy, pressure)
        mask = Image.new("L", (width*supersample,height*supersample))
        draw = ImageDraw.Draw(mask)
        axis = nib.axis
        for j in range(n-1):
            quad = np.array([lo[j],hi[j],hi[j+1],lo[j+1]])
            # Skip zero-area sweeps (zero pressure or parallel nib).
            delta = xy[j+1]-xy[j]
            if abs(delta[0]*axis[1]-delta[1]*axis[0]) < 1e-12 or pressure[j]+pressure[j+1] == 0:
                continue
            coords = [tuple(v) for v in np.rint(quad*supersample).astype(int)]
            draw.polygon(coords, fill=255)
        coverage = np.asarray(mask.resize((width,height), Image.Resampling.BOX), dtype=np.uint32)[...,None]
        canvas = ((canvas.astype(np.uint32)*(255-coverage)+color*coverage+127)//255).astype(np.uint8)
    return canvas


def render_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    allowed = {"width","height","background","supersample","strokes"}
    if set(spec)-allowed or not isinstance(spec.get("strokes"),list) or not 1 <= len(spec["strokes"]) <= 256:
        raise ValueError("invalid spec or strokes count (1..256)")
    pairs = []
    for row in spec["strokes"]:
        if not isinstance(row,dict):
            raise ValueError("stroke must be an object")
        data = dict(row)
        tool = data.pop("nib", {})
        try:
            pairs.append((Stroke(**data), Qalam(**tool)))
        except (TypeError, KeyError) as exc:
            raise ValueError("invalid stroke/nib fields") from exc
    return render_strokes(pairs, **{k:v for k,v in spec.items() if k!="strokes"})


def png_bytes(array):
    with io.BytesIO() as out:
        Image.fromarray(array).save(out, format="PNG", compress_level=9, optimize=False)
        return out.getvalue()
