"""W10: the documentation rules.

- every `rose.py <command>` named in the drafts and the references exists;
- every recipe id named exists in recipes/;
- a claim of "verified" only where VERIFIED_STATUS.json backs it;
- every doc command line runs (read-only ones for real, all others with
  `--help`, so no test writes media, approvals or files). Lines that write
  are never executed here: they are checked for an existing subcommand only.

Every run uses a temp RED_ROSE_DB, so the owner's database is never opened.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOC_FILES = [
    'drafts/SKILL.draft.md',
    'drafts/README_TOP.draft.md',
    'references/USE.md',
    'references/BOOTSTRAP.md',
    'references/WINDOWS.md',
    'references/OWNER_RULES.md',
    'references/DEVELOPING.md',
]
READ_RUN = {'start', 'check-skill', 'describe', 'recipes', 'ops', 'find', 'understand', 'brief'}
READ_RUN_PAIRS = {('recipe', 'validate')}
WRITE_PREFIX_EXPECT = {'pack': 3, 'install-skill': 3}


def _texts():
    return {name: (ROOT / name).read_text(encoding='utf-8') for name in DOC_FILES}


def _subcommands():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'rose.py'), '--help'],
                          capture_output=True, timeout=120, cwd=str(ROOT),
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                   RED_ROSE_DB=str(Path(tempfile.gettempdir()) / 'rr-entry-help.sqlite3')))
    text = proc.stdout.decode('utf-8', errors='replace')
    m = re.search(r'\{([^}]+)\}', text)
    return set(m.group(1).split(',')) if m else set()


def _recipe_ids():
    ids = set()
    for path in (ROOT / 'recipes').glob('*.json'):
        ids.add(json.loads(path.read_text(encoding='utf-8'))['id'])
    return ids


def _verified_count():
    data = json.loads((ROOT / 'references' / 'VERIFIED_STATUS.json').read_text(encoding='utf-8'))
    return data['counts']['verified']


class EntryDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts = _texts()
        cls.commands = _subcommands()
        cls.recipes = _recipe_ids()
        cls.work = Path(tempfile.mkdtemp(prefix='rr-entry-'))
        cls.db = cls.work / 'doc.sqlite3'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def _run(self, args, timeout=300):
        env = dict(os.environ)
        env['RED_ROSE_DB'] = str(self.db)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'rose.py'), *args],
                              capture_output=True, timeout=timeout, env=env, cwd=str(ROOT))
        return proc.returncode, proc.stdout.decode('utf-8', errors='replace')

    def test_subcommand_list_is_readable(self):
        for expected in ('start', 'brief', 'run', 'check', 'recipe', 'pack', 'pack-verify', 'install-skill'):
            self.assertIn(expected, self.commands)

    def test_every_named_command_exists(self):
        named = set()
        for name, text in self.texts.items():
            for cmd in re.findall(r'rose\.py"?\s+([a-z][a-z0-9-]+)', text):
                named.add((name, cmd))
        self.assertTrue(named)
        missing = sorted(f'{name}: {cmd}' for name, cmd in named if cmd not in self.commands)
        self.assertEqual(missing, [])

    def test_every_named_recipe_exists(self):
        pattern = re.compile(r'recipe (?:run|show|selftest) ([a-z][a-z0-9-]+)')
        named = set()
        for text in self.texts.values():
            named.update(pattern.findall(text))
        self.assertTrue(named)
        self.assertEqual(sorted(named - self.recipes), [])
        for rid in ('title-frame-ar', 'title-clip-mp4', 'shot-report-recut', 'captions-from-words',
                    'loudness-fix', 'bank-reconcile', 'iphone-export', 'beat-synced-cut'):
            self.assertIn(rid, self.recipes)

    def test_verified_claims_match_status_file(self):
        count = _verified_count()
        for name, text in self.texts.items():
            for line in text.split('\n'):
                if re.search(r'\bverified\b', line, re.IGNORECASE):
                    self.assertTrue(
                        'VERIFIED_STATUS' in line or 'not measured' in line or 'not re-run' in line
                        or 'not verified' in line or 'measured earlier' in line,
                        f'{name}: unbacked claim: {line.strip()[:120]}')
                for num in re.findall(r'verified\D{0,12}(\d+)', line, re.IGNORECASE):
                    self.assertEqual(int(num), count, f'{name}: {line.strip()[:120]}')

    def test_doc_command_lines_run(self):
        pattern = re.compile(r'python -X utf8\s+"?<skill folder>/rose\.py"?\s+(.+)$')
        lines = []
        for name, text in self.texts.items():
            for line in text.split('\n'):
                m = pattern.search(line.strip())
                if m:
                    lines.append((name, line.strip(), m.group(1)))
        self.assertGreater(len(lines), 8)
        ran = helped = 0
        failures = []
        for name, raw, rest in lines:
            rest = rest.replace('<skill folder>', ROOT.as_posix()).replace('<work>', self.work.as_posix())
            try:
                tokens = shlex.split(rest, posix=True)
            except ValueError as exc:
                failures.append(f'{name}: cannot split: {raw[:100]} ({exc})')
                continue
            if not tokens:
                continue
            cmd = tokens[0]
            if cmd not in self.commands:
                failures.append(f'{name}: unknown command {cmd}')
                continue
            joined = ' '.join(tokens)
            key = (cmd, tokens[1]) if len(tokens) > 1 else (cmd,)
            real = (cmd in READ_RUN or key in READ_RUN_PAIRS) and '<' not in joined \
                and '--approve-write' not in tokens
            if cmd in WRITE_PREFIX_EXPECT and '--approve-write' not in tokens and '<' not in joined:
                rc, out = self._run(tokens)
                ran += 1
                if rc != WRITE_PREFIX_EXPECT[cmd]:
                    failures.append(f'{name}: exit {rc}, expected {WRITE_PREFIX_EXPECT[cmd]}: {raw[:100]}')
                if rc == WRITE_PREFIX_EXPECT[cmd]:
                    self.assertTrue(json.loads(out).get('nothing_written'), out[:200])
                continue
            if real:
                rc, out = self._run(tokens)
                ran += 1
                if rc != 0:
                    failures.append(f'{name}: exit {rc}: {raw[:100]}')
                continue
            helpargs = [cmd] + (tokens[1:2] if key in READ_RUN_PAIRS or cmd == 'recipe' else []) + ['--help']
            rc, _ = self._run(helpargs, timeout=120)
            helped += 1
            if rc != 0:
                failures.append(f'{name}: help exit {rc}: {raw[:100]}')
        self.assertGreater(ran, 0)
        self.assertEqual(failures, [], f'ran={ran} help_checked={helped}')

    def test_no_draft_points_to_legacy_or_private_locations(self):
        for name in ('drafts/SKILL.draft.md', 'drafts/README_TOP.draft.md'):
            text = self.texts[name]
            self.assertNotIn('golden-dragon-alloy-private/red-rose/', text.replace('rr-src/red-rose', ''))
            self.assertNotIn('dragon', text.lower().replace('golden-dragon-alloy-private', ''))


if __name__ == '__main__':
    unittest.main()
