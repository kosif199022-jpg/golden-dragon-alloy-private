"""W10: the skill text, the package and install/pack gates.

Checks the SKILL text (the draft until it is installed as SKILL.md), the README
top block draft, the packing rules, and the approval gates of pack and
install-skill. Nothing here opens ~/.red-rose or the owner's database: every
command runs with RED_ROSE_DB in a temp folder.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DRAFTS = ROOT / 'drafts'
SKILL_DRAFT = DRAFTS / 'SKILL.draft.md'
README_DRAFT = DRAFTS / 'README_TOP.draft.md'
ALLOWED_KEYS = {'name', 'description', 'license', 'compatibility', 'metadata'}
TRIGGERS = ['الوردة', 'الوردة الحمراء', 'مونتاج', 'ريل', 'ريلز', 'قص فيديو', 'كابشن', 'عنوان متحرك',
            'موشن', 'تحليل لقطات', 'ضبط الصوت', 'تسوية بنك', 'مطابقة كشف حساب', 'Red Rose', 'reel',
            'captions', 'kinetic title', 'shot report', 'loudness', 'bank reconciliation']


def skill_target():
    """The installed SKILL.md when it equals the draft, otherwise the draft."""
    live = ROOT / 'SKILL.md'
    if live.is_file() and hashlib.sha256(live.read_bytes()).hexdigest() == \
            hashlib.sha256(SKILL_DRAFT.read_bytes()).hexdigest():
        return live
    return SKILL_DRAFT


def frontmatter(text):
    lines = text.split('\n')
    if lines[0].strip() != '---':
        return None, lines
    end = lines.index('---', 1)
    block = lines[1:end]
    fields = {}
    key = None
    for line in block:
        m = re.match(r'^([A-Za-z_][\w-]*):\s?(.*)$', line)
        if m:
            key = m.group(1)
            fields[key] = m.group(2).strip().strip('"')
    return fields, lines[end + 1:]


def run_rose(args, db, extra_env=None):
    env = dict(os.environ)
    env['RED_ROSE_DB'] = str(db)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'rose.py'), *args],
                          capture_output=True, timeout=600, env=env, cwd=str(ROOT))
    return proc.returncode, proc.stdout.decode('utf-8', errors='replace')


class SkillTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = skill_target()
        cls.text = cls.path.read_text(encoding='utf-8')
        cls.fields, cls.body = frontmatter(cls.text)

    def test_frontmatter_on_line_one_with_allowed_keys_only(self):
        self.assertIsNotNone(self.fields, 'frontmatter must start on line 1')
        self.assertTrue(set(self.fields) <= ALLOWED_KEYS, set(self.fields) - ALLOWED_KEYS)
        self.assertEqual(self.fields.get('name'), 'red-rose')

    def test_description_limits(self):
        desc = self.fields['description']
        self.assertLessEqual(len(desc), 1024)
        self.assertNotRegex(desc, r'[<>]')
        head = desc[:200]
        self.assertTrue('Arabic' in head or 'Red Rose' in head, head)
        self.assertTrue(any(w in head for w in ('video', 'bank', 'reel', 'captions')), head)
        self.assertRegex(desc, r'\bUse (whenever|this|it)\b')

    def test_description_has_arabic_and_english_triggers(self):
        desc = self.fields['description']
        missing = [t for t in TRIGGERS if t not in desc]
        self.assertEqual(missing, [])
        self.assertIn('English keyboard layout', desc)

    def test_size_and_structure(self):
        total = len(self.text.split('\n'))
        if self.path == SKILL_DRAFT:
            self.assertTrue(150 <= total <= 200, total)
        self.assertLess(len(self.body), 500)

    def test_required_strings_and_no_stale_text(self):
        self.assertTrue('kinetic_text' in self.text or 'title_frame' in self.text)
        self.assertIn('bank-reconcile', self.text)
        self.assertNotIn('V17', self.text)
        self.assertNotIn('AGENTS.md', self.text)

    def test_relative_references_resolve(self):
        refs = set(re.findall(r'`((?:references|recipes|agent|catalog)/[\w./-]+)`', self.text))
        self.assertTrue(refs)
        missing = [r for r in refs if not (ROOT / r).exists()]
        self.assertEqual(missing, [])

    def test_forward_slashes_only_in_paths(self):
        for line in self.text.split('\n'):
            if '$env:' in line:
                continue
            self.assertIsNone(re.search(r'[A-Za-z]\\[A-Za-z]', line), line)

    def test_approval_rule_is_stated(self):
        self.assertIn('--approve-write', self.text)
        self.assertIn('explicit yes', self.text)

    def test_readme_top_block_shape(self):
        lines = README_DRAFT.read_text(encoding='utf-8').split('\n')
        self.assertLessEqual(len(lines), 60)
        text = '\n'.join(lines)
        self.assertIn('If you are an AI agent arriving from the link', text)
        self.assertIn('golden-dragon-alloy-private rr-src', text)
        self.assertIn('--no-cone', text)
        self.assertIn('git -C rr-src checkout main', text)
        self.assertIn('core.longpaths=true', text)
        self.assertIn('rose.py" start', text)
        self.assertIn('Do not read the rest of this file', text)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix='rr-pack-test-'))
        cls.db = cls.work / 'test.sqlite3'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_pack_refuses_without_approval_and_writes_nothing(self):
        out = self.work / 'dist_no_approval'
        code, text = run_rose(['pack', '--out', str(out)], self.db)
        self.assertEqual(code, 3)
        doc = json.loads(text)
        self.assertEqual(doc['outcome'], 'approval_required')
        self.assertFalse(out.exists())

    def test_install_refuses_without_approval_and_writes_nothing(self):
        target = self.work / 'skills' / 'red-rose'
        code, text = run_rose(['install-skill', '--target', str(target)], self.db)
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(text)['outcome'], 'approval_required')
        self.assertFalse(target.exists())
        self.assertFalse((self.work / 'skills').exists())

    def test_check_skill_is_clean(self):
        code, text = run_rose(['check-skill'], self.db)
        doc = json.loads(text)
        self.assertEqual(code, 0, doc)
        self.assertTrue(doc['ok'])
        self.assertEqual(doc['findings'], [])

    def test_pack_contents_and_manifest(self):
        import rose_pack
        out = self.work / 'dist'
        doc, code = rose_pack.pack(str(out), approve_write=True)
        self.assertEqual(code, 0, doc)
        archive = out / 'red-rose.skill'
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            self.assertEqual(names.count('red-rose/SKILL.md'), 1)
            self.assertEqual({n.split('/')[0] for n in names}, {'red-rose'})
            for n in names:
                rel = n[len('red-rose/'):]
                self.assertFalse(rel.startswith('test_'), n)
                self.assertFalse('/test_' in n, n)
                self.assertFalse(n.startswith('red-rose/drafts/'), n)
                self.assertFalse(n.startswith('red-rose/evals/'), n)
                self.assertFalse(n.endswith('.sqlite3') or n.endswith('.sqlite'), n)
                self.assertFalse('__pycache__' in n, n)
                self.assertFalse('/QUESTIONS_' in n or rel.startswith('QUESTIONS_'), n)
                self.assertFalse('.red-rose' in n, n)
                self.assertNotIn('/.git/', n)
            manifest = json.loads(zf.read('red-rose/PACKAGE_MANIFEST.json').decode('utf-8'))
            self.assertEqual(manifest['schema'], 'red-rose/package-manifest/1')
            self.assertEqual(manifest['file_count'], len(manifest['files']))
            self.assertFalse(any(k in manifest for k in ('created', 'date', 'built_at', 'generated_at')))
            for entry in manifest['files']:
                data = zf.read('red-rose/' + entry['path'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'], entry['path'])
        self.assertLess(archive.stat().st_size, 10 * 1024 * 1024)
        self.assertTrue(doc['ok'])

    def test_pack_refuses_existing_archive(self):
        import rose_pack
        out = self.work / 'dist'
        doc, code = rose_pack.pack(str(out), approve_write=True)
        self.assertEqual(code, 1)
        self.assertIn('already exists', doc['error'])

    def test_pack_verify_rejects_tampered_archive(self):
        import rose_pack
        src = self.work / 'dist' / 'red-rose.skill'
        bad = self.work / 'tampered.skill'
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(bad, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                data = zin.read(name)
                if name == 'red-rose/SKILL.md':
                    data = data + b'\n# edited\n'
                zout.writestr(name, data)
        doc, code = rose_pack.pack_verify(str(bad))
        self.assertEqual(code, 1)
        self.assertTrue(any('hash mismatch' in p for p in doc['problems']), doc['problems'])

    def test_pack_verify_rejects_forbidden_name(self):
        import rose_pack
        src = self.work / 'dist' / 'red-rose.skill'
        bad = self.work / 'forbidden.skill'
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(bad, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                zout.writestr(name, zin.read(name))
            zout.writestr('red-rose/test_leak.py', b'x = 1\n')
        doc, code = rose_pack.pack_verify(str(bad))
        self.assertEqual(code, 1)
        self.assertTrue(any('unlisted' in p or 'forbidden' in p for p in doc['problems']))

    def test_install_twice_leaves_one_live_copy_and_one_backup(self):
        import rose_pack
        target = self.work / 'skills_twice' / 'red-rose'
        doc1, code1 = rose_pack.install_skill(str(target), approve_write=True)
        self.assertEqual(code1, 0, doc1)
        self.assertIsNone(doc1['backup'])
        doc2, code2 = rose_pack.install_skill(str(target), approve_write=True)
        self.assertEqual(code2, 0, doc2)
        self.assertIsNotNone(doc2['backup'])
        siblings = sorted(p.name for p in target.parent.iterdir())
        live = [n for n in siblings if n == 'red-rose']
        backups = [n for n in siblings if n.startswith('red-rose.backup-')]
        self.assertEqual(live, ['red-rose'])
        self.assertEqual(len(backups), 1)
        self.assertTrue((target / 'SKILL.md').is_file())
        self.assertTrue((Path(doc2['backup']) / 'SKILL.md').is_file())

    def test_install_refuses_target_inside_working_folder(self):
        import rose_pack
        doc, code = rose_pack.install_skill(str(ROOT / 'tmp_should_not_exist'), approve_write=True)
        self.assertEqual(code, 1)
        self.assertFalse((ROOT / 'tmp_should_not_exist').exists())

    def test_pack_module_never_touches_private_store(self):
        source = (ROOT / 'rose_pack.py').read_text(encoding='utf-8')
        self.assertNotIn('sqlite3.connect', source)
        self.assertNotIn('RED_ROSE_DB', source.split('def pack_verify')[0])
        self.assertNotIn('.red-rose', source)
        self.assertNotIn('import rose_run', source)
        self.assertNotIn('subprocess.run', source.split('def pack_verify')[0])


if __name__ == '__main__':
    unittest.main()
