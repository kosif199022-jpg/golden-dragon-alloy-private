"""Offline exercise of net_v28 (net.fetch): every gate, with no network at all.

The urllib opener is replaced by an in-memory fake that serves canned responses;
socket connections, DNS lookups and subprocess.run are patched to raise, so any
accidental real network access or program start fails the test loudly.
"""
import email.message
import io
import json
import os
import socket
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import net_v28 as net

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 120
PAGE = (b'<!doctype html><html><head><title>Red Rose page</title></head><body>'
        b'<h1>Heading</h1><p>Hello offline world.</p>'
        b'<a href="/two.html">two</a> <a href="https://other.example.org/x">ext</a>'
        b'<a href="/doc.pdf">pdf</a><img src="/pic.png"><a href="mailto:a@b.c">m</a>'
        b'<a href="/three.html" rel="nofollow">three</a></body></html>')
ROBOTS_OK = b'User-agent: *\nDisallow: /private\n'


def _headers(ctype=None, extra=None):
    h = email.message.Message()
    if ctype:
        h['Content-Type'] = ctype
    for k, v in (extra or {}).items():
        h[k] = v
    return h


class FakeResp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self._buf = io.BytesIO(body)
        self.closed = False

    def read(self, n=-1):
        return self._buf.read(n)

    def getcode(self):
        return self.status

    def close(self):
        self.closed = True


class FakeOpener:
    """routes: canonical URL -> (status, content-type, body, extra headers)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def open(self, req, timeout=None):
        url = req.full_url
        self.calls.append({'url': url, 'headers': dict(req.header_items()), 'timeout': timeout})
        if url not in self.routes:
            raise urllib.error.HTTPError(url, 404, 'Not Found', _headers('text/plain'), io.BytesIO(b''))
        status, ctype, body, extra = (self.routes[url] + (None,) * 4)[:4]
        hdrs = _headers(ctype, extra)
        if status >= 300:
            raise urllib.error.HTTPError(url, status, 'x', hdrs, io.BytesIO(body or b''))
        return FakeResp(status, hdrs, body or b'')


def _no_network(*a, **k):
    raise AssertionError('real network access attempted in an offline test')


def _no_program(*a, **k):
    raise AssertionError('an external program was started in an offline test')


class NetCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wd = Path(self.tmp.name).resolve()
        net._LAST_HIT.clear()
        for target, attr in ((socket.socket, 'connect'), (socket, 'create_connection'),
                             (socket, 'getaddrinfo')):
            p = mock.patch.object(target, attr, _no_network)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(net.subprocess, 'run', _no_program)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(net.time, 'sleep', lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.opener = None

    def serve(self, routes):
        self.opener = FakeOpener(routes)
        p = mock.patch.object(net, '_opener', lambda: self.opener)
        p.start()
        self.addCleanup(p.stop)
        return self.opener

    def base(self, **kw):
        p = {'url': 'https://example.com/page.html', 'allow_list': ['example.com'],
             'work_dir': str(self.wd), 'min_interval_s': 0.5, 'timeout_s': 5}
        p.update(kw)
        return p

    def records(self):
        path = self.wd / 'sources.jsonl'
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]

    def user_files(self):
        return sorted(p.name for p in self.wd.iterdir() if p.name != 'sources.jsonl')


class TestInterface(NetCase):
    def test_tables(self):
        self.assertEqual(set(net.OPS), set(net.EFFECTS))
        self.assertEqual(set(net.TOPICS.values()), set(net.OPS))
        for op in ('fetch_page', 'fetch_file', 'crawl_site', 'collect_links', 'media_download',
                   'github_repo_info'):
            self.assertEqual(net.EFFECTS[op], 'write', op)
        self.assertEqual(net.EFFECTS['plan_fetch'], 'read')
        self.assertEqual(net.EFFECTS['sources'], 'read')

    def test_run_validation(self):
        with self.assertRaises(ValueError):
            net.run('nope', {})
        with self.assertRaises(ValueError):
            net.run('plan_fetch', [])
        with self.assertRaises(ValueError):
            net.run('plan_fetch', {'url': 'https://example.com', 'allow_list': ['example.com'], 'zzz': 1})
        for key in ('cookie', 'password', 'session_id', 'api_key', 'auth_token'):
            with self.assertRaisesRegex(ValueError, 'refused'):
                net.run('fetch_page', dict(self.base(), **{key: 'x'}))


class TestPlanFetch(NetCase):
    def test_allowed_plan_without_network(self):
        opener = self.serve({})
        out = net.run('plan_fetch', {'url': 'https://Example.com/a?utm_source=x&id=3#frag',
                                     'allow_list': ['example.com'], 'work_dir': str(self.wd)})
        r = out['result']
        self.assertTrue(r['allowed'])
        self.assertEqual(r['canonical_url'], 'https://example.com/a?id=3')
        self.assertEqual(r['removed_tracking_params'], ['utm_source'])
        self.assertEqual(r['plan']['robots_url'], 'https://example.com/robots.txt')
        self.assertEqual(r['plan']['approve_with'], {'approve_write': True})
        self.assertFalse(r['plan']['cookies'])
        self.assertEqual(opener.calls, [])
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_reasons_http_and_allow_list(self):
        r = net.run('plan_fetch', {'url': 'http://evil.example.net/', 'allow_list': ['example.com']})['result']
        self.assertFalse(r['allowed'])
        self.assertIsNone(r['plan'])
        self.assertEqual(len(r['reasons']), 2)
        r = net.run('plan_fetch', {'url': 'http://example.com/', 'allow_list': ['example.com'],
                                   'allow_http': True})['result']
        self.assertTrue(r['allowed'])

    def test_allow_list_forms(self):
        def allowed(url, rules):
            return net.run('plan_fetch', {'url': url, 'allow_list': rules})['result']['allowed']
        self.assertTrue(allowed('https://a.example.org/x', ['*.example.org']))
        self.assertFalse(allowed('https://example.org.evil.com/x', ['*.example.org']))
        self.assertTrue(allowed('https://example.net/docs/a', ['example.net/docs']))
        self.assertFalse(allowed('https://example.net/admin', ['example.net/docs']))
        self.assertFalse(allowed('https://sub.example.com/', ['example.com']))
        self.assertFalse(allowed('http://example.com/', ['https://example.com']))
        for bad in (None, [], 'example.com', ['user@example.com'], ['example.com:8443']):
            with self.assertRaises(ValueError):
                net.run('plan_fetch', {'url': 'https://example.com/', 'allow_list': bad})

    def test_url_refusals(self):
        for url in ('ftp://example.com/x', 'https://user:pw@example.com/', 'example.com/x',
                    'https://exa mple.com/'):
            with self.assertRaises(ValueError):
                net.run('plan_fetch', {'url': url, 'allow_list': ['example.com']})

    def test_media_plan_reports_tool(self):
        with mock.patch.object(net.shutil, 'which', lambda n: None):
            r = net.run('plan_fetch', {'url': 'https://example.com/v', 'allow_list': ['example.com'],
                                       'intended_op': 'media_download'})['result']
        self.assertFalse(r['plan']['yt_dlp_found'])
        self.assertIsNone(r['plan']['robots_url'])


class TestApprovalGate(NetCase):
    def test_every_network_op_needs_approval(self):
        opener = self.serve({})
        calls = {
            'fetch_page': self.base(),
            'fetch_file': self.base(url='https://example.com/a.png'),
            'crawl_site': self.base(),
            'collect_links': self.base(),
        }
        for op, params in calls.items():
            out = net.run(op, params)
            self.assertEqual(out['result']['status'], 'approval_required', op)
            self.assertTrue(out['result']['plan']['external_action'])
        out = net.run('github_repo_info', {'owner': 'python', 'repo': 'cpython', 'work_dir': str(self.wd)})
        self.assertEqual(out['result']['status'], 'approval_required')
        self.assertEqual(opener.calls, [])
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_validation_happens_before_the_approval_check(self):
        # documented order: allow-list / https / work_dir checks refuse even an unapproved call
        with self.assertRaisesRegex(ValueError, 'allow_list'):
            net.run('fetch_page', self.base(url='https://other.example.org/'))
        with self.assertRaisesRegex(ValueError, 'plain http'):
            net.run('fetch_page', self.base(url='http://example.com/'))
        with self.assertRaisesRegex(ValueError, 'work_dir'):
            net.run('fetch_page', self.base(work_dir=str(self.wd / 'missing')))
        with self.assertRaisesRegex(ValueError, 'absolute'):
            net.run('fetch_page', self.base(work_dir='relative/dir'))
        with self.assertRaisesRegex(ValueError, 'UNC'):
            net.run('fetch_page', self.base(work_dir='\\\\server\\share'))
        with self.assertRaises(ValueError):
            net.run('fetch_page', self.base(approve_write='yes'))

    def test_licence_gate_refuses_no_store(self):
        with self.assertRaisesRegex(ValueError, 'licence'):
            net.run('fetch_page', self.base(terms_text='You may not copy, store or redistribute any content.'))


class TestFetchPage(NetCase):
    def test_page_saved_with_robots_and_sources(self):
        opener = self.serve({
            'https://example.com/robots.txt': (200, 'text/plain', ROBOTS_OK),
            'https://example.com/page.html': (200, 'text/html; charset=utf-8', PAGE),
        })
        out = net.run('fetch_page', self.base(approve_write=True))
        r = out['result']
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['title'], 'Red Rose page')
        self.assertIn('Hello offline world.', r['text_summary'])
        self.assertTrue(r['untrusted_content'])
        self.assertEqual([c['url'] for c in opener.calls],
                         ['https://example.com/robots.txt', 'https://example.com/page.html'])
        for c in opener.calls:
            hdrs = {k.lower(): v for k, v in c['headers'].items()}
            self.assertEqual(hdrs['user-agent'], net.USER_AGENT)
            self.assertNotIn('cookie', hdrs)
            self.assertNotIn('authorization', hdrs)
            self.assertEqual(c['timeout'], 5.0)
        files = self.user_files()
        self.assertEqual(len(files), 2)
        self.assertTrue(any(f.endswith('.html') for f in files) and any(f.endswith('.txt') for f in files))
        self.assertFalse(any(f.endswith('.part') for f in files))
        html_file = Path(r['files']['html'])
        self.assertEqual(html_file.read_bytes(), PAGE)
        recs = self.records()
        self.assertEqual([x['kind'] for x in recs], ['robots', 'page'])
        self.assertEqual(recs[1]['saved_as'], sorted(recs[1]['saved_as'], key=lambda n: not n.endswith('.html')))
        self.assertEqual(recs[1]['status'], 200)
        self.assertEqual(len(recs[1]['sha256']), 64)
        self.assertEqual(recs[1]['user_agent'], net.USER_AGENT)
        # a second fetch never overwrites: new names are chosen
        net._LAST_HIT.clear()
        out2 = net.run('fetch_page', self.base(approve_write=True))
        self.assertNotEqual(out2['result']['files']['html'], r['files']['html'])
        self.assertEqual(html_file.read_bytes(), PAGE)

    def test_robots_disallow_stops_before_the_page(self):
        opener = self.serve({'https://example.com/robots.txt': (200, 'text/plain', ROBOTS_OK)})
        out = net.run('fetch_page', self.base(url='https://example.com/private/x.html', approve_write=True))
        r = out['result']
        self.assertEqual(r['status'], 'robots_disallowed')
        self.assertEqual([c['url'] for c in opener.calls], ['https://example.com/robots.txt'])
        self.assertEqual(self.user_files(), [])

    def test_robots_parsing_modes(self):
        page = (200, 'text/html', PAGE)
        cases = [
            ((404, 'text/plain', b''), 'allow_all', 'ok'),
            ((403, 'text/plain', b''), 'disallow_all', 'robots_disallowed'),
            ((503, 'text/plain', b''), 'disallow_all', 'robots_disallowed'),
            ((200, 'text/plain', b'User-agent: RedRose\nDisallow: /\n\nUser-agent: *\nAllow: /\n'),
             'parsed', 'robots_disallowed'),
            ((200, 'text/plain', b'User-agent: *\nCrawl-delay: 500\n'), 'parsed', 'refused'),
        ]
        for robots, mode, outcome in cases:
            with self.subTest(robots=robots[:1], mode=mode):
                net._LAST_HIT.clear()
                tmp = tempfile.TemporaryDirectory()
                try:
                    self.serve({'https://example.com/robots.txt': robots,
                                'https://example.com/page.html': page})
                    r = net.run('fetch_page', self.base(work_dir=tmp.name, approve_write=True))['result']
                    self.assertEqual(r['status'], outcome)
                    if outcome != 'ok':
                        self.assertEqual(r['robots']['mode'], mode)
                finally:
                    tmp.cleanup()

    def test_crawl_delay_is_honoured(self):
        waits = []
        self.serve({'https://example.com/robots.txt': (200, 'text/plain', b'User-agent: *\nCrawl-delay: 7\n'),
                    'https://example.com/page.html': (200, 'text/html', PAGE)})
        with mock.patch.object(net.time, 'sleep', waits.append):
            r = net.run('fetch_page', self.base(approve_write=True))['result']
        self.assertEqual(r['status'], 'ok')
        self.assertTrue(waits and max(waits) > 5.0, waits)

    def test_login_captcha_paywall_refused(self):
        bodies = {'login': b'<html><form><input type="password" name="p"></form></html>',
                  'captcha': b'<html><div class="g-recaptcha"></div></html>',
                  'paywall': b'<html><p>Subscribe to continue reading</p></html>'}
        for name, body in bodies.items():
            with self.subTest(gate=name):
                net._LAST_HIT.clear()
                self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                            'https://example.com/page.html': (200, 'text/html', body)})
                r = net.run('fetch_page', self.base(approve_write=True))['result']
                self.assertEqual(r['status'], 'refused')
                self.assertIn('never bypassed', r['reason'])
                self.assertEqual(self.user_files(), [])
        self.assertTrue(all(x['outcome'] in ('http_error', 'refused_gate') for x in self.records()))

    def test_access_denied_is_not_retried(self):
        for status in (401, 402, 403, 407, 451):
            with self.subTest(status=status):
                net._LAST_HIT.clear()
                opener = self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                                     'https://example.com/page.html': (status, 'text/html', b'no')})
                r = net.run('fetch_page', self.base(approve_write=True, max_attempts=3))['result']
                self.assertEqual(r['http_status'], status)
                self.assertIn('no login, cookie or bypass', r['reason'])
                page_calls = [c for c in opener.calls if c['url'].endswith('page.html')]
                self.assertEqual(len(page_calls), 1)

    def test_server_error_is_retried_then_reported(self):
        opener = self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                             'https://example.com/page.html': (503, 'text/html', b'busy')})
        r = net.run('fetch_page', self.base(approve_write=True, max_attempts=3))['result']
        self.assertEqual(r['status'], 'http_error')
        self.assertEqual(len([c for c in opener.calls if c['url'].endswith('page.html')]), 3)

    def test_wrong_content_type(self):
        self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                    'https://example.com/page.html': (200, 'application/json', b'{}')})
        r = net.run('fetch_page', self.base(approve_write=True))['result']
        self.assertEqual(r['status'], 'wrong_content_type')
        self.assertEqual(self.user_files(), [])

    def test_redirects(self):
        self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                    'https://example.com/page.html': (301, 'text/html', b'',
                                                      {'Location': 'https://elsewhere.example.net/'})})
        r = net.run('fetch_page', self.base(approve_write=True))['result']
        self.assertEqual(r['status'], 'redirect_refused')
        self.assertIn('allow_list', r['reason'])
        net._LAST_HIT.clear()
        self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                    'https://example.com/page.html': (302, 'text/html', b'',
                                                      {'Location': 'http://example.com/page.html'})})
        r = net.run('fetch_page', self.base(approve_write=True, allow_http=True))['result']
        self.assertEqual(r['status'], 'redirect_refused')
        self.assertIn('downgrade', r['reason'])
        net._LAST_HIT.clear()
        opener = self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                             'https://example.com/page.html': (301, 'text/html', b'', {'Location': '/new.html'}),
                             'https://example.com/new.html': (200, 'text/html', PAGE)})
        r = net.run('fetch_page', self.base(approve_write=True))['result']
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['url'], 'https://example.com/new.html')
        self.assertEqual(r['redirects'][0]['to'], 'https://example.com/new.html')

    def test_too_many_redirects(self):
        routes = {'https://example.com/robots.txt': (404, 'text/plain', b'')}
        for i in range(8):
            routes[f'https://example.com/r{i}'] = (302, 'text/html', b'', {'Location': f'/r{i + 1}'})
        self.serve(routes)
        r = net.run('fetch_page', self.base(url='https://example.com/r0', approve_write=True))['result']
        self.assertEqual(r['status'], 'too_many_redirects')

    def test_page_size_cap(self):
        self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                    'https://example.com/page.html': (200, 'text/html', b'x',
                                                      {'Content-Length': str(net.PAGE_CAP + 1)})})
        r = net.run('fetch_page', self.base(approve_write=True))['result']
        self.assertEqual(r['status'], 'too_large')
        self.assertEqual(self.user_files(), [])


class TestFetchFile(NetCase):
    def routes(self, ctype, body, extra=None):
        return {'https://example.com/robots.txt': (404, 'text/plain', b''),
                'https://example.com/a.bin': (200, ctype, body, extra)}

    def test_png_saved_with_sniffed_extension(self):
        self.serve(self.routes('application/octet-stream', PNG))
        r = net.run('fetch_file', self.base(url='https://example.com/a.bin', approve_write=True,
                                            rights='owner', rights_note='my own picture'))['result']
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['sniffed_type'], 'image/png')
        self.assertTrue(r['file'].endswith('.png'))
        self.assertEqual(Path(r['file']).read_bytes(), PNG)
        rec = self.records()[-1]
        self.assertEqual(rec['rights'], 'owner')
        self.assertEqual(rec['saved_as'], [Path(r['file']).name])

    def test_refusals(self):
        cases = [('application/octet-stream', b'MZ' + b'\x00' * 100, 'refused_executable'),
                 ('application/octet-stream', b'<svg xmlns="x">' + b' ' * 80, 'refused_executable'),
                 ('application/octet-stream', b'\x00\x01' * 60, 'unrecognised_signature'),
                 ('image/svg+xml', PNG, 'wrong_content_type'),
                 ('text/html', PNG, 'wrong_content_type')]
        for ctype, body, outcome in cases:
            with self.subTest(outcome=outcome, ctype=ctype):
                net._LAST_HIT.clear()
                self.serve(self.routes(ctype, body))
                r = net.run('fetch_file', self.base(url='https://example.com/a.bin', approve_write=True))['result']
                self.assertEqual(r['status'], outcome)
                self.assertEqual(self.user_files(), [])

    def test_kind_filter_and_size_cap(self):
        self.serve(self.routes('image/png', PNG))
        r = net.run('fetch_file', self.base(url='https://example.com/a.bin', approve_write=True,
                                            kinds=['pdf']))['result']
        self.assertEqual(r['status'], 'wrong_content_type')
        net._LAST_HIT.clear()
        self.serve(self.routes('application/octet-stream', PNG))
        r = net.run('fetch_file', self.base(url='https://example.com/a.bin', approve_write=True,
                                            kinds=['pdf']))['result']
        self.assertEqual(r['status'], 'kind_not_allowed')
        net._LAST_HIT.clear()
        self.serve(self.routes('image/png', PNG))
        r = net.run('fetch_file', self.base(url='https://example.com/a.bin', approve_write=True,
                                            max_bytes=50))['result']
        self.assertEqual(r['status'], 'too_large')
        self.assertEqual(self.user_files(), [])
        with self.assertRaises(ValueError):
            net.run('fetch_file', self.base(kinds=['exe']))
        with self.assertRaises(ValueError):
            net.run('fetch_file', self.base(rights='owner'))          # rights_note missing
        with self.assertRaises(ValueError):
            net.run('fetch_file', self.base(max_bytes=net.FILE_CAP + 1))


class TestOutputGuard(NetCase):
    def test_guard_name(self):
        ok = net._guard_name(self.wd, 'clip.png', net.FILE_EXTS)
        self.assertEqual(ok.parent, self.wd)
        for bad in ('..\\escape.png', '../escape.png', 'x.exe', 'CON.png', 'x.png:ads'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    net._guard_name(self.wd, bad, net.FILE_EXTS)

    def test_safe_stems(self):
        self.assertEqual(net._safe_stem('../../etc/passwd'), 'etc-passwd')
        self.assertEqual(net._safe_stem('***'), 'item')
        self.assertEqual(net._safe_stem('صورة'), 'item')


class TestCrawlAndLinks(NetCase):
    def routes(self):
        return {'https://example.com/robots.txt': (200, 'text/plain', ROBOTS_OK),
                'https://example.com/page.html': (200, 'text/html', PAGE),
                'https://example.com/two.html': (200, 'text/html',
                                                 b'<html><title>Two</title><a href="/private/p.html">p</a></html>')}

    def test_crawl_site_same_origin_depth(self):
        opener = self.serve(self.routes())
        r = net.run('crawl_site', self.base(approve_write=True, max_depth=2, max_pages=10))['result']
        self.assertEqual(r['status'], 'ok')
        urls = [p['url'] for p in r['pages']]
        self.assertEqual(urls, ['https://example.com/page.html', 'https://example.com/two.html'])
        fetched = [c['url'] for c in opener.calls]
        self.assertNotIn('https://other.example.org/x', fetched)      # other origin
        self.assertNotIn('https://example.com/doc.pdf', fetched)      # non-HTML extension
        self.assertNotIn('https://example.com/pic.png', fetched)      # media
        self.assertNotIn('https://example.com/three.html', fetched)   # nofollow
        self.assertNotIn('https://example.com/private/p.html', fetched)  # robots
        self.assertEqual(fetched.count('https://example.com/robots.txt'), 1)
        self.assertTrue(any(s.get('outcome') == 'robots_disallowed' for s in r['skipped']))
        self.assertEqual(len([f for f in self.user_files() if f.endswith('.html')]), 2)

    def test_crawl_max_pages(self):
        self.serve(self.routes())
        r = net.run('crawl_site', self.base(approve_write=True, max_depth=2, max_pages=1,
                                            save_pages=False))['result']
        self.assertEqual(len(r['pages']), 1)
        self.assertEqual(r['stop_reason'], 'max_pages reached')
        self.assertEqual(self.user_files(), [])
        for bad in ({'max_depth': 4}, {'max_pages': 0}, {'max_pages': 201}):
            with self.assertRaises(ValueError):
                net.run('crawl_site', self.base(**bad))

    def test_collect_links_filters(self):
        self.serve(self.routes())
        r = net.run('collect_links', self.base(approve_write=True))['result']
        urls = {l['url'] for l in r['links']}
        self.assertIn('https://example.com/two.html', urls)
        self.assertIn('https://other.example.org/x', urls)
        self.assertFalse(any(u.startswith('mailto:') for u in urls))
        self.assertEqual(self.user_files(), [])          # save_page defaults to False
        net._LAST_HIT.clear()
        r = net.run('collect_links', self.base(approve_write=True, extensions=['.pdf']))['result']
        self.assertEqual([l['url'] for l in r['links']], ['https://example.com/doc.pdf'])
        net._LAST_HIT.clear()
        r = net.run('collect_links', self.base(approve_write=True, same_host_only=True,
                                               include_media=False, pattern=r'two|three'))['result']
        self.assertEqual(sorted(l['url'] for l in r['links']),
                         ['https://example.com/three.html', 'https://example.com/two.html'])
        with self.assertRaises(ValueError):
            net.run('collect_links', self.base(pattern='('))
        with self.assertRaises(ValueError):
            net.run('collect_links', self.base(extensions=['pdf']))

    def test_links_parser_base_href(self):
        links = net._links('<base href="https://example.com/dir/"><a href="x.html">x</a>'
                           '<a href="javascript:alert(1)">j</a><a href="#top">t</a>',
                           'https://example.com/')
        self.assertEqual([l['url'] for l in links], ['https://example.com/dir/x.html'])


class TestMediaAndGithub(NetCase):
    def media(self, **kw):
        p = {'url': 'https://example.com/v', 'allow_list': ['example.com'], 'work_dir': str(self.wd)}
        p.update(kw)
        return p

    def test_media_download_not_installed(self):
        with mock.patch.object(net.shutil, 'which', lambda n: None):
            with self.assertRaisesRegex(ValueError, 'yt-dlp was not found'):
                net.run('media_download', self.media(rights='owner', rights_note='my clip'))

    def test_media_download_gates(self):
        with self.assertRaisesRegex(ValueError, 'rights'):
            net.run('media_download', self.media())
        with self.assertRaisesRegex(ValueError, 'plain http'):
            net.run('media_download', self.media(url='http://example.com/v', rights='owner', rights_note='n'))
        with mock.patch.object(net.shutil, 'which', lambda n: 'C:/fake/yt-dlp.exe'):
            r = net.run('media_download', self.media(rights='licensed',
                                                     rights_note='CC licence from the author'))['result']
        self.assertEqual(r['status'], 'approval_required')
        cmd = r['plan']['command_preview']
        for flag in ('--ignore-config', '--no-cookies', '--no-cookies-from-browser', '--no-playlist'):
            self.assertIn(flag, cmd)
        self.assertFalse(any(x in cmd for x in ('--cookies', '--username', '--password', '--netrc')))
        self.assertEqual(cmd[-2:], ['--', 'https://example.com/v'])
        self.assertEqual(list(self.wd.iterdir()), [])

    def test_media_download_approved_with_fake_program(self):
        """subprocess.run is replaced by an in-memory fake: no program is started."""
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[1:] == ['--version']:
                return subprocess.CompletedProcess(cmd, 0, '2099.01.01\n', '')
            out_dir = Path(cmd[cmd.index('-P') + 1])
            (out_dir / 'My_clip-abc123.webm').write_bytes(b'\x1aE\xdf\xa3' + b'webm' + b'\x00' * 200)
            (out_dir / 'notes.txt').write_text('ignored', encoding='utf-8')
            return subprocess.CompletedProcess(cmd, 0, '', '')

        with mock.patch.object(net.shutil, 'which', lambda n: 'C:/fake/yt-dlp.exe' if n == 'yt-dlp' else None), \
                mock.patch.object(net.subprocess, 'run', fake_run):
            r = net.run('media_download', self.media(rights='owner', rights_note='my own upload',
                                                     approve_write=True))['result']
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(len(r['files']), 1)
        self.assertTrue(r['files'][0]['file'].endswith('.webm'))
        self.assertTrue(all(isinstance(c, list) for c in calls))
        self.assertNotIn('shell', str(calls))
        self.assertEqual(self.user_files(), ['My_clip-abc123.webm'])   # temp folder removed
        rec = self.records()[-1]
        self.assertEqual((rec['rights'], rec['outcome']), ('owner', 'ok'))

    def test_media_download_program_fails_to_start(self):
        def fake_run(cmd, **kw):
            if cmd[1:] == ['--version']:
                return subprocess.CompletedProcess(cmd, 0, 'x', '')
            raise FileNotFoundError('gone')

        with mock.patch.object(net.shutil, 'which', lambda n: 'C:/fake/yt-dlp.exe' if n == 'yt-dlp' else None), \
                mock.patch.object(net.subprocess, 'run', fake_run):
            r = net.run('media_download', self.media(rights='owner', rights_note='n',
                                                     approve_write=True))['result']
        self.assertEqual(r['status'], 'failed')
        self.assertIn('could not start', r['stderr_tail'])
        self.assertEqual(self.user_files(), [])

    def test_mp4_without_ffprobe_is_not_delivered(self):
        def fake_run(cmd, **kw):
            if cmd[1:] == ['--version']:
                return subprocess.CompletedProcess(cmd, 0, 'x', '')
            out_dir = Path(cmd[cmd.index('-P') + 1])
            (out_dir / 'clip-1.mp4').write_bytes(b'\x00\x00\x00\x18ftypisom' + b'\x00' * 100)
            return subprocess.CompletedProcess(cmd, 0, '', '')

        with mock.patch.object(net.shutil, 'which', lambda n: 'C:/fake/yt-dlp.exe' if n == 'yt-dlp' else None), \
                mock.patch.object(net.subprocess, 'run', fake_run):
            r = net.run('media_download', self.media(rights='owner', rights_note='n',
                                                     approve_write=True))['result']
        self.assertEqual(r['status'], 'failed')
        self.assertIn('ffprobe not found', r['problems'][0]['reason'])
        self.assertEqual(self.user_files(), [])

    def test_github_repo_info_offline(self):
        api = 'https://api.github.com/repos/python/cpython'
        body = json.dumps({'full_name': 'python/cpython', 'stargazers_count': 1,
                           'license': {'spdx_id': 'PSF-2.0'}}).encode()
        opener = self.serve({api: (200, 'application/json; charset=utf-8', body),
                             api + '/languages': (200, 'application/json', b'{"Python": 10}')})
        r = net.run('github_repo_info', {'owner': 'python', 'repo': 'cpython', 'work_dir': str(self.wd),
                                         'approve_write': True, 'include_languages': True})['result']
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['repo']['license'], 'PSF-2.0')
        self.assertEqual(r['languages'], {'Python': 10})
        self.assertNotIn('https://api.github.com/robots.txt', [c['url'] for c in opener.calls])
        saved = json.loads(Path(r['file']).read_text(encoding='utf-8'))
        self.assertEqual(saved['repo']['full_name'], 'python/cpython')
        self.assertEqual(len(self.records()), 2)
        for bad in ({'owner': '../x', 'repo': 'r'}, {'owner': 'a', 'repo': '..'}, {'owner': 'a'}):
            with self.assertRaises(ValueError):
                net.run('github_repo_info', dict(bad, work_dir=str(self.wd)))

    def test_github_rate_limit_reported(self):
        api = 'https://api.github.com/repos/python/cpython'
        self.serve({api: (403, 'application/json', b'{}', {'X-RateLimit-Remaining': '0'})})
        r = net.run('github_repo_info', {'owner': 'python', 'repo': 'cpython', 'work_dir': str(self.wd),
                                         'approve_write': True})['result']
        self.assertEqual(r['http_status'], 403)
        self.assertEqual(r['rate_limit_headers'].get('X-RateLimit-Remaining'), '0')


class TestSources(NetCase):
    def test_sources_log(self):
        r = net.run('sources', {'work_dir': str(self.wd)})['result']
        self.assertFalse(r['exists'])
        self.assertEqual(r['records'], [])
        lines = [json.dumps({'kind': 'robots', 'url': 'u1'}), 'not json', json.dumps([1]),
                 json.dumps({'kind': 'page', 'url': 'u2'}), json.dumps({'kind': 'page', 'url': 'u3'})]
        (self.wd / 'sources.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        r = net.run('sources', {'work_dir': str(self.wd), 'kind': 'page', 'limit': 1})['result']
        self.assertEqual(r['records'], [{'kind': 'page', 'url': 'u3'}])
        self.assertEqual(r['matching'], 2)
        self.assertEqual(r['malformed_lines'], 2)
        with self.assertRaises(ValueError):
            net.run('sources', {'work_dir': str(self.wd), 'kind': 'cookie'})

    def test_sources_jsonl_must_be_regular_file(self):
        (self.wd / 'sources.jsonl').mkdir()
        self.serve({'https://example.com/robots.txt': (404, 'text/plain', b''),
                    'https://example.com/page.html': (200, 'text/html', PAGE)})
        with self.assertRaises(RuntimeError):
            net.run('fetch_page', self.base(approve_write=True))
        self.assertFalse(any(p.suffix == '.part' for p in self.wd.iterdir()))


if __name__ == '__main__':
    unittest.main()
