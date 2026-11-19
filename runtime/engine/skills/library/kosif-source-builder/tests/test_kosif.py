import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import kosif_studio as studio
import kosif_registry as registry
class TestKosif(unittest.TestCase):
    def test_manifest(self):
        self.assertGreaterEqual(len(registry.repositories(ROOT)),35)
    def test_groups(self):
        self.assertTrue(all(x['group']=='own-video' for x in registry.selected(ROOT,'own-video')))
    def test_owned(self):
        self.assertIn('kosif-studio',[x['name'] for x in registry.selected(ROOT,'own')])
    def test_storyboard(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'f.json';studio.storyboard(p,'Unit test',9,3)
            data=json.loads(p.read_text());self.assertEqual(len(data['shots']),3)
            self.assertEqual(sum(x['duration'] for x in data['shots']),9)
    def test_invalid_shots(self):
        with self.assertRaises(ValueError):studio.storyboard(Path('unused'),'',10,0)
    def test_color(self):
        self.assertEqual(studio.valid_color('#abcdef'),'0xabcdef')
    def test_invalid_color(self):
        with self.assertRaises(ValueError):studio.valid_color('red; rm -rf /')
    def test_catalog_paths(self):
        for item in registry.repositories(ROOT):self.assertTrue(item['clone'].startswith('https://github.com/'))
if __name__=='__main__':unittest.main()
