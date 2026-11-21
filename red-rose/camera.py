"""Self-contained 2.5D parallax scene renderer using SVG geometry."""
import html, math

def _color(v):
    if not isinstance(v,str) or len(v)!=7 or v[0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in v[1:]):
        raise ValueError('invalid color')
    return v

def camera_frame(t,duration,width,height,recipe):
    if not 0<=t<=duration or duration<=0 or width<16 or height<16: raise ValueError('invalid camera timeline')
    camera=recipe.get('camera',{})
    pan=float(camera.get('pan',.16)); zoom=float(camera.get('zoom',.08))
    if not all(math.isfinite(v) and abs(v)<=2 for v in (pan,zoom)): raise ValueError('invalid camera motion')
    layers=recipe.get('layers',[])
    if not isinstance(layers,list) or len(layers)>100: raise ValueError('invalid layers')
    phase=t/duration
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         f'<rect width="100%" height="100%" fill="{_color(recipe.get("background","#101827"))}"/>']
    for layer in sorted(layers,key=lambda l:float(l.get('depth',0)),reverse=True):
        depth=float(layer.get('depth',0))
        if not math.isfinite(depth) or depth<0 or depth>10: raise ValueError('invalid depth')
        factor=1/(1+depth)
        shift=(phase-.5)*pan*width*factor
        scale=1+zoom*phase*factor
        x=float(layer.get('x',.5))*width; y=float(layer.get('y',.5))*height
        if not all(math.isfinite(v) for v in (x,y)): raise ValueError('invalid coordinates')
        color=_color(layer.get('color','#e35b79'))
        out.append(f'<g transform="translate({shift:.3f} 0) translate({x:.3f} {y:.3f}) scale({scale:.5f})">')
        kind=layer.get('shape','circle')
        if kind=='circle':
            r=float(layer.get('size',.1))*min(width,height)
            if not 0<r<max(width,height): raise ValueError('invalid radius')
            out.append(f'<circle r="{r:.3f}" fill="{color}"/>')
        elif kind=='rect':
            size=float(layer.get('size',.2))*min(width,height)
            if not 0<size<max(width,height): raise ValueError('invalid size')
            out.append(f'<rect x="{-size/2:.3f}" y="{-size/2:.3f}" width="{size:.3f}" height="{size:.3f}" rx="{size*.1:.3f}" fill="{color}"/>')
        elif kind=='text':
            label=html.escape(str(layer.get('text',''))[:200])
            out.append(f'<text text-anchor="middle" fill="{color}" font-size="{width*.06:.3f}">{label}</text>')
        else: raise ValueError('unsupported shape')
        out.append('</g>')
    out.append('</svg>')
    return ''.join(out)
