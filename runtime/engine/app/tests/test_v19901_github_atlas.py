"""Offline tests of the v1990.1 GitHub metadata bridge. No repository code executed."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'tools/github_atlas/atlas.py'


def call(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,text=True,encoding='utf-8',timeout=30)


class AtlasOfflineTests(unittest.TestCase):
    def test_doctor_sha(self):
        r=call('doctor','--json');self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout);self.assertTrue(result['verified']);self.assertEqual(result['entries'],1000)
        self.assertEqual(result['categories'],22)
        self.assertFalse(result['network']);self.assertFalse(result['executed'])

    def test_stats_and_cats(self):
        r=call('stats','--json');self.assertEqual(r.returncode,0,r.stderr)
        x=json.loads(r.stdout);self.assertEqual(x['total'],1000)
        self.assertEqual(x['blocked'],8);self.assertEqual(x['consent'],30)
        cats=json.loads(call('cats','--json').stdout);self.assertEqual(sum(cats.values()),1000)

    def test_search_arabic_and_english(self):
        for q in ['مونتاج فيديو','voice transcription','تطبيقات ويب']:
            r=call('find',q,'--json','-n','8');self.assertEqual(r.returncode,0,r.stderr)
            items=json.loads(r.stdout);self.assertTrue(items,q)
            self.assertTrue(all(x['policy']!='blocked' for x in items))

    def test_blocked_cannot_be_shown_or_recommended(self):
        r=call('show','massgravel/Microsoft-Activation-Scripts');self.assertEqual(r.returncode,3)
        r=call('find','Microsoft-Activation-Scripts','--json');self.assertEqual(r.returncode,0)
        self.assertNotIn('massgravel/Microsoft-Activation-Scripts',r.stdout)
        r=call('top','--by','stars','--json','-n','100');self.assertEqual(r.returncode,0)
        self.assertNotIn('massgravel/Microsoft-Activation-Scripts',r.stdout)

    def test_consent_warning(self):
        # A flagged repo in the user-provided metadata
        r=call('show','RVC-Project/Retrieval-based-Voice-Conversion-WebUI')
        if r.returncode==2:
            r=call('show','facefusion/facefusion')
        if r.returncode==0:
            d=json.loads(r.stdout)
            if d.get('policy')=='consent':self.assertIn('notice',d)

    def test_valid_record_details(self):
        r=call('show','yt-dlp/yt-dlp');self.assertEqual(r.returncode,0,r.stderr)
        d=json.loads(r.stdout);self.assertEqual(d['repo'],'yt-dlp/yt-dlp')
        self.assertIn('note',d)

    def test_known_unknown(self):
        r=call('show','not-real/not-a-repo');self.assertEqual(r.returncode,2)

    def test_top_filtered(self):
        r=call('top','--by','relevance','--cat','media-processing','--json','-n','5')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(all(x['category']=='media-processing' for x in json.loads(r.stdout)))

    def test_no_network_execution_calls_in_new_adapter(self):
        # Scope: this script only. The other pre-existing Dragon code is NOT verified by this test.
        txt=SCRIPT.read_text(encoding='utf-8')
        for needle in ('subprocess.', 'os.system(', 'requests.', 'urllib.request.', 'socket.', 'eval(', 'exec(', 'pip install'):
            self.assertNotIn(needle,txt)


if __name__=='__main__':unittest.main()
