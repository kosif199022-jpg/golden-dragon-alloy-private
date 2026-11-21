"""Deterministic SVG scene animation. Uses ffmpeg for MP4 when available."""
import html, json, math, shutil, subprocess
from pathlib import Path

PALETTE={'background':'#101827','foreground':'#f9d65c','accent':'#e35b79'}

def svg_frame(t, duration=10, width=540, height=960, recipe=None):
    if not 0 <= t <= duration or duration <= 0 or width <= 0 or height <= 0:
        raise ValueError('Invalid timeline or dimensions')
    recipe=recipe or {}
    colors={k:recipe.get(k,v) for k,v in PALETTE.items()}
    if any(not isinstance(v,str) or len(v)!=7 or not v.startswith('#') or any(c not in '0123456789abcdefABCDEF' for c in v[1:]) for v in colors.values()):
        raise ValueError('Colors must be #RRGGBB')
    phase=t/duration
    x=width*(.18+.64*phase)
    y=height*(.55-.12*math.sin(phase*math.pi*2))
    radius=min(width,height)*(.09+.015*math.sin(phase*math.pi*4))
    title=html.escape(str(recipe.get('title','RED ROSE')))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="100%" height="100%" fill="{colors["background"]}"/>'
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}" fill="{colors["accent"]}"/>'
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius*.44:.3f}" fill="{colors["foreground"]}"/>'
            f'<text x="{width/2}" y="{height*.2}" text-anchor="middle" font-size="{width*.07:.1f}" fill="{colors["foreground"]}">{title}</text></svg>')

def render(output, duration=10, fps=24, width=540, height=960, recipe=None, mp4=False):
    if not 0 < duration <= 600 or not 1 <= fps <= 120 or width < 16 or height < 16:
        raise ValueError('Invalid render settings')
    out=Path(output).resolve()
    out.mkdir(parents=True,exist_ok=True)
    count=round(duration*fps)
    for i in range(count):
        (out/f'frame_{i:05d}.svg').write_text(svg_frame(i/fps,duration,width,height,recipe),encoding='utf-8')
    manifest={'frames':count,'fps':fps,'duration':duration,'width':width,'height':height,'format':'svg','mp4':None}
    if mp4:
        # ffmpeg cannot ingest SVG frames directly on every build; cairosvg is an optional rasterizer.
        try:
            import cairosvg
        except ImportError as exc:
            raise RuntimeError('MP4 export requires cairosvg (pip install cairosvg) and ffmpeg') from exc
        if not shutil.which('ffmpeg'):
            raise RuntimeError('MP4 export requires ffmpeg')
        for i in range(count):
            cairosvg.svg2png(url=str(out/f'frame_{i:05d}.svg'),write_to=str(out/f'frame_{i:05d}.png'))
        target=out/'video.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(out/'frame_%05d.png'),'-c:v','libx264','-pix_fmt','yuv420p',str(target)],check=True)
        manifest['mp4']=str(target)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest
