"""Native Red Rose art-directed 2.5D cinema illustration renderer.

Independent of earlier dragon skills. SVG scene composed procedurally; no models
or third-party source artwork. Delivers editable project information, not a
claim of photorealistic character generation.
"""
import html
import math
from camera import _color
from motion_tracks import scalar


def _phase(t,duration):
    if not (isinstance(t,(int,float)) and isinstance(duration,(int,float))
            and math.isfinite(t) and math.isfinite(duration) and duration>0 and 0<=t<=duration):
        raise ValueError('invalid timeline')
    return t/duration


def _caption(recipe,t,width,height):
    cues=recipe.get('captions',[])
    if not isinstance(cues,list) or len(cues)>100:raise ValueError('invalid subtitle list')
    for c in cues:
        if not isinstance(c,dict):raise ValueError('invalid subtitle')
        start,end=c.get('start',-1),c.get('end',-1)
        if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or not math.isfinite(start) or not math.isfinite(end) or end<=start or start<0:
            raise ValueError('invalid caption times')
        if start<=t<end:
            label=html.escape(str(c.get('text',''))[:160])
            size=min(width*.053,24)
            return (f'<g><rect x="{width*.08:.1f}" y="{height*.85:.1f}" width="{width*.84:.1f}" height="{height*.079:.1f}" rx="16" fill="#0d1823" opacity="0.89"/>'
                    f'<text x="{width/2:.2f}" y="{height*.90:.1f}" font-size="{size:.1f}" font-family="sans-serif" fill="#fff4e5" text-anchor="middle">{label}</text></g>')
    return ''


def _mountains(width,height,shift,level,col,amplitude=0.07):
    # Broad bezier silhouette; shift depends on depth and animated camera.
    offset=shift*level
    y=height*(.59+level*.056)
    x0=-width*.25+offset;x1=width*.27+offset;x2=width*.6+offset;x3=width*1.4+offset
    return (f'<path d="M {x0:.1f} {height} L {x0:.1f} {y:.1f} '
            f'Q {x1:.1f} {y-height*amplitude:.1f} {x2:.1f} {y:.1f} '
            f'Q {x3-width*.22:.1f} {y-height*amplitude*.70:.1f} {x3:.1f} {y+height*.015:.1f} '
            f'L {x3:.1f} {height} Z" fill="{col}"/>')


def _character(x,y,k,phase,recipe):
    skin=_color(recipe.get('skin','#e5b98e'))
    coat=_color(recipe.get('coat','#c14f64'))
    hair=_color(recipe.get('hair','#282331'))
    trousers=_color(recipe.get('trousers','#21283f'))
    gait=float(recipe.get('gait',1.0))
    if not math.isfinite(gait) or not 0<=gait<=4: raise ValueError('invalid gait')
    stride=math.sin(2*math.pi*phase*gait)
    opposite=math.sin(2*math.pi*phase*gait+math.pi)
    sway=math.sin(4*math.pi*phase*gait)*2.7
    left=17*stride;right=17*opposite
    # stylized original 2D painted figure (not a likeness to any person)
    return f'''<g transform="translate({x:.2f} {y+sway*k:.2f}) scale({k:.3f})" stroke-linecap="round">
      <ellipse cx="4" cy="87" rx="38" ry="6" fill="#000" opacity=".22"/>
      <path d="M -6 9 L {-19+left:.2f} 78" stroke="{trousers}" stroke-width="15" fill="none"/>
      <path d="M 7 9 L {20+right:.2f} 79" stroke="{trousers}" stroke-width="15" fill="none"/>
      <path d="M -6 78 l -11 5 M 7 79 l 14 4" stroke="#0e1525" stroke-width="11"/>
      <path d="M -17 -57 Q 0 -64 17 -57 L 23 22 Q 0 33 -23 22 Z" fill="{coat}"/>
      <path d="M -12 -51 Q -32 -21 {-36-left:.2f} 7" stroke="{coat}" stroke-width="14" fill="none"/>
      <path d="M 12 -51 Q 32 -21 {36-right:.2f} 7" stroke="{coat}" stroke-width="14" fill="none"/>
      <circle cx="{-36-left:.2f}" cy="7" r="6.5" fill="{skin}"/>
      <circle cx="{36-right:.2f}" cy="7" r="6.5" fill="{skin}"/>
      <rect x="-7" y="-70" width="14" height="18" rx="5" fill="{skin}"/>
      <ellipse cx="0" cy="-88" rx="24" ry="30" fill="{skin}"/>
      <path d="M -24 -90 Q -30 -125 5 -120 Q 30 -113 24 -89 Q 9 -111 -10 -103 Z" fill="{hair}"/>
      <path d="M -6 -87 q 2 -2 4 0 M 8 -87 q 2 -2 4 0" stroke="#4b3332" stroke-width="2" fill="none"/>
      <path d="M -3 -77 Q 3 -74 9 -78" stroke="#7d5345" stroke-width="1.7" fill="none"/>
      <path d="M -4 -53 L 0 -23 L 5 -53" stroke="#f8dbaf" stroke-width="2" fill="none"/>
    </g>'''


def director_frame(t,duration,width,height,recipe):
    """Composite a stylized scene with keyframed camera and actor motion."""
    phase=_phase(t,duration)
    if not isinstance(recipe,dict) or width<160 or height<240 or width>4096 or height>4096:
        raise ValueError('unsupported recipe or dimensions')
    palette=recipe.get('palette',{})
    if not isinstance(palette,dict):raise ValueError('palette must be object')
    sky=_color(palette.get('sky','#0f2138'))
    horizon=_color(palette.get('horizon','#a06f82'))
    distant=_color(palette.get('distant','#435775'))
    middle=_color(palette.get('middle','#263e55'))
    ground=_color(palette.get('ground','#12283b'))
    warm=_color(palette.get('light','#f9d8a5'))
    camera=recipe.get('camera',{})
    if not isinstance(camera,dict):raise ValueError('camera must be object')
    pan=scalar(camera.get('pan_keys'),phase,0.0,-.5,.5)
    zoom=scalar(camera.get('zoom_keys'),phase,1.0,.6,2.0)
    actor=recipe.get('actor',{})
    if not isinstance(actor,dict):raise ValueError('actor must be object')
    ax=scalar(actor.get('x_keys'),phase,.52,-.3,1.3)*width
    ay=scalar(actor.get('y_keys'),phase,.70,.2,1.3)*height
    size=scalar(actor.get('scale_keys'),phase,1.0,.3,3.0)
    shift=pan*width
    # Camera applies to the world, while typography is pinned to the frame.
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<defs>',
         f'<linearGradient id="sky" x2="0" y2="1"><stop stop-color="{sky}"/><stop offset="1" stop-color="{horizon}"/></linearGradient>',
         f'<radialGradient id="glow"><stop stop-color="{warm}" stop-opacity=".55"/><stop offset="1" stop-color="{warm}" stop-opacity="0"/></radialGradient>',
         '</defs>',
         f'<rect width="{width}" height="{height}" fill="url(#sky)"/>',
         f'<circle cx="{width*.76:.1f}" cy="{height*.23:.1f}" r="{width*.23:.1f}" fill="url(#glow)"/>',
         f'<circle cx="{width*.76:.1f}" cy="{height*.23:.1f}" r="{width*.065:.1f}" fill="{warm}" opacity=".92"/>',
         f'<g transform="translate({width/2:.2f} {height/2:.2f}) scale({zoom:.5f}) translate({-width/2:.2f} {-height/2:.2f})">',
         _mountains(width,height,shift*.15,0,distant,.13),
         _mountains(width,height,shift*.55,1,middle,.11),
         f'<rect x="{-width*.2+shift:.1f}" y="{height*.72:.1f}" width="{width*1.4:.1f}" height="{height*.4:.1f}" fill="{ground}"/>',
         f'<path d="M {-width*.2+shift:.1f} {height*.72:.1f} Q {width*.5+shift:.1f} {height*.66:.1f} {width*1.2+shift:.1f} {height*.72:.1f}" stroke="{horizon}" stroke-width="2.2" opacity=".5" fill="none"/>',
         _character(ax-shift*.55,ay,size*min(width/340,height/640),phase,actor),
         '</g>']
    title=str(recipe.get('title',''))[:96]
    if title:
        out.append(f'<text x="{width*.08:.1f}" y="{height*.1:.1f}" font-family="sans-serif" font-size="{max(16,width*.052):.1f}" font-weight="600" fill="#fff3e3">{html.escape(title)}</text>')
    out.append(_caption(recipe,t,width,height))
    out.append('</svg>')
    return ''.join(out)
