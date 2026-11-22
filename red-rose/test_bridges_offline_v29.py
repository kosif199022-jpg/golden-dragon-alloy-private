"""Offline exercise of bridges_v28 (app.bridge) without starting any program.

shutil.which and subprocess.run inside bridges_v28 are replaced by fakes, so
Blender, FFmpeg, piper and espeak are never launched; generated scripts and
project files are checked as text (Python parsed with ast, XML with ElementTree,
JSON with json).
"""
import ast
import json
import os
import re
import subprocess
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import bridges_v28 as B

AR = 'الوردة الحمراء'


def _timeline(**kw):
    tl = {'width': 1080, 'height': 1920, 'fps': 24, 'duration': 4.0, 'background': '#5a1020',
          'layers': [
              {'module': 'typemotion', 'op': 'kinetic_text', 'z': 2, 'start': 0.0, 'end': 2.4,
               'params': {'text': AR, 'size': 120, 'color': '#ffffff'}},
              {'module': 'graphics', 'op': 'route_map', 'z': 1, 'start': 2.0, 'end': 4.0,
               'params': {'color': '#ffd166'}},
              {'module': 'typemotion', 'op': 'lower_third', 'z': 3, 'start': 1.0, 'end': 3.0,
               'params': {'text': 'Hello "world" </text>', 'color': 'red'}},
          ],
          'audio': [{'path': 'C:/not-here/voice.wav', 'start': 0.5, 'role': 'voice'}]}
    tl.update(kw)
    return tl


def _no_program(*a, **k):
    raise AssertionError('an external program was started in an offline test')


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wd = Path(self.tmp.name).resolve()
        p = mock.patch.object(B.subprocess, 'run', _no_program)
        p.start()
        self.addCleanup(p.stop)

    def which(self, mapping):
        p = mock.patch.object(B.shutil, 'which', lambda n: mapping.get(n))
        p.start()
        self.addCleanup(p.stop)


class TestInterface(BridgeCase):
    def test_tables(self):
        self.assertEqual(set(B.OPS), set(B.EFFECTS))
        for op in ('blender_render', 'tts_local', 'nle_export'):
            self.assertEqual(B.EFFECTS[op], 'write')
        for op in ('detect', 'blender_script', 'ae_jsx', 'remotion_project'):
            self.assertEqual(B.EFFECTS[op], 'read')
        with self.assertRaises(ValueError):
            B.run('nope', {})
        with self.assertRaises(ValueError):
            B.run('detect', [])
        with self.assertRaises(ValueError):
            B.run('detect', {'zzz': 1})

    def test_exe_allow_list(self):
        with self.assertRaises(ValueError):
            B._exe('cmd')
        self.which({})
        self.assertEqual(B._exe('blender'), (None, 'not_installed'))


class TestDetect(BridgeCase):
    def test_detect_statuses_with_fake_version_run(self):
        exe = 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'
        self.which({'blender': exe, 'ffmpeg': 'C:/fake/ffmpeg.bat' if os.name == 'nt' else None})
        calls = []

        def fake_run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, b'Blender 9.9.9\nbuild date x\n', b'')

        with mock.patch.object(B.subprocess, 'run', fake_run):
            r = B.run('detect', {'programs': ['blender', 'ffmpeg', 'piper']})['result']
        self.assertEqual(r['programs']['blender']['status'], 'installed')
        self.assertEqual(r['programs']['blender']['version'], 'Blender 9.9.9 | build date x')
        self.assertEqual(r['programs']['piper']['status'], 'not_installed')
        if os.name == 'nt':
            self.assertEqual(r['programs']['ffmpeg']['status'], 'launcher_refused')
            self.assertIn('never started', r['programs']['ffmpeg']['note'])
        self.assertEqual(r['installed'], ['blender'])
        self.assertEqual(calls, [[str(Path(exe)), '--version']])     # only the version flag

    def test_detect_without_versions_runs_nothing(self):
        self.which({'blender': 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'})
        r = B.run('detect', {'programs': ['blender'], 'versions': False})['result']
        self.assertEqual(r['programs']['blender']['status'], 'installed')
        self.assertNotIn('version', r['programs']['blender'])
        for bad in ({'programs': []}, {'programs': ['bash']}, {'timeout_s': 0}, {'versions': 'no'}):
            with self.assertRaises(ValueError):
                B.run('detect', bad)

    def test_version_failure_is_reported(self):
        self.which({'blender': 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'})

        def boom(argv, **kw):
            raise subprocess.TimeoutExpired(argv, 1)

        with mock.patch.object(B.subprocess, 'run', boom):
            r = B.run('detect', {'programs': ['blender']})['result']
        self.assertIn('timed out', r['programs']['blender']['version_error'])


class TestBlenderScript(BridgeCase):
    def config_of(self, script):
        tree = ast.parse(script)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'CONFIG'):
                return json.loads(ast.literal_eval(node.value.args[0]))
        self.fail('CONFIG assignment not found')

    def test_default_scene_script_parses(self):
        r = B.run('blender_script', {})['result']
        cfg = self.config_of(r['script'])
        self.assertEqual([p['name'] for p in cfg['primitives']], ['ground', 'block', 'ball'])
        self.assertEqual(r['frames'], 48)
        self.assertFalse(r['executed'])
        self.assertEqual(r['run_args'][:5], ['blender', '-b', '--factory-startup', '--python-exit-code', '1'])
        self.assertTrue(any('demo scene' in n for n in r['notes']))

    def test_owner_text_never_becomes_code(self):
        evil = "x'); import os; os.system('calc') #"
        r = B.run('blender_script', {'primitives': [{'type': 'cube', 'name': evil}, {'type': 'torus', 'name': AR}],
                                     'engine': 'eevee', 'output': 'mp4', 'output_dir': str(self.wd)})['result']
        script = r['script']
        cfg = self.config_of(script)
        self.assertEqual(cfg['primitives'][0]['name'], evil)
        self.assertEqual(cfg['primitives'][1]['name'], AR)
        self.assertEqual(cfg['output_dir'], str(self.wd))
        self.assertNotIn('calc', script.split('CONFIG = json.loads(')[0])
        self.assertTrue(script.isascii())
        self.assertIn('mp4_note', r)
        self.assertEqual(r['engine'], 'eevee')

    def test_gltf_inputs(self):
        gltf = {'asset': {'version': '2.0'}, 'buffers': [{'uri': 'data:application/octet-stream;base64,AAAA',
                                                          'byteLength': 3}]}
        cfg = self.config_of(B.run('blender_script', {'gltf': gltf})['result']['script'])
        self.assertEqual(json.loads(cfg['gltf_text'])['asset']['version'], '2.0')
        self.assertEqual(cfg['primitives'], [])
        bad = [{'gltf': {'asset': {'version': '1.0'}}},
               {'gltf': {'asset': {'version': '2.0'}, 'buffers': [{'uri': 'scene.bin'}]}},
               {'gltf': 'not json'},
               {'gltf': gltf, 'gltf_path': 'x.gltf'},
               {'gltf_path': str(self.wd / 'missing.gltf')}]
        for params in bad:
            with self.assertRaises(ValueError):
                B.run('blender_script', params)
        path = self.wd / 'scene.gltf'
        path.write_text(json.dumps(gltf), encoding='utf-8')
        cfg = self.config_of(B.run('blender_script', {'gltf_path': str(path)})['result']['script'])
        self.assertEqual(cfg['gltf_path'], str(path))

    def test_validation(self):
        bad = [{'width': 1281}, {'engine': 'octane'}, {'frame_start': 1, 'frame_end': 5000},
               {'primitives': [{'type': 'teapot'}]}, {'primitives': [{'type': 'cube', 'colour': 1}]},
               {'lights': []}, {'camera': {'turns': 0}}, {'camera': {'direction': [0, 0, 0]}},
               {'samples': 0}, {'cycles_device': 'tpu'}, {'output_dir': 'https://example.com/x'},
               {'output_dir': '\\\\server\\share'}, {'zzz': 1}]
        for params in bad:
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    B.run('blender_script', params)


class TestBlenderRender(BridgeCase):
    def test_unapproved_call_raises_permission_error_and_writes_nothing(self):
        with self.assertRaises(PermissionError):
            B.run('blender_render', {'work_dir': str(self.wd)})
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_not_installed(self):
        self.which({})
        r = B.run('blender_render', {'work_dir': str(self.wd), 'approve_write': True})['result']
        self.assertEqual(r['status'], 'not_installed')
        self.assertEqual(r['programs'], {'blender': 'not_installed'})
        self.assertEqual(list(self.wd.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'launcher refusal is Windows-specific')
    def test_launcher_refused(self):
        self.which({'blender': 'C:/fake/blender.cmd'})
        r = B.run('blender_render', {'work_dir': str(self.wd), 'approve_write': True})['result']
        self.assertEqual(r['status'], 'not_installed')
        self.assertEqual(r['programs'], {'blender': 'launcher_refused'})

    def test_mp4_needs_ffmpeg(self):
        self.which({'blender': 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'})
        r = B.run('blender_render', {'work_dir': str(self.wd), 'approve_write': True,
                                     'output': 'mp4'})['result']
        self.assertEqual(r['status'], 'not_installed')
        self.assertEqual(r['programs']['ffmpeg'], 'not_installed')

    def test_never_overwrites(self):
        (self.wd / 'shot.py').write_text('keep', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            B.run('blender_render', {'work_dir': str(self.wd), 'basename': 'shot', 'approve_write': True})
        self.assertEqual((self.wd / 'shot.py').read_text(encoding='utf-8'), 'keep')
        for bad in ('../x', 'a/b', 'CON', 'x.', 'a..b', ''):
            with self.assertRaises(ValueError):
                B.run('blender_render', {'work_dir': str(self.wd), 'basename': bad, 'approve_write': True})

    def test_fake_blender_run_png(self):
        exe = 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'
        self.which({'blender': exe})
        seen = []

        def fake_run(argv, **kw):
            seen.append((argv, kw))
            script = Path(argv[argv.index('--python') + 1])
            text = script.read_text(encoding='utf-8')
            out_dir = Path(json.loads(ast.literal_eval(re.search(r'CONFIG = json.loads\((.*)\)\n', text)
                                                       .group(1)))['output_dir'])
            for f in range(1, 4):
                (out_dir / f'frame_{f:04d}.png').write_bytes(b'\x89PNG\r\n\x1a\n')
            summary = 'RED_ROSE_RESULT ' + json.dumps({'frames_written': 3})
            return subprocess.CompletedProcess(argv, 0, ('log\n' + summary + '\n').encode(), b'')

        with mock.patch.object(B.subprocess, 'run', fake_run):
            r = B.run('blender_render', {'work_dir': str(self.wd), 'approve_write': True,
                                         'frame_start': 1, 'frame_end': 3})['result']
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(r['frames_written'], 3)
        self.assertEqual(r['blender_summary'], {'frames_written': 3})
        argv, kw = seen[0]
        self.assertIsInstance(argv, list)
        self.assertNotIn('shell', kw)
        self.assertEqual(kw['timeout'], 900)
        self.assertTrue((self.wd / 'red_rose_blender.py').is_file())

    def test_fake_blender_short_frames_is_failed(self):
        self.which({'blender': 'C:/fake/blender.exe' if os.name == 'nt' else '/fake/blender'})

        def fake_run(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, b'', b'Error: boom')

        with mock.patch.object(B.subprocess, 'run', fake_run):
            r = B.run('blender_render', {'work_dir': str(self.wd), 'approve_write': True,
                                         'frame_end': 2})['result']
        self.assertEqual(r['status'], 'failed')
        self.assertIn('exited with code 1', r['error'])


class TestAeJsx(BridgeCase):
    def cfg_of(self, jsx):
        m = re.search(r'var CFG = (\{.*?\});\n', jsx)
        return json.loads(m.group(1))

    def test_jsx_text(self):
        r = B.run('ae_jsx', {'timeline': _timeline(), 'comp_name': 'Rose "comp"',
                             'keyframes': {'0': {'opacity': [[0, 0], [1.0, 1]], 'position': [[0, [540, 960]]]}}})['result']
        jsx = r['jsx']
        self.assertTrue(jsx.isascii())
        cfg = self.cfg_of(jsx)
        self.assertEqual(cfg['name'], 'Rose "comp"')
        self.assertEqual([l['kind'] for l in cfg['layers']], ['placeholder', 'text', 'text'])  # sorted by z
        ar = cfg['layers'][1]
        self.assertEqual(ar['text'], AR)
        self.assertTrue(ar['rtl'])
        self.assertEqual(ar['keyframes']['opacity'], [[0.0, 0.0], [1.0, 1.0]])
        self.assertFalse(cfg['layers'][2]['rtl'])
        self.assertEqual(cfg['layers'][2]['color'], [1.0, 1.0, 1.0])     # bad colour -> default
        self.assertEqual(r['text_layers'], 2)
        self.assertEqual(r['placeholder_layers'], 1)
        self.assertFalse(r['executed'])
        self.assertTrue(any('placeholder' in w for w in r['warnings']))
        self.assertTrue(any('not "#rrggbb"' in w for w in r['warnings']))
        self.assertTrue(any('not found' in w for w in r['warnings']))
        self.assertEqual(jsx.count('__RR_CFG__'), 0)

    def test_timeline_validation(self):
        bad = [None, {}, _timeline(width=1081), _timeline(duration=0), _timeline(extra=1),
               _timeline(layers=[{'module': 'x', 'start': 2, 'end': 1}]),
               _timeline(audio=[{'path': 'https://example.com/a.wav'}])]
        for tl in bad:
            with self.assertRaises(ValueError):
                B.run('ae_jsx', {'timeline': tl})
        for kf in ({'5': {'opacity': [[0, 1]]}}, {'0': {'rotation': [[0, 1]]}},
                   {'0': {'opacity': [[1, 1], [0.5, 1]]}}, {'0': {'opacity': [[0, 2]]}}):
            with self.assertRaises(ValueError):
                B.run('ae_jsx', {'timeline': _timeline(), 'keyframes': kf})

    def test_timeline_as_json_text(self):
        r = B.run('ae_jsx', {'timeline': json.dumps(_timeline(), ensure_ascii=False)})['result']
        self.assertEqual(r['text_layers'], 2)


class TestNleExport(BridgeCase):
    CLIPS = [{'path': 'C:/v/a.mp4', 'src_in': 1.0, 'src_out': 3.0},
             {'path': 'C:/v/b.mp4', 'src_out': 2.0, 'track': 'B', 'name': 'B roll'},
             {'path': 'C:/v/m.wav', 'src_out': 4.0, 'track': 'A2', 'record_in': 0}]

    def test_edl_and_fcpxml_text(self):
        r = B.run('nle_export', {'clips': self.CLIPS, 'fps': 25, 'record_start_hour': 1})['result']
        edl = r['edl'].splitlines()
        self.assertEqual(edl[0], 'TITLE: Red Rose')
        self.assertEqual(edl[1], 'FCM: NON-DROP FRAME')
        events = [l for l in edl if re.match(r'^\d{3}  ', l)]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].split()[-4:], ['00:00:01:00', '00:00:03:00', '01:00:00:00', '01:00:02:00'])
        self.assertEqual(events[2].split()[-2:], ['01:00:02:00', '01:00:04:00'])   # B after a on V
        self.assertIn('* FROM CLIP NAME: B roll', edl)
        root = ET.fromstring(r['fcpxml'].encode('utf-8'))
        self.assertEqual(root.tag, 'fcpxml')
        self.assertEqual(root.get('version'), '1.9')
        clips = root.findall('.//asset-clip')
        self.assertEqual(len(clips), 3)
        self.assertEqual({c.get('srcEnable') for c in clips}, {'video', 'all', 'audio'})
        lanes = {c.get('name'): int(c.get('lane')) for c in clips}
        self.assertLess(lanes['m'], 0)
        self.assertEqual(root.find('.//format').get('frameDuration'), '1/25s')
        self.assertEqual(r['files'], [])

    def test_timeline_titles_in_fcpxml(self):
        r = B.run('nle_export', {'timeline': _timeline(), 'format': 'fcpxml'})['result']
        self.assertIsNone(r['edl'])
        root = ET.fromstring(r['fcpxml'].encode('utf-8'))
        texts = [t.text for t in root.findall('.//title/text/text-style')]
        self.assertEqual(texts, [AR, 'Hello "world" </text>'])
        self.assertEqual(r['titles'], 2)
        self.assertEqual(r['events'], 1)
        with self.assertRaises(ValueError):
            B.run('nle_export', {'timeline': _timeline(), 'fps': 25})
        with self.assertRaises(ValueError):
            B.run('nle_export', {'timeline': _timeline(fps=120)})
        with self.assertRaises(ValueError):
            B.run('nle_export', {'timeline': _timeline(layers=[], audio=[])})

    def test_validation(self):
        bad = [{}, {'clips': self.CLIPS, 'timeline': _timeline()}, {'clips': []},
               {'clips': [{'path': 'C:/v/a.mp4', 'src_in': 2, 'src_out': 2}]},
               {'clips': [{'path': 'C:/v/a.mp4', 'src_out': 2, 'track': 'Z'}]},
               {'clips': self.CLIPS, 'format': 'aaf'}, {'clips': self.CLIPS, 'fps': 61},
               {'clips': self.CLIPS, 'keyframes': {}}]
        for params in bad:
            with self.assertRaises(ValueError):
                B.run('nle_export', params)

    def test_writes_need_approval_and_never_overwrite(self):
        params = {'clips': self.CLIPS, 'work_dir': str(self.wd), 'basename': 'cut'}
        with self.assertRaises(PermissionError):
            B.run('nle_export', params)
        self.assertEqual(list(self.wd.iterdir()), [])
        r = B.run('nle_export', dict(params, approve_write=True))['result']
        names = sorted(Path(f['path']).name for f in r['files'])
        self.assertEqual(names, ['cut.edl', 'cut.fcpxml'])
        self.assertEqual((self.wd / 'cut.edl').read_text(encoding='utf-8'), r['edl'])
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            B.run('nle_export', dict(params, approve_write=True))

    def test_timecode_helpers(self):
        self.assertEqual(B._tc(25 * 3661 + 7, 25), '01:01:01:07')
        self.assertEqual(B._ftime(0, 24), '0s')
        self.assertEqual(B._ftime(48, 24), '2s')
        self.assertEqual(B._ftime(1, 30), '1/30s')


class TestRemotion(BridgeCase):
    def test_file_map(self):
        r = B.run('remotion_project', {'timeline': _timeline(), 'project_name': 'rose-test',
                                       'composition_id': 'Rose1'})['result']
        files = r['files']
        self.assertEqual(sorted(files), ['package.json', 'src/Main.tsx', 'src/Root.tsx', 'src/index.ts',
                                         'src/timeline.ts', 'tsconfig.json'])
        pkg = json.loads(files['package.json'])
        self.assertEqual(pkg['name'], 'rose-test')
        self.assertIn('Rose1', pkg['scripts']['render'])
        json.loads(files['tsconfig.json'])
        data = json.loads(re.search(r'export const TIMELINE: Timeline = (\{.*\});', files['src/timeline.ts'])
                          .group(1))
        self.assertEqual(data['id'], 'Rose1')
        self.assertEqual(data['frames'], 96)
        self.assertEqual(data['layers'][0]['text'], AR)
        self.assertTrue(data['layers'][0]['rtl'])
        self.assertEqual(data['audio'][0]['file'], 'voice.wav')
        self.assertEqual(r['public_copies'][0]['to'], 'public/voice.wav')
        self.assertFalse(r['installed'])
        self.assertFalse(r['written'])
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_validation(self):
        for params in ({}, {'timeline': _timeline(), 'project_name': 'Bad Name'},
                       {'timeline': _timeline(), 'composition_id': 'a b'}):
            with self.assertRaises(ValueError):
                B.run('remotion_project', params)


class TestTts(BridgeCase):
    def test_not_installed(self):
        self.which({})
        r = B.run('tts_local', {'text': AR, 'work_dir': str(self.wd), 'approve_write': True})['result']
        self.assertEqual(r['status'], 'not_installed')
        self.assertEqual(set(r['programs']), {'espeak-ng', 'espeak'})
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_validation_and_approval(self):
        with self.assertRaises(PermissionError):
            B.run('tts_local', {'text': AR, 'work_dir': str(self.wd)})
        bad = [{'work_dir': str(self.wd)}, {'text': '   ', 'work_dir': str(self.wd)},
               {'text': 'x' * (B.MAX_TTS_CHARS + 1), 'work_dir': str(self.wd)},
               {'text': AR, 'engine': 'piper', 'work_dir': str(self.wd)},
               {'text': AR, 'voice': 'ar; rm', 'work_dir': str(self.wd)},
               {'text': AR, 'rate': 10, 'work_dir': str(self.wd)},
               {'text': AR, 'engine': 'say', 'work_dir': str(self.wd)}]
        for params in bad:
            with self.assertRaises(ValueError):
                B.run('tts_local', params)

    def test_fake_espeak_writes_owner_text_wav(self):
        exe = 'C:/fake/espeak-ng.exe' if os.name == 'nt' else '/fake/espeak-ng'
        self.which({'espeak-ng': exe})
        seen = {}

        def fake_run(argv, **kw):
            seen['argv'], seen['input'] = argv, kw.get('input')
            out = argv[argv.index('-w') + 1]
            with wave.open(out, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b'\x00\x00' * 2205)
            return subprocess.CompletedProcess(argv, 0, b'', b'')

        with mock.patch.object(B.subprocess, 'run', fake_run):
            r = B.run('tts_local', {'text': AR + '\x07', 'work_dir': str(self.wd), 'approve_write': True,
                                    'basename': 'voice'})['result']
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(seen['input'], AR.encode('utf-8'))        # control char dropped, text unchanged
        self.assertEqual(seen['argv'][1:3], ['-v', 'ar'])
        self.assertEqual(r['files'][0]['duration'], 0.1)
        self.assertEqual(sorted(p.name for p in self.wd.iterdir()), ['voice.wav'])   # temp removed

    def test_fake_engine_without_audio_is_failed(self):
        self.which({'espeak-ng': 'C:/fake/espeak-ng.exe' if os.name == 'nt' else '/fake/espeak-ng'})
        with mock.patch.object(B.subprocess, 'run',
                               lambda argv, **kw: subprocess.CompletedProcess(argv, 0, b'', b'')):
            r = B.run('tts_local', {'text': 'hi', 'work_dir': str(self.wd), 'approve_write': True})['result']
        self.assertEqual(r['status'], 'failed')
        self.assertEqual(list(self.wd.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
