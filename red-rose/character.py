"""Native Red Rose 2D character and compositing, no legacy runtime imports."""
import html, math
from camera import camera_frame, _color

def character_frame(t, duration, width, height, recipe):
    if not 0 <= t <= duration or duration <= 0:
        raise ValueError('invalid character time')
    if not isinstance(recipe,dict): raise ValueError('recipe must be dict')
    background=camera_frame(t,duration,width,height,recipe)
    actor=recipe.get('character',{})
    if not isinstance(actor,dict):raise ValueError('character must be dict')
    x=float(actor.get('x',0.5))*width
    y=float(actor.get('y',0.72))*height
    scale=float(actor.get('scale',max(0.4,min(width/320,2))))
    speed=float(actor.get('speed',1))
    if not all(math.isfinite(a) for a in (x,y,scale,speed)) or not 0.1<=scale<=5 or not 0<=speed<=10:
        raise ValueError('invalid character parameters')
    body=_color(actor.get('body','#f5d8c1'))
    accent=_color(actor.get('accent','#e35b79'))
    theta=2*math.pi*t*speed
    swing=math.sin(theta)*20
    bend=math.cos(theta)*11
    tilt=math.sin(theta)*5
    expr=str(actor.get('expression','smile'))
    if expr not in ('smile','neutral'):raise ValueError('invalid expression')
    mouth='<path d="M -8 -91 Q 0 -85 8 -91" stroke="#4e2c42" stroke-width="2" fill="none"/>' if expr=='smile' else '<path d="M -7 -90 L 7 -90" stroke="#4e2c42" stroke-width="2"/>'
    figure=f"""<g transform="translate({x:.3f} {y:.3f}) scale({scale:.4f})" stroke-linecap="round">
<ellipse cx="0" cy="93" rx="34" ry="7" fill="#000000" opacity="0.16"/>
<path d="M 0 -54 L 0 15" stroke="{accent}" stroke-width="24" fill="none"/>
<path d="M 0 -39 Q {-26+swing:.3f} -20 {-34+swing:.3f} 7 M 0 -39 Q {26+swing:.3f} -20 {34+swing:.3f} 7" stroke="{body}" stroke-width="10" fill="none"/>
<path d="M -7 15 L {-22+bend:.3f} 80 M 7 15 L {22-bend:.3f} 80" stroke="#546ca4" stroke-width="13" fill="none"/>
<circle cx="{tilt:.3f}" cy="-83" r="25" fill="{body}"/>
<path d="M {-21+tilt:.3f} -95 Q {tilt:.3f} -123 {21+tilt:.3f} -96" fill="none" stroke="#4e2c42" stroke-width="7"/>
<circle cx="{-8+tilt:.3f}" cy="-88" r="2.4" fill="#302534" stroke="none"/><circle cx="{8+tilt:.3f}" cy="-88" r="2.4" fill="#302534" stroke="none"/>{mouth}</g>"""
    caption=''
    captions=recipe.get('captions',[])
    if not isinstance(captions,list) or len(captions)>100:raise ValueError('invalid captions')
    for c in captions:
        if not isinstance(c,dict):raise ValueError('invalid caption')
        start=float(c.get('start',-1));end=float(c.get('end',-1))
        if not all(math.isfinite(a) for a in (start,end)) or start<0 or end<=start or end>duration+1e-7:
            raise ValueError('invalid caption timing')
        if start<=t<end:
            label=html.escape(str(c.get('text',''))[:140])
            caption=f'<rect x="12" y="{height-72}" width="{width-24}" height="54" rx="16" fill="#111a2b" opacity="0.82"/><text x="{width/2}" y="{height-37}" fill="#ffffff" text-anchor="middle" font-family="sans-serif" font-size="{max(12,min(width*.055,26))}">{label}</text>'
            break
    return background.replace('</svg>',figure+caption+'</svg>')
