"""V69: every dua request that passes through `brief` carries the owner's mandatory source gate."""
import unittest

import json
import subprocess
import sys
from pathlib import Path

import rose_agent
import rose_dua_gate_v69 as gate_mod

ROOT = Path(__file__).resolve().parent


class DuaGateTest(unittest.TestCase):
    def test_arabic_dua_requests_carry_the_gate(self):
        for text in ('اعمل ريل دعاء يوم الجمعة', 'عايز ريل أدعية الصباح', 'ريل أذكار المساء', 'دُعَاء للمريض ريل'):
            b = gate_mod.brief(text)
            gate = b.get('mandatory_gate')
            self.assertIsNotNone(gate, text)
            self.assertEqual(gate['id'], 'dua-source-gate')
            self.assertEqual(gate['read_first'], 'references/DUA_REELS_PLAYBOOK.md')
            self.assertIn('dua-telegram-complete', gate['text_ar'])
            self.assertIn('⛔', b['text'])

    def test_latin_dua_words_match_whole_words_only(self):
        self.assertIsNotNone(gate_mod.dua_gate('make a dua reel for friday'))
        self.assertIsNotNone(gate_mod.dua_gate('morning Azkar video'))
        for text in ('dual audio export', 'fix the audio loudness', 'adequate quality'):
            self.assertIsNone(gate_mod.dua_gate(text), text)

    def test_other_requests_are_untouched(self):
        for text in ('عايز اطابق كشف حساب البنك مع الدفتر', 'اعمل عنوان متحرك باسم الوردة الحمراء', 'شكرا'):
            b = gate_mod.brief(text)
            self.assertNotIn('mandatory_gate', b, text)
            self.assertNotIn('⛔', b['text'])

    def test_follow_up_inherits_the_gate_from_the_previous_message(self):
        b = gate_mod.brief('كمل', prev='اعمل ريل دعاء يوم الجمعة')
        self.assertIn('mandatory_gate', b)

    def test_gate_does_not_change_the_route_or_grant_approval(self):
        with_gate = gate_mod.brief('اعمل ريل دعاء يوم الجمعة')
        self.assertEqual(with_gate['route']['id'], 'shot-report-recut')
        self.assertEqual(with_gate['approvals'], ['write'])

    def test_the_playbook_section_the_gate_points_to_exists(self):
        text = (ROOT / gate_mod.PLAYBOOK).read_text(encoding='utf-8')
        self.assertIn('Mandatory owner rule', text)

    def test_router_result_is_identical_apart_from_the_gate(self):
        text = 'اعمل ريل دعاء يوم الجمعة'
        plain, gated = rose_agent.brief(text), gate_mod.brief(text)
        gated.pop('mandatory_gate')
        plain.pop('text'), gated.pop('text')
        self.assertEqual(plain, gated)

    def _cli(self, *args):
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'rose.py'), *args],
                              capture_output=True, timeout=120)
        return proc.returncode, proc.stdout.decode('utf-8')

    def test_cli_brief_json_and_text_carry_the_gate(self):
        code, out = self._cli('brief', 'اعمل ريل دعاء يوم الجمعة')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['mandatory_gate']['id'], 'dua-source-gate')
        code, out = self._cli('brief', 'اعمل ريل دعاء يوم الجمعة', '--text')
        self.assertEqual(code, 0)
        self.assertTrue(out.split('\n')[1].startswith('⛔'))
        code, out = self._cli('brief', 'ظبطلي صوت الفيديو ده')
        self.assertNotIn('mandatory_gate', json.loads(out))

    def test_cli_dua_gate_command(self):
        code, out = self._cli('dua-gate', 'ريل أذكار الصباح')
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)['applies'])
        code, out = self._cli('dua-gate', 'dual audio')
        self.assertFalse(json.loads(out)['applies'])


class PackagedDocsTest(unittest.TestCase):
    """V69: the installed skill carries every root guide SKILL.md tells the agent to read."""

    def test_root_documents_named_in_skill_md_are_packaged(self):
        import re
        import rose_pack
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        named = {m.group(0) for m in re.finditer(r'(?<![/\w])[A-Z][A-Z0-9_]+\.(?:md|json)', skill)}
        named = {n for n in named if (ROOT / n).is_file()}
        self.assertIn('AGENT_NOTES.md', named)
        got = rose_pack.collect()
        self.assertEqual(got['problems'], [])
        self.assertEqual(sorted(named - set(got['files'])), [])

if __name__ == '__main__':
    unittest.main()
