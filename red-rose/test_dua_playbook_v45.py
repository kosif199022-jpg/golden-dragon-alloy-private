"""V45: the dua-reel playbook, presets, analyzer and lyric-motion engine ship and are well formed."""
import json, py_compile, shutil, subprocess, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent


class DuaPlaybook(unittest.TestCase):
    def test_presets(self):
        P = json.loads((ROOT / 'agent' / 'dua_style' / 'presets.json').read_text(encoding='utf-8'))
        for name in ('oaun', 'dxhmen'):
            st = P['styles'][name]
            for key in ('shots', 'shot_len_s', 'words_per_s', 'deliver_lufs', 'layout', 'footage', 'hashtags_top', 'card'):
                self.assertIn(key, st, f'{name}.{key}')
            self.assertTrue((ROOT / st['card']).is_file(), st['card'])
        self.assertAlmostEqual(sum(P['styles']['dxhmen']['transitions'].values()), 1.0, places=2)

    def test_playbook_links(self):
        text = (ROOT / 'references' / 'DUA_REELS_PLAYBOOK.md').read_text(encoding='utf-8')
        for rel in ('agent/dua_style/presets.json', 'references/STYLE_OAUN.md', 'references/STYLE_DXHMEN.md',
                    'agent/pins_catalog.csv', 'agent/dua_audio/dua_audio_catalog.csv', 'agent/reel_analyzer/analyze.py',
                    'agent/lyric_motion/README.md', 'references/SOCIAL_FETCH.md'):
            self.assertIn(rel.split('/')[-1], text)
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertIn('DUA_REELS_PLAYBOOK', (ROOT / 'SKILL.md').read_text(encoding='utf-8'))

    def test_tools_compile(self):
        for rel in ('agent/reel_analyzer/analyze.py', 'agent/reel_analyzer/label_sheets.py', 'agent/lyric_motion/build.py',
                    'agent/dua_audio/dua_audio.py', 'agent/dua_audio/fetch_audio.py'):
            py_compile.compile(str(ROOT / rel), doraise=True)
        json.loads((ROOT / 'agent' / 'lyric_motion' / 'song.example.json').read_text(encoding='utf-8'))
        if shutil.which('node'):
            r = subprocess.run(['node', '--check', str(ROOT / 'agent' / 'lyric_motion' / 'web' / 'main.js')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_engine_is_generic(self):
        js = (ROOT / 'agent' / 'lyric_motion' / 'web' / 'main.js').read_text(encoding='utf-8')
        self.assertNotIn('ELISSA', js)
        self.assertIn('CFG.title', js)


if __name__ == '__main__':
    unittest.main()


class CloudRender(unittest.TestCase):
    def test_cloud_render_is_the_default(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('Higgsfield cloud sandbox', skill)
        self.assertIn('CLOUD_RENDER.md', skill)
        doc = (ROOT / 'references' / 'CLOUD_RENDER.md').read_text(encoding='utf-8')
        for word in ('size: "xl"', '15 min', 'render_job.sh', 'media_confirm'):
            self.assertIn(word, doc)
        self.assertTrue((ROOT / 'agent' / 'cloud_render' / 'render_job.sh').is_file())
        if shutil.which('bash'):
            r = subprocess.run(['bash', '-n', str(ROOT / 'agent' / 'cloud_render' / 'render_job.sh')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
