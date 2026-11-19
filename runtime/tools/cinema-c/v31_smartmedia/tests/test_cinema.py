#!/usr/bin/env python3
"""Offline contract tests for Cinema C V31 (mocked downloaders; no remote sites)."""
import os, subprocess, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / 'Cinema_C_V31_SmartMedia_iPhone.sh'
if not SCRIPT.exists():
 SCRIPT = Path('/mnt/data/Cinema_C_V31_SmartMedia_iPhone.sh')

YTDLP='''#!/bin/sh
case " $* " in *" --version "*) echo 2026.11.1; exit 0;; esac
case " $* " in *" --list-impersonate-targets "*) echo 'Safari - available'; exit 0;; esac
case " $* " in *" -F "*) echo '18 mp4 360p'; exit 0;; esac
printf '%s\\n' "$@" >> "${MOCK_YTDLP_ARGS:-/dev/null}"
case "${MOCK_YTDLP_MODE:-video}" in
  novideo) echo 'ERROR: [Instagram] There is no video in this post' >&2; exit 1;;
  fail) echo 'ERROR: video unavailable' >&2; exit 1;;
  login) echo 'Unsupported URL: https://www.facebook.com/login/' >&2; exit 1;;
  videolist)
    case " $* " in
      *" --write-pages "*)
        echo 'contains /reel/1234567890 and {"video_id":"1234567892"}' > mock_page.dump
        exit 0;;
    esac;;
esac
out=''
archive=''
while [ "$#" -gt 0 ]; do
 case "$1" in
  -o) out=$2; shift 2;;
  --download-archive) archive=$2; shift 2;;
  *) shift;;
 esac
done
[ -n "$out" ] || exit 0
folder=${out%/*}
[ "$folder" != "$out" ] || folder=.
mkdir -p "$folder"
printf 'mock-video-bytes' > "$folder/cinema_test_video.mp4"
if [ -n "$archive" ]; then printf 'facebook 1234567890\\n' >> "$archive"; fi
exit 0
'''
GALLERY='''#!/bin/sh
case " $* " in *" --version "*) echo 1.30.0; exit 0;; esac
printf '%s\\n' "$@" >> "${MOCK_GALLERY_ARGS:-/dev/null}"
dir=''
while [ "$#" -gt 0 ]; do
 case "$1" in
  -D) dir=$2; shift 2;;
  *) shift;;
 esac
done
[ -n "$dir" ] || exit 2
mkdir -p "$dir"
case "${MOCK_GALLERY_MODE:-images}" in
  images) printf mock > "$dir/image_a.jpg"; printf mock > "$dir/image_b.png";;
  mixed) printf mock > "$dir/image_a.jpg"; printf mock > "$dir/video_a.mp4";;
  fail) echo 'Authentication required' >&2; exit 2;;
  partial) printf mock > "$dir/image_a.jpg"; echo 'some error' >&2; exit 2;;
esac
exit 0
'''

class CinemaV31Test(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='cinema_v31_contract_')
  self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.home=self.root/'home'
  self.home.mkdir()
  self.bin=self.root/'bin'; self.bin.mkdir()
  for filename,contents in [('yt-dlp',YTDLP),('gallery-dl',GALLERY)]:
   f=self.bin/filename; f.write_text(contents); f.chmod(0o755)
  self.env=os.environ.copy()
  self.env.update({'HOME':str(self.home),'PATH':f'{self.bin}:'+os.environ['PATH'],'MOCK_YTDLP_MODE':'novideo','MOCK_GALLERY_MODE':'images','MOCK_YTDLP_ARGS':str(self.root/'yt_args.txt'), 'MOCK_GALLERY_ARGS':str(self.root/'gallery_args.txt')})
 def run_script(self,*args,stdin=''):
  return subprocess.run(['sh',str(SCRIPT),*args],env=self.env,input=stdin,text=True,capture_output=True,cwd=self.root,timeout=10)
 def files(self):
  return list((self.home/'Documents'/'Cinema_Downloads').rglob('*'))
 def test_help(self):
  p=self.run_script('--help'); self.assertEqual(p.returncode,0,p.stderr)
  self.assertIn('--smart',p.stdout)
 def test_doctor(self):
  p=self.run_script('--doctor'); self.assertEqual(p.returncode,0,p.stderr)
  self.assertIn('gallery-dl: 1.30.0',p.stdout)
 def test_gallery_smart_photo(self):
  p=self.run_script('--files','--smart','https://www.instagram.com/p/Ddcxrll0Oml/?x=foo')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('Saved 2 media assets',p.stdout)
  self.assertEqual(len([x for x in self.files() if x.is_file()]),2)
  self.assertTrue(any('Instagram_Ddcxrll0Oml' in str(x) for x in self.files()))
 def test_gallery_smart_mixed(self):
  self.env['MOCK_GALLERY_MODE']='mixed'
  p=self.run_script('--files','--smart','https://www.instagram.com/p/Anything/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('1 image(s), 1 video(s)',p.stdout)
 def test_video_best_falls_back_on_no_video(self):
  p=self.run_script('--files','https://www.instagram.com/p/Ddcxrll0Oml/',stdin='1\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('Checking Instagram photos/carousel',p.stderr)
  self.assertIn('Saved 2 media assets',p.stdout)
 def test_video_normal_path(self):
  self.env['MOCK_YTDLP_MODE']='video'
  p=self.run_script('--files','https://www.instagram.com/reel/TestReel/',stdin='1\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('DONE:',p.stdout)
  self.assertEqual(len([x for x in self.files() if x.is_file()]),1)
 def test_missing_gallery_in_photo_path(self):
  (self.bin/'gallery-dl').unlink()
  p=self.run_script('--files','https://www.instagram.com/p/TestPhoto/',stdin='1\n')
  self.assertNotEqual(p.returncode,0)
  self.assertIn('gallery-dl',p.stderr)
 def test_gallery_partial_success(self):
  self.env['MOCK_GALLERY_MODE']='partial'
  p=self.run_script('--files','--gallery','https://www.instagram.com/p/partial/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('some errors',p.stderr)
  self.assertEqual(len([x for x in self.files() if x.is_file()]),1)
 def test_gallery_fail_does_not_claim_success(self):
  self.env['MOCK_GALLERY_MODE']='fail'
  p=self.run_script('--gallery','https://www.instagram.com/p/fail/')
  self.assertNotEqual(p.returncode,0)
  self.assertIn('did not produce any complete media files',p.stderr)
 def test_cookies_absolute_for_gallery(self):
  (self.root/'cookies.txt').write_text('# Netscape HTTP Cookie File\n')
  p=self.run_script('--cookies','cookies.txt','--files','--gallery','https://www.instagram.com/p/foo/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  args=(self.root/'gallery_args.txt').read_text()
  self.assertIn(str(self.root/'cookies.txt'),args)
 def test_facebook_public_bulk_discovery(self):
  self.env['MOCK_YTDLP_MODE']='videolist'
  p=self.run_script('--files','https://www.facebook.com/profile.php?id=12345678',stdin='1\ny\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('Candidate links discovered: 2',p.stdout)
  self.assertIn('New downloads: 2',p.stdout)
 def test_facebook_cookies_absolute_after_cd(self):
  (self.root/'cookies.txt').write_text('# Netscape HTTP Cookie File\n')
  self.env['MOCK_YTDLP_MODE']='login'
  p=self.run_script('--cookies','cookies.txt','https://www.facebook.com/profile.php?id=12345678',stdin='1\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn(str(self.root/'cookies.txt'),(self.root/'yt_args.txt').read_text())
 def test_install_c_command(self):
  p=self.run_script('--install')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertTrue((self.home/'Documents'/'bin'/'c').is_file())
 def test_invalid_cookie_rejected(self):
  (self.root/'badcookies.txt').write_text('not a cookie file\n')
  p=self.run_script('--cookies','badcookies.txt','--gallery','https://www.instagram.com/p/foo/')
  self.assertNotEqual(p.returncode,0)
  self.assertIn('Netscape',p.stderr)
 def test_gallery_works_without_ytdlp(self):
  (self.bin/'yt-dlp').unlink()
  p=self.run_script('--gallery','--files','https://www.instagram.com/p/withoutVideo/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_smart_gallery_works_without_ytdlp(self):
  (self.bin/'yt-dlp').unlink()
  p=self.run_script('--smart','--files','https://www.instagram.com/p/withoutVideo/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_download_quality_respects_max(self):
  self.env['MOCK_YTDLP_MODE']='video'
  p=self.run_script('--files','https://www.instagram.com/reel/Quality/',stdin='6\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  args=(self.root/'yt_args.txt').read_text()
  self.assertIn('height<=480',args)
  self.assertNotIn('/best\n',args)
 def test_relative_output_normalized(self):
  p=self.run_script('--output','downloads','--files','--gallery','https://www.instagram.com/p/output/')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertTrue(any((self.root/'downloads').rglob('*.jpg')))
 def test_facebook_login_gate(self):
  self.env['MOCK_YTDLP_MODE']='login'
  p=self.run_script('--files','https://www.facebook.com/profile.php?id=12345678',stdin='1\n')
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('LOGIN',p.stdout)
  self.assertIn('requires a logged-in session',p.stdout)

if __name__ == '__main__': unittest.main(verbosity=2)
