"""`mcb selftest`: offline end-to-end check of the kit, needing nothing but Python + numpy + Pillow.

Builds the starter project on flat ground in Chinese and in English (design -> export -> verify -> materials ->
release), re-reads the schematic independently, writes the site into a vanilla save and reads it back with the
world reader, and parses F3 text. Prints one line per check; exit code 0 when everything passed.
"""
from __future__ import annotations
import shutil, tempfile, time, traceback
from pathlib import Path
from .util import log


def selftest(keep=False, shots=False):
    import importlib.util, sys
    missing = [m for m in ('numpy', 'PIL') if importlib.util.find_spec(m) is None]
    if missing:
        req = Path(__file__).resolve().parent.parent / 'requirements.txt'
        log(f'SELFTEST NOT RUN - missing {", ".join(missing)}: "{sys.executable}" -m pip install -r "{req}"')
        return False
    results = []
    tmp = Path(tempfile.mkdtemp(prefix='mcbuild-selftest-'))

    def check(name, fn):
        t0 = time.time()
        try:
            info = fn()
            results.append((name, True, info))
            log(f'[ok] {name}  {info or ""}  ({time.time() - t0:.1f}s)')
        except BaseException as e:                                   # noqa: BLE001 - report everything
            results.append((name, False, repr(e)))
            log(f'[FAIL] {name}: {e!r}')
            traceback.print_exc()

    def data():
        from .registry import parse, facts, display_name, set_version
        from .util import default_version
        set_version(default_version())
        st = parse('oak_stairs[facing=east,half=top]')
        f = facts(st)
        assert f.boxes and display_name('oak_stairs', 'en') == 'Oak Stairs' and display_name('oak_stairs', 'zh') != 'oak_stairs'
        return f'{default_version()} data, {st.key()}'
    check('bundled block data', data)

    def project(lang):
        from .scaffold import init_project
        from .project import Project
        from . import cli
        d = tmp / f'cottage-{lang}'
        init_project(d, name='Selftest' if lang == 'en' else '自检小屋', pid=f'Selftest{lang.upper()}', source='flat', lang=lang)
        for cmd in (['design'], ['export'], ['verify'], ['materials'], ['release']):
            cli.main(['-p', str(d)] + cmd)
        P = Project(d)
        from .util import read_json
        ver = read_json(P.art / 'verification.json')
        assert ver['status'] == 'PASS', ver.get('errors')
        rep = read_json(P.art / 'litematic-report.json')
        from .schematic import litematic_cells
        from .registry import AIR
        cells = {k: v for k, v in litematic_cells(P.release_dir / rep['file']).items() if v != AIR}
        assert len(cells) == rep['totalBlocks'], (len(cells), rep['totalBlocks'])
        guide = 'README.md' if lang == 'en' else '使用说明.md'
        assert (P.release_dir / guide).exists(), guide
        csvname = 'materials.csv' if lang == 'en' else '材料清单.csv'
        assert (P.release_dir / csvname).exists(), csvname
        if shots:
            cli.main(['-p', str(d), 'preview', '--shots'])
        return f'{len(cells)} blocks, verify PASS, {guide}'
    check('starter project (zh)', lambda: project('zh'))
    check('starter project (en)', lambda: project('en'))

    def world_roundtrip():
        from .terrain import make_flat, extract_anvil
        from .world import write_world
        from .registry import parse
        site = make_flat((0, 48, 0, 48, 96, 48), 63, water_y=None)
        site.IDS[70 - 48, 10, 20] = 0
        ids = dict(site._pal)
        ids[str(len(ids))] = parse('oak_log[axis=y]').nbt()
        site._pal = ids
        site.IDS[66 - 48, 5, 7] = len(ids) - 1
        write_world(tmp / 'world', site, None, 'selftest')
        back = extract_anvil(tmp / 'world', (0, 48, 0, 48, 96, 48))
        diff = sum(1 for y in range(50, 90) for z in range(0, 48, 3) for x in range(0, 48, 3)
                   if back.world(x, y, z) != site.world(x, y, z))
        assert diff == 0 and back.world(7, 66, 5).short == 'oak_log', diff
        return 'save written and read back identically'
    check('world writer + reader', world_roundtrip)

    def f3():
        from .camera import from_f3, points_in_polygon
        cam, f = from_f3('/execute in minecraft:overworld run tp @s 10.5 64 -3.5 450 30', 1920, 1080, 70)
        assert abs(cam.yaw - 90) < 1e-6 and abs(cam.eye[1] - 65.62) < 1e-6
        assert points_in_polygon([(0.5, 0.5), (2, 2)], [(0, 0), (1, 0), (1, 1), (0, 1)]).tolist() == [True, False]
        return 'F3+C text -> camera'
    check('F3 parsing', f3)

    ok = all(r[1] for r in results)
    log(('SELFTEST PASSED' if ok else 'SELFTEST FAILED') + f' - {sum(r[1] for r in results)}/{len(results)} checks; files: {tmp}')
    if not keep and ok:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok
