"""Start a Maven 3D project.

  python new.py <folder> [--lang en|ar] [--from dragons-en|door-ar|blank]

Copies the engine (core, kits, three.js, fonts) into <folder>/web, plus story.js, script.txt, config.json, cues.json.
--from copies a finished example to edit; blank (default) gives the commented template.
"""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
args = sys.argv[1:]
if not args: sys.exit(__doc__)
proj = Path(args[0]).resolve(); lang = args[args.index('--lang') + 1] if '--lang' in args else 'en'
src = args[args.index('--from') + 1] if '--from' in args else 'blank'
if (proj / 'web').exists(): sys.exit(f'{proj} already has a web/ folder; pick a new folder')
proj.mkdir(parents=True, exist_ok=True)
shutil.copytree(HERE / 'engine', proj / 'web', ignore=shutil.ignore_patterns('gallery.js'))
shutil.copy(HERE / 'engine' / 'gallery.js', proj / 'web' / 'gallery.js')
if src == 'blank':
    t = HERE / 'templates'
    shutil.copy(t / 'story.js', proj / 'web' / 'story.js')
    shutil.copy(t / f'script.{lang}.txt', proj / 'script.txt')
    shutil.copy(t / 'cues.json', proj / 'cues.json')
    cfg = json.loads((t / f'config.{lang}.json').read_text(encoding='utf-8'))
else:
    e = HERE / 'examples' / src
    shutil.copy(e / 'story.js', proj / 'web' / 'story.js')
    for f in ('script.txt', 'cues.json'): shutil.copy(e / f, proj / f)
    if (e / 'sfx').exists(): shutil.copytree(e / 'sfx', proj / 'sfx')
    cfg = json.loads((e / 'config.json').read_text(encoding='utf-8'))
cfg['name'] = proj.name
(proj / 'config.json').write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding='utf-8')
(proj / 'web' / 'config.json').write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'''new Maven 3D project: {proj}
  1. write the script        {proj / "script.txt"}
  2. voice + word timings    python "{HERE / "scripts" / "voice.py"}" "{proj}"
  3. write the shots         {proj / "web" / "story.js"}
  4. check shots             python "{HERE / "scripts" / "build.py"}" "{proj}" shots
  5. sound cues              {proj / "cues.json"}
  6. render + mix + master   python "{HERE / "scripts" / "build.py"}" "{proj}" all''')
