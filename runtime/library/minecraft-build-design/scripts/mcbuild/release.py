"""Collect the deliverables into release/ and write the player's guide (使用说明.md / README.md, project language)."""
from __future__ import annotations
import shutil, zipfile
from pathlib import Path
from .registry import version
from .i18n import t, direction
from .util import log, read_json


def guide(P, rep, ver, ig, files, removes=0):
    pc = P.cfg.get('preview', {})
    rc = P.cfg.get('release', {})
    mode = rep.get('mode', 'site')
    ox, oy, oz = rep['origin']
    sx, sy, sz = rep['enclosingSize']
    L = [f'# {P.name}', '']
    if pc.get('lead'):
        L += [pc['lead'], '']
    L += [f"## {t('rel.files')}", '']
    for f, what in files:
        L.append(f'- `{f}`: {what}' if P.lang != 'zh' else f'- `{f}`：{what}')
    L += ['', f"## {t('rel.place')}", '']
    if mode == 'site':
        L += ['- ' + t('rel.site1', x=ox, y=oy, z=oz), '- ' + t('rel.site2', sx=sx, sy=sy, sz=sz, n=len(rep['regions']))]
    else:
        front = direction(pc.get('front', 'south'))
        L += ['- ' + t('rel.portable1', sx=sx, sy=sy, sz=sz, front=front), '- ' + t('rel.portable2')]
    if removes:
        L += ['- ' + t('rel.paste_all', n=removes), '- ' + t('rel.survival_all')]
    else:
        L += ['- ' + t('rel.paste_nonair'), '- ' + t('rel.survival')]
    from .compat import is_older
    if is_older(rep.get('targetVersion'), version()):
        ren = ', '.join(f"{a.split(':')[1]} → {b.split(':')[1]}" for a, b in (rep.get('renamed') or {}).items())
        L += ['- ' + t('rel.version_target', t=rep['targetVersion'], dv=rep['dataVersion'], renamed=t('rel.renamed', list=ren) if ren else '')]
    else:
        L += ['- ' + t('rel.version_note', v=version())]
    if rc.get('notes'):
        L += ['', f"## {t('rel.notes')}", ''] + [f'- {n}' for n in rc['notes']]
    L += ['', f"## {t('rel.checks')}", '']
    if ver:
        f = ver.get('file', {})
        L.append('- ' + t('rel.chk_file', r=f.get('regions'), c=f.get('cellsDecoded'), s=f.get('paletteStatesValidated'), v=version(),
                          te=f.get('tileEntities'), rs='' if f.get('regions') == 1 else 's', tes='y' if f.get('tileEntities') == 1 else 'ies'))
        L.append('- ' + t('rel.chk_rules', n=ver.get('rules', {}).get('problems', '?')))
        sp = ver.get('spawnProofing')
        if sp:
            L.append('- ' + t('rel.chk_spawn', n=sp['spawnableSurfaces'], d=sp['darkSurfaces']))
        if ver.get('walk'):
            tg = ver['walk']['targets']
            L.append('- ' + t('rel.chk_walk', a=sum(tg.values()), b=len(tg)))
        for w in ver.get('warnings', []):
            L.append('- ' + t('rel.chk_warn', check=w['check'], count=w.get('count', ''), blocks=w.get('blocks', '')))
    if ig:
        names = {'none': t('rel.mode_none'), 'with_non_air': 'With non-air', 'all': 'All'}
        parts = []
        for k, v in ig.items():
            if k.startswith('paste_'):
                m = k[k.find('(') + 1:-1] if '(' in k else k[6:]
                parts.append(t('rel.mismatch', mode=names.get(m, m), n=v['cellsMismatched']))
        L.append('- ' + t('rel.chk_ingame', v=version(), parts=t('rel.join').join(parts)))
    return '\n'.join(L) + '\n'


def clearing_count(P):
    """Design AIR cells that remove a non-air terrain block (trees, cut ground). Such builds must be pasted with
    Litematica's `All` mode: `With non-air` skips the schematic's air cells and leaves those blocks in place."""
    from .registry import AIR
    B = P.design()
    if B.site is None:
        return 0
    return sum(1 for p, st in B.cells.items() if st == AIR and B.world(p) != AIR)


def release(P):
    rd = P.release_dir
    rd.mkdir(exist_ok=True)
    rep = read_json(P.art / 'litematic-report.json')
    if rep is None:
        raise SystemExit('run `mcb export` first')
    ver = read_json(P.art / 'verification.json')
    ig = read_json(P.art / 'ingame' / 'ingame-report.json')
    files = [(rep['file'], t('rel.f_litematic', v=version()))]
    schem = (rd / rep['file']).with_suffix('.schem')
    if schem.exists():
        files.append((schem.name, t('rel.f_schem')))
    prev = P.art / 'preview' / 'index.html'
    if prev.exists():
        name = t('file.preview', name=P.name)
        shutil.copy2(prev, rd / name)
        files.append((name, t('rel.f_preview')))
    if (P.art / 'materials.csv').exists():
        name = t('file.materials')
        shutil.copy2(P.art / 'materials.csv', rd / name)
        files.append((name, t('rel.f_materials')))
    shots = sorted((P.art / 'ingame').glob('*.png')) if ig else sorted((P.art / 'shots').glob('*.png'))
    if shots:
        sd = rd / t('file.shots')
        if sd.exists():
            shutil.rmtree(sd)
        sd.mkdir()
        for s in shots:
            shutil.copy2(s, sd / s.name)
        files.append((sd.name + '/', t('rel.f_shots_ingame' if ig else 'rel.f_shots_preview', n=len(shots))))
    for extra in sorted(rd.glob('*.zip')) + sorted(rd.glob('*.mp4')):
        if extra.suffix == '.zip' and not extra.stem.endswith(('展示存档', 'showcase-world')):
            continue
        files.append((extra.name, t('rel.f_showcase') if extra.suffix == '.zip' else t('rel.f_video')))
    removes = clearing_count(P) if rep.get('mode', 'site') == 'site' else 0
    gname = t('file.guide')
    (rd / gname).write_text(guide(P, rep, ver, ig, files, removes), encoding='utf-8')
    if P.cfg.get('release', {}).get('zip', False):
        zp = rd.parent / t('file.bundle', id=P.id)
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in rd.rglob('*'):
                if f.is_file():
                    z.write(f, f.relative_to(rd))
        log('ZIP', zp)
    log('RELEASE', rd, [f for f, _ in files] + [gname])
    return rd
