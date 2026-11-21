"""Independent multi-shot SVG storyboard with deterministic scene transitions."""
import html, math, re
from render import svg_frame, PALETTE
from camera import camera_frame
from character import character_frame
from director import director_frame

def validate_shots(shots):
    if not isinstance(shots,list) or not shots or len(shots)>100:
        raise ValueError('shots must be a nonempty list of at most 100')
    total=0.0
    for shot in shots:
        if not isinstance(shot,dict) or not 0.1<=shot.get('duration',0)<=120:
            raise ValueError('each shot needs duration 0.1..120')
        if shot.get('transition','cut') not in ('cut','fade'):
            raise ValueError('unsupported transition')
        total+=shot['duration']
    if total>600: raise ValueError('storyboard exceeds 600 seconds')
    return total

def _render(shot,local,width,height):
    recipe=dict(shot.get('recipe',{}));duration=shot['duration']
    mode=recipe.get('mode')
    if mode=='character2d': return character_frame(local,duration,width,height,recipe)
    if mode=='director2d': return director_frame(local,duration,width,height,recipe)
    if mode=='camera2_5d': return camera_frame(local,duration,width,height,recipe)
    return svg_frame(local,duration,width,height,recipe)

def _svg_inside(svg, namespace=''):
    """Extract SVG content, scoping paint-server IDs before crossfading."""
    fragment=svg[svg.index('>')+1:svg.rindex('</svg>')]
    if namespace:
        # Keep each scene's paint-server identifiers isolated in one SVG.
        ids=re.findall(r'\bid=["\']([A-Za-z_][\w.-]*)["\']',fragment)
        for item in ids:
            fragment=re.sub(r'\bid=(["\'])'+re.escape(item)+r'\1',
                            'id="'+namespace+'_'+item+'"',fragment)
            fragment=fragment.replace('url(#'+item+')','url(#'+namespace+'_'+item+')')
    return fragment

def frame_at(shots,t,width=540,height=960):
    duration=validate_shots(shots)
    if t<0 or t>duration: raise ValueError('time outside storyboard')
    start=0.0
    for index,shot in enumerate(shots):
        end=start+shot['duration']
        if t<end or index==len(shots)-1:
            local=min(t-start,shot['duration'])
            svg=_render(shot,local,width,height)
            if index and shot.get('transition')=='fade' and local < 0.35:
                # True cross-dissolve: previous clip continues behind the next.
                previous=shots[index-1]
                old_plain=dict(previous)
                old_recipe=dict(previous.get('recipe',{}))
                old_recipe.pop('title',None)
                old_plain['recipe']=old_recipe
                old=_render(old_plain,previous['duration'],width,height)
                amount=max(0.0,min(local/0.35,1.0))
                return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
                        f'<g opacity="{1-amount:.5f}">{_svg_inside(old,"old")}</g>'
                        f'<g opacity="{amount:.5f}">{_svg_inside(svg,"new")}</g></svg>')
            return svg
        start=end
    raise RuntimeError('unreachable')
