"""Tests for web_offline_v23 (topics 22.01-22.10): offline web building blocks."""
import ast
import hashlib
import inspect
import json
import time
import unittest

import web_offline_v23 as W

FORBIDDEN_IMPORTS = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
STDLIB_OK = {'__future__', 'hashlib', 'json', 'random', 're', 'unicodedata', 'datetime', 'decimal', 'html'}


class TestInterface(unittest.TestCase):
    def test_topics_ops_names(self):
        self.assertEqual(list(W.TOPICS), [f'22.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(W.TOPICS.values()), set(W.OPS))
        self.assertEqual(set(W.TOPIC_NAMES_AR), set(W.TOPICS))

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(W))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or '').split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print', '__import__'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)
        self.assertLessEqual(imported, STDLIB_OK)

    def test_every_op_runs_with_defaults(self):
        for op in W.OPS:
            with self.subTest(op=op):
                start = time.perf_counter()
                out = W.run(op, {})
                self.assertLess(time.perf_counter() - start, 3.0)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                json.dumps(out, allow_nan=False)
                self.assertTrue(out['assumptions'])
                self.assertIn(W.OFFLINE_LIMIT, out['limits'])
                self.assertIn(W.REFUSAL_LIMIT, out['limits'])

    def test_bad_calls_raise_value_error(self):
        with self.assertRaises(ValueError):
            W.run('not_an_op', {})
        with self.assertRaises(ValueError):
            W.run('html_text', [])
        for op in W.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    W.run(op, {'shell': 'rm -rf /'})

    def test_sensitive_parameters_refused(self):
        for key in ('cookies', 'password', 'login', 'captcha_solution', 'session_id', 'auth_token'):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'refused'):
                    W.run('html_text', {key: 'x'})
        with self.assertRaisesRegex(ValueError, 'credentials'):
            W.run('source_link', {'results': [{'url': 'https://user:pw@example.com/', 'title': 't',
                                               'retrieved_at': '2026-01-01', 'content': 'x'}]})

    def test_missing_required_inputs(self):
        cases = [('permitted_extract', {'allow_list': ['example.com']}),
                 ('crawl_policy', {'seeds': ['https://example.com/']}),
                 ('oem_normalise', {'supersessions': []}),
                 ('price_records', {'records': []}),
                 ('source_link', {'later_copies': []}),
                 ('export_json', {'records': []}),
                 ('data_licence', {'intended_uses': ['store']})]
        for op, params in cases:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    W.run(op, params)


class TestPermittedExtract(unittest.TestCase):  # 22.01
    def test_approved_processed_unapproved_refused(self):
        out = W.run('permitted_extract', {
            'allow_list': ['example.com/docs', '*.parts.example'],
            'pages': [{'url': 'https://example.com/docs/a', 'html': '<h1>A</h1><p>Hello</p>',
                       'fetched_at': '2026-11-20T10:00:00Z'},
                      {'url': 'https://shop.parts.example/x', 'html': '<p>Pads</p>',
                       'fetched_at': '2026-11-20T10:00:00Z'},
                      {'url': 'https://evil.example.org/docs/a', 'html': '<p>No</p>',
                       'fetched_at': '2026-11-20T10:00:00Z'},
                      {'url': 'https://example.com/docsx', 'html': '<p>No</p>',
                       'fetched_at': '2026-11-20T10:00:00Z'}]})['result']
        self.assertEqual([p['index'] for p in out['processed']], [0, 1])
        self.assertIn('Hello', out['processed'][0]['text'])
        self.assertEqual([r['index'] for r in out['refused']], [2, 3])
        self.assertIn('allow-list', out['refused'][0]['reason'])

    def test_login_captcha_and_403_refused_personal_data_redacted(self):
        page = lambda html, status=None: {'url': 'https://example.com/p', 'html': html,
                                          'fetched_at': '2026-11-20', **({'status': status} if status else {})}
        out = W.run('permitted_extract', {'allow_list': ['example.com'], 'pages': [
            page('<form><input type="password" name="pw"></form>'),
            page('<div class="g-recaptcha"></div>'),
            page('<p>secret</p>', 403),
            page('<p>Mail a@b.com or call +20 100 123 4567. Part 0986494524</p>')]})['result']
        self.assertEqual(len(out['refused']), 3)
        text = out['processed'][0]['text']
        self.assertNotIn('a@b.com', text)
        self.assertNotIn('123 4567', text)
        self.assertIn('0986494524', text)
        self.assertEqual(out['processed'][0]['redacted'], {'emails': 1, 'phones': 1})

    def test_default_example(self):
        res = W.run('permitted_extract')['result']
        self.assertEqual(res['approved_count'], 1)
        self.assertEqual(res['refused_count'], 1)
        self.assertEqual(res['processed'][0]['url'], 'https://example.com/docs/brakes')


class TestCrawlPolicy(unittest.TestCase):  # 22.02
    ROBOTS = ('User-agent: *\nDisallow: /private/\nAllow: /private/open\nCrawl-delay: 7\n\n'
              'User-agent: RedRoseBot\nUser-agent: other\nDisallow: /tmp\nAllow: /tmp/ok$\nCrawl-delay: 4\n')

    def test_disallowed_excluded_and_intervals_respect_delay(self):
        graph = {'https://example.com/': ['https://example.com/a', 'https://example.com/tmp/x',
                                          'https://example.com/tmp/ok', 'https://example.com/private/y']}
        out = W.run('crawl_policy', {'robots_txt': self.ROBOTS, 'site': 'https://example.com',
                                     'user_agent': 'RedRoseBot/1.0', 'link_graph': graph,
                                     'max_requests_per_minute': 60})['result']
        urls = [s['url'] for s in out['scheduled']]
        self.assertEqual(out['robots_group'], 'redrosebot')
        self.assertNotIn('https://example.com/tmp/x', urls)
        self.assertIn('https://example.com/tmp/ok', urls)
        self.assertIn('https://example.com/private/y', urls)  # '*' group does not apply to RedRoseBot
        self.assertTrue(any(e['url'] == 'https://example.com/tmp/x' and 'robots' in e['reason']
                            for e in out['excluded']))
        self.assertEqual(out['crawl_delay_s'], 4)
        gaps = [b['at_s'] - a['at_s'] for a, b in zip(out['scheduled'], out['scheduled'][1:])]
        self.assertTrue(gaps and min(gaps) >= 4 - 1e-9)

    def test_longest_match_and_rate_limit(self):
        out = W.run('crawl_policy', {'robots_txt': self.ROBOTS, 'site': 'https://example.com',
                                     'user_agent': 'Unknown', 'max_requests_per_minute': 2,
                                     'seeds': ['https://example.com/private/open', 'https://example.com/private/z',
                                               'https://example.com/b']})['result']
        urls = [s['url'] for s in out['scheduled']]
        self.assertIn('https://example.com/private/open', urls)
        self.assertNotIn('https://example.com/private/z', urls)
        self.assertEqual(out['interval_s'], 30.0)  # 60/2 > crawl delay 7
        self.assertGreaterEqual(out['min_gap_s'], 30.0 - 1e-9)

    def test_depth_and_page_limits(self):
        graph = {'https://example.com/': ['https://example.com/1'],
                 'https://example.com/1': ['https://example.com/2'],
                 'https://example.com/2': ['https://example.com/3']}
        out = W.run('crawl_policy', {'robots_txt': '', 'site': 'https://example.com', 'link_graph': graph,
                                     'max_depth': 1})['result']
        self.assertEqual([s['url'] for s in out['scheduled']], ['https://example.com/', 'https://example.com/1'])
        self.assertTrue(any(e['reason'] == 'beyond max_depth' for e in out['excluded']))
        out = W.run('crawl_policy', {'robots_txt': '', 'site': 'https://example.com', 'link_graph': graph,
                                     'max_pages': 2, 'max_depth': 5})['result']
        self.assertEqual(len(out['scheduled']), 2)


class TestOem(unittest.TestCase):  # 22.03
    def test_leading_zero_kept(self):
        out = W.run('oem_normalise', {'parts': [
            {'id': 1, 'manufacturer': 'Bosch', 'number': '0 986-494 524'},
            {'id': 2, 'manufacturer': 'bosch ', 'number': '0986494524'},
            {'id': 3, 'manufacturer': 'Bosch', 'number': '986494524'},
            {'id': 4, 'manufacturer': 'Bosch', 'number': '٠٩٨٦.٤٩٤.٥٢٤'},
            {'id': 5, 'manufacturer': 'Valeo', 'number': '0986494524'}]})['result']
        norm = {p['id']: p['normalised'] for p in out['parts']}
        self.assertEqual(norm['1'], '0986494524')
        self.assertEqual(norm['3'], '986494524')
        groups = [sorted(g['ids']) for g in out['alternates']]
        self.assertIn(['1', '2', '4'], groups)
        self.assertIn(['3'], groups)
        self.assertIn(['5'], groups)

    def test_supersession_chain_and_errors(self):
        out = W.run('oem_normalise', {'parts': [{'id': 'x', 'manufacturer': 'M', 'number': 'A-1'}],
                                      'supersessions': [{'manufacturer': 'M', 'old': 'A1', 'new': 'A2'},
                                                        {'manufacturer': 'm', 'old': 'A.2', 'new': 'A3'}]})['result']
        self.assertEqual(out['parts'][0]['current'], 'A3')
        self.assertEqual(out['parts'][0]['chain'], ['A1', 'A2', 'A3'])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            W.run('oem_normalise', {'parts': [{'manufacturer': 'M', 'number': 'A1'}],
                                    'supersessions': [{'manufacturer': 'M', 'old': 'A1', 'new': 'A2'},
                                                      {'manufacturer': 'M', 'old': 'A2', 'new': 'A1'}]})
        with self.assertRaisesRegex(ValueError, 'leading zeros'):
            W.run('oem_normalise', {'parts': [{'manufacturer': 'M', 'number': 986494524}]})


class TestPrices(unittest.TestCase):  # 22.04
    BASE = {'now': '2026-11-21T12:00:00Z', 'max_age_days': 7}

    def rec(self, **kw):
        r = {'id': kw.pop('id', 'r'), 'value': '10.00', 'currency': 'USD', 'source_url': 'https://s.example/p',
             'observed_at': '2026-11-20T00:00:00Z'}
        r.update(kw)
        return {k: v for k, v in r.items() if v is not None}

    def test_undated_and_stale_rejected(self):
        out = W.run('price_records', {**self.BASE, 'records': [
            self.rec(id='ok'), self.rec(id='nodate', observed_at=None),
            self.rec(id='old', observed_at='2026-10-01T00:00:00Z'),
            self.rec(id='future', observed_at='2026-12-01T00:00:00Z'),
            self.rec(id='float', value=10.5)]})['result']
        self.assertEqual([a['id'] for a in out['accepted']], ['ok'])
        reasons = {r['id']: r['reason'] for r in out['rejected']}
        self.assertIn('timestamp', reasons['nodate'])
        self.assertIn('stale', reasons['old'])
        self.assertIn('future', reasons['future'])
        self.assertIn('decimal string', reasons['float'])

    def test_currency_mismatch_without_rate_refused(self):
        out = W.run('price_records', {**self.BASE, 'target_currency': 'EGP', 'records': [
            self.rec(id='usd'), self.rec(id='eur', currency='EUR')],
            'fx_rates': [{'base': 'EGP', 'quote': 'USD', 'rate': '0.02', 'as_of': '2026-11-19'}]})['result']
        self.assertEqual([r['id'] for r in out['refused']], ['eur'])
        usd = out['accepted'][0]
        self.assertEqual(usd['converted_value'], '500.00')  # 10 / 0.02 via inverse rate
        self.assertTrue(usd['fx']['inverted'])

    def test_stale_rate_not_used_and_bad_currency(self):
        out = W.run('price_records', {**self.BASE, 'target_currency': 'EGP', 'records': [self.rec()],
                                      'fx_rates': [{'base': 'USD', 'quote': 'EGP', 'rate': '48',
                                                    'as_of': '2026-01-01'}]})['result']
        self.assertEqual(len(out['refused']), 1)
        out = W.run('price_records', {**self.BASE, 'records': [self.rec(currency='XYZ')]})['result']
        self.assertIn('ISO-4217', out['rejected'][0]['reason'])


class TestHtmlText(unittest.TestCase):  # 22.05
    def test_malformed_page_yields_text_without_script(self):
        html = ('<html><head><style>.x{}</style><title>T &amp; U</title></head><body>'
                '<h2>Title <b>bold</b></h2><p>One &lt;two&gt; &eacute;<p>Para<div><span>Unclosed'
                '<script>alert("SECRET_JS")</script><noscript>NOSCRIPT_TXT</noscript>'
                '<template>TPL_TXT</template></table></b></i><p>End')
        res = W.run('html_text', {'html': html})['result']
        self.assertIn('One <two> é', res['text'])
        self.assertIn('End', res['text'])
        for hidden in ('SECRET_JS', 'NOSCRIPT_TXT', 'TPL_TXT', '.x{}'):
            self.assertNotIn(hidden, res['text'])
        self.assertEqual(res['title'], 'T & U')
        self.assertEqual(res['headings'], [{'level': 2, 'text': 'Title bold'}])
        self.assertIn('\n\n', res['text'])
        self.assertFalse(res['javascript_evaluated'])

    def test_unclosed_script_and_garbage(self):
        res = W.run('html_text', {'html': '<p>Visible<script>var a = "<p>HIDDEN"'})['result']
        self.assertIn('Visible', res['text'])
        self.assertNotIn('HIDDEN', res['text'])
        for junk in ('<<<>>>', '</p></p><![CDATA[x', '<a href="x', '&#99999999;&bogus;', '<!--'):
            W.run('html_text', {'html': junk})

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            W.run('html_text', {'html': 'x' * (W.MAX_TEXT_BYTES + 1)})


class TestSourceLink(unittest.TestCase):  # 22.06
    def test_canonical_and_verification(self):
        out = W.run('source_link', {
            'results': [{'url': 'HTTPS://WWW.Example.com:443/Path?a=1&utm_source=x&UTM_Medium=y&gclid=z#frag',
                         'title': 'Page', 'retrieved_at': '2026-11-20T10:00:00+02:00', 'content': 'Price 10'}],
            'later_copies': [{'url': 'https://www.example.com/Path?a=1', 'content': 'Price 10'},
                             {'url': 'https://www.example.com/Path?a=1#x', 'content': 'Price 11'},
                             {'url': 'https://other.example/', 'content': 'Price 10'}]})['result']
        c = out['citations'][0]
        self.assertEqual(c['url'], 'https://www.example.com/Path?a=1')
        self.assertEqual(sorted(c['removed_params']), ['UTM_Medium', 'gclid', 'utm_source'])
        self.assertEqual(c['retrieved_at'], '2026-11-20T08:00:00Z')
        self.assertEqual([v['status'] for v in out['verifications']],
                         ['verified', 'content_changed', 'no_citation'])
        self.assertFalse(out['verifications'][1]['verified'])


class TestDedupe(unittest.TestCase):  # 22.07
    def test_spacing_dedupes_numbers_protect(self):
        base = 'Front brake pad set for compact cars, fits many models, part 0986494524 price 1250 EGP today'
        out = W.run('dedupe_content', {'records': [
            {'id': 'a', 'text': base},
            {'id': 'b', 'text': '  FRONT brake pad   set for compact cars,\nfits many models, part 0986494524 price 1250 EGP today '},
            {'id': 'c', 'text': base.replace('0986494524', '0986494525')},
            {'id': 'd', 'text': base.replace('1250', '1350')},
            {'id': 'e', 'text': 'Completely different text about oil filters and engines'}]})['result']
        clusters = sorted(sorted(c) for c in out['clusters'])
        self.assertIn(['a', 'b'], clusters)
        self.assertIn(['c'], clusters)
        self.assertIn(['d'], clusters)
        apart = {(k['a'], k['b']) for k in out['kept_apart']}
        self.assertIn(('a', 'c'), apart)
        self.assertIn(('a', 'd'), apart)

    def test_near_duplicate_merges_without_numbers(self):
        t1 = ('the quick brown fox jumps over the lazy dog while the farmer watches from the old red barn '
              'and the children laugh in the green field near the river bank')
        t2 = t1 + ' again'
        out = W.run('dedupe_content', {'records': [{'id': 1, 'text': t1}, {'id': 2, 'text': t2}],
                                       'max_hamming': 16, 'min_jaccard': 0.8})['result']
        self.assertEqual(sorted(map(sorted, out['clusters'])), [['1', '2']])
        self.assertEqual(out['merged_pairs'][0]['reason'], 'near duplicate')


class TestRetry(unittest.TestCase):  # 22.08
    def test_403_stops(self):
        out = W.run('retry_policy', {'events': [{'status': 403}, {'status': 503}]})['result']
        self.assertEqual(out['decisions'][0]['action'], 'stop')
        self.assertEqual(out['decisions'][1]['action'], 'ignored')
        self.assertTrue(out['stopped'])
        self.assertTrue(out['report'])

    def test_429_waits_retry_after(self):
        out = W.run('retry_policy', {'events': [{'status': 429, 'retry_after': '120'}]})['result']
        d = out['decisions'][0]
        self.assertEqual(d['action'], 'stop_and_wait')
        self.assertGreaterEqual(d['delay_s'], 120)
        out = W.run('retry_policy', {'events': [{'status': 429, 'retry_after': 'Sat, 21 Nov 2026 12:05:00 GMT'}],
                                     'now': '2026-11-21T12:00:00Z'})['result']
        self.assertGreaterEqual(out['decisions'][0]['delay_s'], 300)
        out = W.run('retry_policy', {'events': [{'status': 429}] * 3})['result']
        self.assertEqual([d['action'] for d in out['decisions']], ['stop_and_wait', 'stop_and_wait', 'stop'])

    def test_503_backoff_grows_and_caps(self):
        out = W.run('retry_policy', {'events': [{'status': 503}] * 9, 'max_attempts': 10, 'base_delay_s': 1,
                                     'max_delay_s': 10, 'seed': 7})['result']
        delays = out['retry_delays_s']
        self.assertEqual(len(delays), 9)
        self.assertTrue(all(b >= a for a, b in zip(delays, delays[1:])))
        self.assertTrue(all(b > a for a, b in zip(delays[:3], delays[1:4])))
        self.assertLessEqual(max(delays), 10)
        self.assertEqual(delays[-1], 10)
        again = W.run('retry_policy', {'events': [{'status': 503}] * 9, 'max_attempts': 10, 'base_delay_s': 1,
                                       'max_delay_s': 10, 'seed': 7})['result']['retry_delays_s']
        self.assertEqual(delays, again)

    def test_budget_timeouts_and_non_retryable(self):
        out = W.run('retry_policy', {'events': [{'error': 'timeout'}] * 3, 'max_attempts': 3})['result']
        self.assertEqual([d['action'] for d in out['decisions']], ['retry', 'retry', 'stop'])
        for ev in ({'status': 404}, {'status': 401}, {'error': 'tls_error'}, {'status': 501}):
            with self.subTest(ev=ev):
                self.assertEqual(W.run('retry_policy', {'events': [ev]})['result']['decisions'][0]['action'], 'stop')
        out = W.run('retry_policy', {'events': [{'status': 503, 'retry_after': 30}]})['result']
        self.assertGreaterEqual(out['decisions'][0]['delay_s'], 30)


class TestExport(unittest.TestCase):  # 22.09
    SCHEMA = {'version': '2', 'source_field': 'src',
              'fields': {'name': {'type': 'string', 'required': True},
                         'qty': {'type': 'integer'},
                         'src': {'type': 'url', 'required': True}}}

    def test_no_silent_loss_and_required(self):
        recs = [{'name': 'a', 'qty': 1, 'src': 'https://e.example/1', 'extra': 'kept?'},
                {'qty': 2, 'src': 'https://e.example/2'},
                {'name': 'c', 'qty': True, 'src': 'https://e.example/3'}]
        out = W.run('export_json', {'schema': self.SCHEMA, 'records': recs})['result']
        self.assertEqual(out['manifest']['count'], 0)  # undeclared field rejects by default
        self.assertEqual(len(out['rejected']), 3)
        self.assertTrue(any('missing required' in e for e in out['rejected'][1]['errors']))
        out = W.run('export_json', {'schema': self.SCHEMA, 'records': recs, 'drop_undeclared': True})['result']
        self.assertEqual(out['manifest']['count'], 1)
        self.assertEqual(out['manifest']['dropped_fields'], [{'index': 0, 'fields': ['extra']}])
        data = json.loads(out['json'])
        self.assertEqual(data, [{'name': 'a', 'qty': 1, 'src': 'https://e.example/1'}])
        self.assertEqual(out['manifest']['sha256'], hashlib.sha256(out['json'].encode('utf-8')).hexdigest())
        self.assertEqual(out['manifest']['schema_version'], '2')

    def test_schema_needs_source_link(self):
        bad = {**self.SCHEMA, 'source_field': 'name'}
        with self.assertRaisesRegex(ValueError, 'source'):
            W.run('export_json', {'schema': bad, 'records': [{'name': 'x', 'src': 'https://e.example'}]})


class TestLicence(unittest.TestCase):  # 22.10
    def test_cc_by_allows_redistribution_with_attribution(self):
        out = W.run('data_licence', {'licence_id': 'CC BY 4.0', 'intended_uses': ['redistribute']})['result']
        self.assertTrue(out['uses']['redistribute']['allowed'])
        self.assertIn('attribution', out['conditions'])
        self.assertIn('attribution', out['decisions']['redistribute'])
        self.assertFalse(out['refused'])

    def test_all_rights_reserved_no_scraping_blocks_store(self):
        out = W.run('data_licence', {'terms_text': 'Copyright 2026. All rights reserved. No scraping.',
                                     'intended_uses': ['store']})['result']
        self.assertFalse(out['uses']['store']['allowed'])
        self.assertTrue(out['protected_database'])
        self.assertTrue(out['refused'])
        self.assertIn('refused', out['decisions']['store'])

    def test_unknown_and_override(self):
        out = W.run('data_licence', {'licence_id': 'Some-Custom-Licence'})['result']
        self.assertFalse(out['recognised'])
        self.assertFalse(any(out['uses'][u]['allowed'] for u in ('quote', 'store', 'redistribute', 'commercial')))
        out = W.run('data_licence', {'licence_id': 'CC-BY-4.0',
                                     'terms_text': 'You may not extract or re-utilise the database.'})['result']
        self.assertFalse(out['uses']['store']['allowed'])
        self.assertTrue(out['protected_database'])
        out = W.run('data_licence', {'licence_id': 'CC-BY-NC-4.0'})['result']
        self.assertFalse(out['uses']['commercial']['allowed'])
        out = W.run('data_licence', {'terms_text': 'جميع الحقوق محفوظة. يمنع النسخ'})['result']
        self.assertFalse(out['uses']['store']['allowed'])


if __name__ == '__main__':
    unittest.main()
