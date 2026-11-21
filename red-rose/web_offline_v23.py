"""Red Rose V23: offline building blocks for a future, owner-approved web capability.

Pure standard-library Python. This module NEVER performs network access: it does not
fetch pages, resolve hosts or open sockets. Every op works only on page text,
headers and records that the caller supplies as parameters. A future capability that
actually fetches pages needs explicit owner approval and its own review.

No file I/O, no subprocess, no printing. Every op validates its inputs strictly
(ValueError on wrong types, unknown parameter names and out-of-range values), caps
its work (page text <= 2 MB, bounded record counts) and is deterministic.

Out of scope and refused: logins, cookies, credentials, CAPTCHAs, paywall bypass and
collecting personal data. Each op returns its assumptions and limits next to its result.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from html.parser import HTMLParser

MAX_PARAMS = 24
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 500
MAX_URL = 2048

TOPICS = {
    '22.01': 'permitted_extract',
    '22.02': 'crawl_policy',
    '22.03': 'oem_normalise',
    '22.04': 'price_records',
    '22.05': 'html_text',
    '22.06': 'source_link',
    '22.07': 'dedupe_content',
    '22.08': 'retry_policy',
    '22.09': 'export_json',
    '22.10': 'data_licence',
}

TOPIC_NAMES_AR = {
    '22.01': 'استخراج بيانات موقع مأذون',
    '22.02': 'ملاحقة صفحات مفهرسة',
    '22.03': 'توحيد أرقام قطع الغيار',
    '22.04': 'تجميع أسعار موثوقة',
    '22.05': 'استخراج نص من HTML',
    '22.06': 'ربط نتائج البحث بالأصل',
    '22.07': 'كشف المحتوى المكرر',
    '22.08': 'معالجة أخطاء الاتصال',
    '22.09': 'تصدير تجميعة JSON',
    '22.10': 'تقييم ترخيص البيانات',
}

OFFLINE_LIMIT = ('offline only: never performs network access; works only on page text, headers '
                 'and records supplied as parameters (a future fetching capability needs explicit '
                 'owner approval and a separate review)')
REFUSAL_LIMIT = ('refuses logins, cookies, credentials, CAPTCHAs, paywall bypass and '
                 'personal-data collection')


# --------------------------------------------------------------------------- validation

_SENSITIVE_KEY = re.compile(
    r'(?:^|_)(?:cookies?|set_cookie|password|passwd|login|credentials?|captcha|session|session_id|'
    r'auth|authorization|token|access_token|api_key|apikey|secret|paywall|bypass)(?:$|_)')


def _refuse_keys(keys, where):
    for key in keys:
        if isinstance(key, str) and _SENSITIVE_KEY.search(key.lower().replace('-', '_')):
            raise ValueError(f'refused: {where} contains {key!r}; logins, cookies, credentials, '
                             'CAPTCHAs and paywall bypass are out of scope')


def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _str(value, name, max_len=10_000, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    return value


def _text(value, name, allow_empty=True):
    value = _str(value, name, MAX_TEXT_BYTES, allow_empty=allow_empty)
    if len(value.encode('utf-8')) > MAX_TEXT_BYTES:
        raise ValueError(f'{name} must be at most {MAX_TEXT_BYTES} bytes of UTF-8')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _num(value, low, high, name, *, low_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value \
            or value in (float('inf'), float('-inf')):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high or (low_open and value <= low):
        raise ValueError(f'{name} must be in {"(" if low_open else "["}{low}, {high}]')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _list(value, name, max_len, min_len=0):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{name} must be a list')
    if not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must have {min_len}..{max_len} items')
    return list(value)


def _dict(value, name, allowed, required=()):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object/dict')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    _refuse_keys(value, name)
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f'{name} has unknown field(s): {", ".join(sorted(unknown))}')
    missing = [k for k in required if value.get(k) is None]
    if missing:
        raise ValueError(f'{name} is missing required field(s): {", ".join(missing)}')
    return value


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits) + [OFFLINE_LIMIT, REFUSAL_LIMIT]}


def _sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '0123456789' * 2)


# --------------------------------------------------------------------------- time

def _ts(value, name):
    s = _str(value, name, 64).strip()
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f'{name} must be an ISO-8601 date/time, e.g. 2026-11-21T10:00:00Z') from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt):
    return dt.isoformat().replace('+00:00', 'Z')


# --------------------------------------------------------------------------- URLs (own splitter)

_URL_RE = re.compile(r'^(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*)://(?P<authority>[^/?#]*)'
                     r'(?P<path>[^?#]*)(?:\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?$', re.S)
_HOST_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$')
_PCT = re.compile(r'%[0-9a-fA-F]{2}')
_TRACKING = {'fbclid', 'gclid', 'dclid', 'gbraid', 'wbraid', 'msclkid', 'mc_cid', 'mc_eid', 'yclid',
             'igshid', '_ga', '_gl', 'twclid', 'ttclid', 'li_fat_id', 's_cid', 'ref_src'}


def _host(raw, name):
    host = raw.strip().rstrip('.').lower()
    if host.startswith('[') and host.endswith(']'):
        if not re.fullmatch(r'\[[0-9a-f:.]{2,45}\]', host):
            raise ValueError(f'{name} has an invalid IPv6 host')
        return host
    try:
        host = host.encode('idna').decode('ascii')
    except (UnicodeError, ValueError):
        raise ValueError(f'{name} has an invalid host name') from None
    if not host or len(host) > 253 or not _HOST_RE.match(host):
        raise ValueError(f'{name} has an invalid host name')
    return host


def _url(value, name):
    """Split an http(s) URL into normalised parts. Refuses credentials in the URL."""
    s = _str(value, name, MAX_URL).strip()
    if re.search(r'[\s\x00-\x1f\x7f]', s):
        raise ValueError(f'{name} must not contain whitespace or control characters')
    m = _URL_RE.match(s)
    if not m:
        raise ValueError(f'{name} must be an absolute http(s) URL')
    scheme = m.group('scheme').lower()
    if scheme not in ('http', 'https'):
        raise ValueError(f'{name} must use http or https')
    authority = m.group('authority')
    if '@' in authority:
        raise ValueError(f'refused: {name} embeds credentials (user@host); logins are out of scope')
    port = None
    pm = re.match(r'^(.*?)(?::(\d{1,5}))?$', authority) if not authority.startswith('[') else \
        re.match(r'^(\[[^\]]*\])(?::(\d{1,5}))?$', authority)
    if not pm:
        raise ValueError(f'{name} has an invalid host/port')
    host = _host(pm.group(1), name)
    if pm.group(2):
        port = int(pm.group(2))
        if not 1 <= port <= 65535:
            raise ValueError(f'{name} has an invalid port')
        if (scheme, port) in (('http', 80), ('https', 443)):
            port = None
    path = _PCT.sub(lambda x: x.group(0).upper(), m.group('path') or '/')
    query = m.group('query')
    if query is not None:
        query = _PCT.sub(lambda x: x.group(0).upper(), query)
    return {'scheme': scheme, 'host': host, 'port': port, 'path': path,
            'query': query, 'fragment': m.group('fragment')}


def _unsplit(p, with_fragment=False):
    out = f"{p['scheme']}://{p['host']}" + (f":{p['port']}" if p['port'] else '') + p['path']
    if p['query']:
        out += '?' + p['query']
    if with_fragment and p['fragment']:
        out += '#' + p['fragment']
    return out


def _strip_tracking(query):
    if not query:
        return None, []
    kept, removed = [], []
    for part in query.split('&'):
        if not part:
            continue
        key = part.split('=', 1)[0].lower()
        if key.startswith('utm_') or key in _TRACKING:
            removed.append(part.split('=', 1)[0])
        else:
            kept.append(part)
    return ('&'.join(kept) or None), removed


def _canonical(value, name):
    p = _url(value, name)
    p['query'], removed = _strip_tracking(p['query'])
    p['fragment'] = None
    return _unsplit(p), removed, p


# --------------------------------------------------------------------------- HTML text parser

_SKIP_TAGS = {'script', 'style', 'noscript', 'template'}
_PARA_TAGS = {'p', 'div', 'section', 'article', 'header', 'footer', 'main', 'aside', 'nav',
              'blockquote', 'pre', 'table', 'ul', 'ol', 'dl', 'form', 'figure', 'hr',
              'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_LINE_TAGS = {'br', 'li', 'tr', 'dt', 'dd', 'figcaption', 'caption'}
_HEADINGS = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 4, 'h5': 5, 'h6': 6}


class _TextParser(HTMLParser):
    def __init__(self, max_links):
        super().__init__(convert_charrefs=True)
        self.parts, self.headings, self.title_parts, self.links = [], [], [], []
        self.skip = 0
        self.in_title = False
        self.heading = None
        self.max_links = max_links
        self.skipped_blocks = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
            self.skipped_blocks += 1
            return
        if self.skip:
            return
        if tag == 'title':
            self.in_title = True
        elif tag in _PARA_TAGS:
            self.parts.append('\n\n')
        elif tag in _LINE_TAGS:
            self.parts.append('\n')
            if tag == 'li':
                self.parts.append('- ')
        if tag in _HEADINGS:
            self.heading = (_HEADINGS[tag], len(self.parts))
            self.parts.append('#' * _HEADINGS[tag] + ' ')
        if tag == 'a' and len(self.links) < self.max_links:
            href = dict(attrs).get('href')
            if isinstance(href, str) and href.strip():
                self.links.append(href.strip())

    def handle_startendtag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            return  # self-closing <script/> opens nothing
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            if self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        if tag == 'title':
            self.in_title = False
        if tag in _HEADINGS and self.heading:
            level, idx = self.heading
            text = re.sub(r'\s+', ' ', ''.join(self.parts[idx + 1:])).strip()
            if text:
                self.headings.append({'level': level, 'text': text[:500]})
            self.heading = None
        if tag in _PARA_TAGS:
            self.parts.append('\n\n')
        elif tag in _LINE_TAGS - {'br'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        self.parts.append(re.sub(r'\s+', ' ', data))


def _extract(html, max_chars, max_links=200):
    parser = _TextParser(max_links)
    warnings = []
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # malformed input must never crash the caller
        warnings.append(f'parser stopped early ({type(exc).__name__}); partial text returned')
    if parser.skip:
        warnings.append('an unclosed script/style/noscript/template element hid the rest of the page')
    text = ''.join(parser.parts)
    text = re.sub(r'[ \t\r\f\v ]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    title = re.sub(r'\s+', ' ', ''.join(parser.title_parts)).strip()[:1000]
    return {'text': text, 'title': title, 'headings': parser.headings[:500],
            'links': parser.links, 'truncated': truncated, 'chars': len(text),
            'skipped_blocks': parser.skipped_blocks, 'warnings': warnings}


# --------------------------------------------------------------------------- 22.01 permitted_extract

_LOGIN_RE = re.compile(r'<input[^>]{0,300}type\s*=\s*["\']?password', re.I)
_CAPTCHA_RE = re.compile(r'g-recaptcha|h-captcha|hcaptcha|cf-turnstile|captcha', re.I)
_PAYWALL_RE = re.compile(r'paywall|subscribe to (?:continue|read)|subscribers only|للمشتركين فقط', re.I)
_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,24}')
_PHONE_RE = re.compile(r'(?:\+|\btel:)\s?\d[\d \-().]{6,20}\d')


def _allow_rule(entry, name):
    s = _str(entry, name, 512).strip()
    scheme = None
    m = re.match(r'^(https?)://', s, re.I)
    if m:
        scheme, s = m.group(1).lower(), s[m.end():]
    host, _, path = s.partition('/')
    wildcard = host.startswith('*.')
    if wildcard:
        host = host[2:]
    if '@' in host or ':' in host:
        raise ValueError(f'{name} must be host[/path-prefix] without credentials or port')
    return {'scheme': scheme, 'host': _host(host, name), 'subdomains': wildcard,
            'prefix': '/' + path if path else '/'}


def _rule_allows(rule, parts):
    if rule['scheme'] and rule['scheme'] != parts['scheme']:
        return False
    host = parts['host']
    if rule['subdomains']:
        if not host.endswith('.' + rule['host']):
            return False
    elif host != rule['host']:
        return False
    prefix = rule['prefix']
    if prefix == '/':
        return True
    base = prefix.rstrip('/')
    return parts['path'] == base or parts['path'].startswith(base + '/')


def _resolve_link(href, base):
    href = href.strip()
    low = href.lower()
    if low.startswith(('javascript:', 'mailto:', 'tel:', 'data:', '#')):
        return None
    if low.startswith('//'):
        href = base['scheme'] + ':' + href
    elif not re.match(r'^[a-z][a-z0-9+.\-]*:', low):
        root = f"{base['scheme']}://{base['host']}" + (f":{base['port']}" if base['port'] else '')
        if href.startswith('/'):
            href = root + href
        else:
            directory = base['path'].rsplit('/', 1)[0] + '/'
            href = root + directory + href
    try:
        url, _, _ = _canonical(href, 'link')
    except ValueError:
        return None
    return url


def permitted_extract(*, allow_list=None, pages=None, max_text_chars=20_000, max_links=100, **extra):
    """Extract title/headings/text/links from supplied pages ONLY if their URL is on the
    owner's allow-list ('host', '*.host', 'host/path-prefix', optionally with https://).
    Unapproved URLs, access-denied statuses and login/CAPTCHA/paywall pages are refused.
    Emails and +phone numbers in the extracted text are redacted (no personal-data collection)."""
    _no_extra(extra)
    example = allow_list is None and pages is None
    if example:
        allow_list = ['example.com/docs']
        pages = [{'url': 'https://example.com/docs/brakes?utm_source=x',
                  'html': '<title>Brake pads</title><h1>Brake pads</h1><p>Part 0 986 494 524 fits.'
                          ' Contact sales@example.com</p><a href="/docs/rotors">Rotors</a>',
                  'fetched_at': '2026-11-20T09:00:00Z'},
                 {'url': 'https://other.example.net/page', 'html': '<p>Not approved</p>',
                  'fetched_at': '2026-11-20T09:00:00Z'}]
    elif allow_list is None or pages is None:
        raise ValueError('allow_list and pages are both required (omit both for the built-in example)')
    rules = [_allow_rule(e, f'allow_list[{i}]')
             for i, e in enumerate(_list(allow_list, 'allow_list', 200, 1))]
    pages = _list(pages, 'pages', 50, 1)
    max_text_chars = _int(max_text_chars, 100, 500_000, 'max_text_chars')
    max_links = _int(max_links, 0, 1000, 'max_links')
    total = 0
    processed, refused = [], []
    for i, page in enumerate(pages):
        name = f'pages[{i}]'
        _dict(page, name, {'url', 'html', 'fetched_at', 'status'}, ('url', 'html', 'fetched_at'))
        html = _text(page['html'], f'{name}.html')
        total += len(html.encode('utf-8'))
        if total > MAX_TEXT_BYTES:
            raise ValueError(f'total page text must be at most {MAX_TEXT_BYTES} bytes')
        fetched = _ts(page['fetched_at'], f'{name}.fetched_at')
        url, removed, parts = _canonical(page['url'], f'{name}.url')
        status = page.get('status')
        if status is not None:
            status = _int(status, 100, 599, f'{name}.status')
        if not any(_rule_allows(r, parts) for r in rules):
            refused.append({'index': i, 'url': url,
                            'reason': 'domain/path is not on the owner-approved allow-list'})
            continue
        if status in (401, 402, 403, 407, 451):
            refused.append({'index': i, 'url': url,
                            'reason': f'HTTP {status}: access is restricted; no login or bypass is attempted'})
            continue
        if status is not None and status >= 300:
            refused.append({'index': i, 'url': url, 'reason': f'HTTP {status}: not a successful page'})
            continue
        gate = ('login form' if _LOGIN_RE.search(html) else
                'CAPTCHA/bot challenge' if _CAPTCHA_RE.search(html) else
                'paywall' if _PAYWALL_RE.search(html) else None)
        if gate:
            refused.append({'index': i, 'url': url,
                            'reason': f'page shows a {gate}; it is not processed and never bypassed'})
            continue
        ex = _extract(html, max_text_chars, max_links * 4 + 10)
        text, n_mail = _EMAIL_RE.subn('[redacted-email]', ex['text'])
        text, n_phone = _PHONE_RE.subn('[redacted-phone]', text)
        links = []
        for href in ex['links']:
            link = _resolve_link(href, parts)
            if link and link not in (x['url'] for x in links):
                lp = _url(link, 'link')
                links.append({'url': link, 'approved': any(_rule_allows(r, lp) for r in rules)})
            if len(links) >= max_links:
                break
        processed.append({'index': i, 'url': url, 'removed_tracking_params': removed,
                          'fetched_at': _iso(fetched), 'title': ex['title'],
                          'headings': ex['headings'], 'text': text, 'text_sha256': _sha256(text),
                          'truncated': ex['truncated'], 'links': links,
                          'redacted': {'emails': n_mail, 'phones': n_phone},
                          'warnings': ex['warnings']})
    return _pack('permitted_extract',
                 {'processed': processed, 'refused': refused, 'approved_count': len(processed),
                  'refused_count': len(refused), 'example': example},
                 ['the allow-list is the owner\'s explicit approval; anything not on it is refused',
                  "'*.host' matches subdomains only, 'host' matches that exact host; path prefixes match on '/' boundaries",
                  'login forms, CAPTCHA markers and paywall markers are detected by simple text patterns (conservative: a page that merely mentions "captcha" is refused)',
                  'emails and phone numbers written with + or tel: are redacted; other personal data is not detected'],
                 ['<= 50 pages, total HTML <= 2 MB, <= 200 allow-list entries, links <= max_links per page',
                  'robots.txt and site terms are not checked here: use crawl_policy and data_licence first',
                  'URL credentials (user@host) are refused; IDN hosts are converted with the idna codec'])


# --------------------------------------------------------------------------- 22.02 crawl_policy

def _parse_robots(text):
    groups, sitemaps, warnings = [], [], []
    current, last_was_agent = None, False
    data = text.encode('utf-8')
    if len(data) > 512_000:
        text = data[:512_000].decode('utf-8', 'ignore')
        warnings.append('robots.txt longer than 500 KiB; only the first 500 KiB was parsed (RFC 9309)')
    for lineno, raw in enumerate(text.splitlines()[:20_000], 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if ':' not in line:
            warnings.append(f'line {lineno}: no ":" separator, ignored')
            continue
        key, value = (x.strip() for x in line.split(':', 1))
        key = key.lower()
        if key in ('user-agent', 'useragent'):
            if current is None or not last_was_agent:
                current = {'agents': [], 'rules': [], 'crawl_delay': None}
                groups.append(current)
            current['agents'].append(value.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if key in ('allow', 'disallow'):
            if current is None:
                warnings.append(f'line {lineno}: rule before any User-agent, ignored')
                continue
            current['rules'].append((key == 'allow', value[:2000]))
        elif key == 'crawl-delay':
            if current is None:
                continue
            try:
                delay = float(value)
            except ValueError:
                warnings.append(f'line {lineno}: invalid Crawl-delay {value!r}, ignored')
                continue
            if delay == delay and 0 <= delay <= 86_400:
                current['crawl_delay'] = delay
        elif key == 'sitemap':
            if len(sitemaps) < 100:
                sitemaps.append(value[:MAX_URL])
    return groups, sitemaps, warnings


def _select_group(groups, user_agent):
    token = user_agent.split('/', 1)[0].strip().lower()
    exact = [g for g in groups if token in g['agents']]
    if exact:
        chosen, matched = exact, token
    else:
        prefix = sorted({a for g in groups for a in g['agents'] if a != '*' and a and token.startswith(a)},
                        key=len, reverse=True)
        if prefix:
            matched = prefix[0]
            chosen = [g for g in groups if matched in g['agents']]
        else:
            matched = '*'
            chosen = [g for g in groups if '*' in g['agents']]
    rules = [r for g in chosen for r in g['rules']]
    delays = [g['crawl_delay'] for g in chosen if g['crawl_delay'] is not None]
    return (matched if chosen else None), rules, (max(delays) if delays else None)


_PATTERN_CACHE = {}


def _pattern(pat):
    rx = _PATTERN_CACHE.get(pat)
    if rx is None:
        anchored = pat.endswith('$')
        body = pat[:-1] if anchored else pat
        rx = re.compile(''.join('.*' if c == '*' else re.escape(c) for c in body) + ('$' if anchored else ''),
                        re.S)
        if len(_PATTERN_CACHE) < 4096:
            _PATTERN_CACHE[pat] = rx
    return rx


def _robots_decision(rules, path):
    """Longest matching pattern wins; on a tie Allow wins (RFC 9309)."""
    if path == '/robots.txt':
        return True, None
    best = None
    for allow, pat in rules:
        if not pat:
            continue  # empty Disallow = no restriction
        if _pattern(pat).match(path):
            if best is None or len(pat) > len(best[1]) or (len(pat) == len(best[1]) and allow):
                best = (allow, pat)
    if best is None:
        return True, None
    return best[0], ('Allow: ' if best[0] else 'Disallow: ') + best[1]


def crawl_policy(*, robots_txt=None, site=None, user_agent='RedRoseBot', seeds=None, link_graph=None,
                 max_depth=2, max_pages=50, max_requests_per_minute=6.0, min_interval_s=1.0, **extra):
    """Parse a supplied robots.txt (User-agent groups, Allow/Disallow with longest-match
    precedence, Crawl-delay) and plan a breadth-first crawl over a supplied link graph
    {url: [linked urls]} limited by depth/pages, scheduled no faster than the crawl delay
    and the max request rate. Nothing is fetched."""
    _no_extra(extra)
    example = robots_txt is None and site is None and seeds is None and link_graph is None
    if example:
        robots_txt = ('User-agent: *\nDisallow: /private/\nAllow: /private/public-note\n'
                      'Crawl-delay: 5\n\nUser-agent: OtherBot\nDisallow: /\n')
        site = 'https://example.com'
        seeds = ['https://example.com/']
        link_graph = {'https://example.com/': ['https://example.com/parts', 'https://example.com/private/x',
                                               'https://example.com/private/public-note'],
                      'https://example.com/parts': ['https://example.com/parts/1', 'https://elsewhere.org/']}
    elif robots_txt is None or site is None:
        raise ValueError('robots_txt and site are required (omit everything for the built-in example)')
    robots_txt = _text(robots_txt, 'robots_txt')
    _, _, site_parts = _canonical(site, 'site')
    user_agent = _str(user_agent, 'user_agent', 200)
    if not re.fullmatch(r'[A-Za-z0-9_\-./ ()+;:]+', user_agent):
        raise ValueError('user_agent must be a plain product token such as RedRoseBot/1.0')
    max_depth = _int(max_depth, 0, 10, 'max_depth')
    max_pages = _int(max_pages, 1, 1000, 'max_pages')
    rate = _num(max_requests_per_minute, 0, 600, 'max_requests_per_minute', low_open=True)
    min_interval_s = _num(min_interval_s, 0, 3600, 'min_interval_s')
    if seeds is None:
        seeds = [_unsplit({**site_parts, 'path': '/', 'query': None})]
    seeds = _list(seeds, 'seeds', 100, 1)
    graph = {}
    if link_graph is not None:
        if not isinstance(link_graph, dict) or len(link_graph) > 2000:
            raise ValueError('link_graph must be a dict {url: [urls]} with at most 2000 entries')
        for key, targets in link_graph.items():
            src, _, _ = _canonical(key, 'link_graph key')
            graph[src] = [_canonical(t, f'link_graph[{key!r}]')[0]
                          for t in _list(targets, f'link_graph[{key!r}]', 500)]

    groups, sitemaps, warnings = _parse_robots(robots_txt)
    matched, rules, crawl_delay = _select_group(groups, user_agent)
    interval = max(crawl_delay or 0.0, 60.0 / rate, min_interval_s)
    site_origin = (site_parts['scheme'], site_parts['host'], site_parts['port'])

    scheduled, excluded = [], []
    queue = []
    for i, s in enumerate(seeds):
        u = _canonical(s, f'seeds[{i}]')[0]
        if u not in (q[0] for q in queue):
            queue.append((u, 0))
    queued = {q[0] for q in queue}
    head = 0
    while head < len(queue):
        url, depth = queue[head]
        head += 1
        p = _url(url, 'url')
        if (p['scheme'], p['host'], p['port']) != site_origin:
            excluded.append({'url': url, 'reason': 'off-site (robots.txt applies to one origin)'})
            continue
        path = p['path'] + ('?' + p['query'] if p['query'] else '')
        allowed, rule = _robots_decision(rules, path)
        if not allowed:
            excluded.append({'url': url, 'reason': 'disallowed by robots.txt', 'rule': rule})
            continue
        if len(scheduled) >= max_pages:
            excluded.append({'url': url, 'reason': 'max_pages reached'})
            continue
        scheduled.append({'url': url, 'depth': depth, 'at_s': round(len(scheduled) * interval, 6),
                          'rule': rule})
        for target in graph.get(url, []):
            if target in queued:
                continue
            queued.add(target)
            if depth < max_depth:
                queue.append((target, depth + 1))
            else:
                excluded.append({'url': target, 'reason': 'beyond max_depth'})
    gaps = [b['at_s'] - a['at_s'] for a, b in zip(scheduled, scheduled[1:])]
    return _pack('crawl_policy',
                 {'robots_group': matched, 'rules': [('Allow: ' if a else 'Disallow: ') + p for a, p in rules],
                  'crawl_delay_s': crawl_delay, 'interval_s': interval,
                  'min_gap_s': min(gaps) if gaps else None, 'scheduled': scheduled, 'excluded': excluded,
                  'sitemaps': sitemaps, 'warnings': warnings, 'example': example},
                 ['RFC 9309 matching: the most specific matching User-agent group (merged if repeated), else "*"; no group = everything allowed',
                  'longest matching Allow/Disallow pattern wins, Allow wins ties; * and $ wildcards supported; /robots.txt always allowed',
                  'Crawl-delay is non-standard but honoured; schedule interval = max(crawl delay, 60 / max rate, min_interval_s)',
                  'the link graph is supplied by the caller; no page is fetched to discover links'],
                 ['robots.txt parsed up to 500 KiB / 20000 lines; link_graph <= 2000 entries x 500 links; max_pages <= 1000; max_depth <= 10',
                  'percent-encoding is not decoded before matching, so %-encoded and literal paths may match differently',
                  'robots.txt permission is not a licence: also check site terms with data_licence'])


# --------------------------------------------------------------------------- 22.03 oem_normalise

_DASHES = '-‐‑‒–—―−﹣－'


def _norm_part(value, name):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raise ValueError(f'{name} must be a string (numbers lose leading zeros)')
    s = _str(value, name, 100).translate(_DIGITS)
    s = re.sub('[\\s.' + re.escape(_DASHES) + ']+', '', s).upper()
    if not re.fullmatch(r'[A-Z0-9/+_]{1,60}', s):
        raise ValueError(f'{name} must contain only letters, digits, spaces, dashes and dots')
    return s


def _norm_mfr(value, name):
    return re.sub(r'\s+', ' ', _str(value, name, 100).strip()).upper()


def oem_normalise(*, parts=None, supersessions=None, **extra):
    """Normalise OEM part numbers (strip spaces/dashes/dots, uppercase, Arabic-Indic digits
    -> ASCII, keep leading zeros), group alternates by (manufacturer, normalised number) and
    resolve supersession chains (old -> new) per manufacturer."""
    _no_extra(extra)
    example = parts is None and supersessions is None
    if example:
        parts = [{'id': 'a', 'manufacturer': 'Bosch', 'number': '0 986-494 524'},
                 {'id': 'b', 'manufacturer': 'BOSCH', 'number': '0986494524'},
                 {'id': 'c', 'manufacturer': 'Bosch', 'number': '986494524'},
                 {'id': 'd', 'manufacturer': 'Bosch', 'number': '٠٩٨٦.٤٩٤.٥٢٤'}]
        supersessions = [{'manufacturer': 'Bosch', 'old': '0986494524', 'new': '0 986 494 999'}]
    if parts is None:
        raise ValueError('parts is required (omit everything for the built-in example)')
    parts = _list(parts, 'parts', 5000, 1)
    supersessions = _list(supersessions or [], 'supersessions', 5000)
    chain = {}
    for i, rec in enumerate(supersessions):
        name = f'supersessions[{i}]'
        _dict(rec, name, {'manufacturer', 'old', 'new', 'date'}, ('manufacturer', 'old', 'new'))
        mfr = _norm_mfr(rec['manufacturer'], f'{name}.manufacturer')
        old, new = _norm_part(rec['old'], f'{name}.old'), _norm_part(rec['new'], f'{name}.new')
        if old == new:
            raise ValueError(f'{name}: old and new are the same normalised number')
        if (mfr, old) in chain and chain[(mfr, old)] != (mfr, new):
            raise ValueError(f'{name}: {mfr} {old} is superseded by two different numbers')
        chain[(mfr, old)] = (mfr, new)

    def resolve(key):
        path, seen = [key[1]], {key}
        while key in chain:
            key = chain[key]
            if key in seen:
                raise ValueError(f'supersession cycle involving {key[0]} {key[1]}')
            seen.add(key)
            path.append(key[1])
        return key, path

    out, groups, families, ids = [], {}, {}, set()
    for i, rec in enumerate(parts):
        name = f'parts[{i}]'
        _dict(rec, name, {'id', 'manufacturer', 'number'}, ('manufacturer', 'number'))
        pid = rec.get('id', i)
        if isinstance(pid, bool) or not isinstance(pid, (str, int)):
            raise ValueError(f'{name}.id must be a string or integer')
        pid = str(pid)
        if pid in ids:
            raise ValueError(f'duplicate part id {pid!r}')
        ids.add(pid)
        key = (_norm_mfr(rec['manufacturer'], f'{name}.manufacturer'),
               _norm_part(rec['number'], f'{name}.number'))
        final, path = resolve(key)
        groups.setdefault(key, []).append(pid)
        families.setdefault(final, []).append(pid)
        out.append({'id': pid, 'input': rec['number'], 'manufacturer': key[0], 'normalised': key[1],
                    'current': final[1], 'superseded': final != key, 'chain': path})
    return _pack('oem_normalise',
                 {'parts': out,
                  'alternates': [{'manufacturer': k[0], 'number': k[1], 'ids': v} for k, v in groups.items()],
                  'families': [{'manufacturer': k[0], 'current': k[1], 'ids': v} for k, v in families.items()],
                  'example': example},
                 ['normalisation removes whitespace, dots and dash characters only, uppercases, and maps Arabic-Indic digits to ASCII; leading zeros are significant and kept',
                  'parts match only within the same normalised manufacturer name; cross-brand interchange needs supplied supersession/cross-reference data',
                  'supersession is directional (old -> new) and chains are followed to the latest number'],
                 ['<= 5000 parts and 5000 supersession records; numbers <= 60 characters of A-Z 0-9 / + _ after normalisation',
                  'integers are refused because they would lose leading zeros; manufacturer aliases (e.g. "Robert Bosch") are not merged'])


# --------------------------------------------------------------------------- 22.04 price_records

ISO_4217 = {
    'AED': 2, 'AFN': 2, 'ALL': 2, 'AMD': 2, 'ARS': 2, 'AUD': 2, 'AZN': 2, 'BAM': 2, 'BDT': 2, 'BGN': 2,
    'BHD': 3, 'BRL': 2, 'BYN': 2, 'CAD': 2, 'CHF': 2, 'CLP': 0, 'CNY': 2, 'COP': 2, 'CZK': 2, 'DKK': 2,
    'DZD': 2, 'EGP': 2, 'ETB': 2, 'EUR': 2, 'GBP': 2, 'GEL': 2, 'GHS': 2, 'HKD': 2, 'HUF': 2, 'IDR': 2,
    'ILS': 2, 'INR': 2, 'IQD': 3, 'IRR': 2, 'ISK': 0, 'JOD': 3, 'JPY': 0, 'KES': 2, 'KRW': 0, 'KWD': 3,
    'KZT': 2, 'LBP': 2, 'LKR': 2, 'LYD': 3, 'MAD': 2, 'MXN': 2, 'MYR': 2, 'NGN': 2, 'NOK': 2, 'NZD': 2,
    'OMR': 3, 'PEN': 2, 'PHP': 2, 'PKR': 2, 'PLN': 2, 'QAR': 2, 'RON': 2, 'RSD': 2, 'RUB': 2, 'SAR': 2,
    'SDG': 2, 'SEK': 2, 'SGD': 2, 'SYP': 2, 'THB': 2, 'TND': 3, 'TRY': 2, 'TWD': 2, 'UAH': 2, 'USD': 2,
    'UZS': 2, 'VND': 0, 'YER': 2, 'ZAR': 2,
}


def _decimal(value, name):
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(f'{name} must be a decimal string such as "12.50" (floats lose precision)')
    s = value.strip().translate(_DIGITS).replace('٫', '.')
    if not re.fullmatch(r'\d{1,15}(?:\.\d{1,8})?', s):
        raise ValueError(f'{name} must be a non-negative decimal string without thousands separators')
    return Decimal(s)


def _currency(value, name):
    if not isinstance(value, str) or value.strip().upper() not in ISO_4217:
        raise ValueError(f'{name} must be an ISO-4217 code from the built-in list')
    return value.strip().upper()


def _quant(amount, cur):
    return amount.quantize(Decimal(1).scaleb(-ISO_4217[cur]), rounding=ROUND_HALF_EVEN)


def _median(values):
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def price_records(*, records=None, now=None, max_age_days=30, target_currency=None, fx_rates=None,
                  fx_max_age_days=3, **extra):
    """Validate supplied price records {value (decimal string), currency (ISO-4217), source_url,
    observed_at, context}. Records without a timestamp, older than max_age_days before `now` or in
    the future are rejected. Conversion uses only supplied dated FX rates; a currency mismatch
    without a usable rate is refused (never guessed)."""
    _no_extra(extra)
    example = records is None and now is None
    if example:
        now = '2026-11-21T12:00:00Z'
        target_currency = 'EGP' if target_currency is None else target_currency
        records = [{'id': 'p1', 'value': '1250.00', 'currency': 'EGP', 'source_url': 'https://shop.example/p/1',
                    'observed_at': '2026-11-20T08:00:00Z', 'context': 'list price incl. VAT'},
                   {'id': 'p2', 'value': '25.90', 'currency': 'USD', 'source_url': 'https://shop.example/p/2',
                    'observed_at': '2026-11-19T08:00:00Z', 'context': 'list price'},
                   {'id': 'p3', 'value': '999', 'currency': 'EGP', 'source_url': 'https://old.example/p'},
                   {'id': 'p4', 'value': '20', 'currency': 'EUR', 'source_url': 'https://shop.example/p/4',
                    'observed_at': '2026-11-18T08:00:00Z'}]
        if fx_rates is None:
            fx_rates = [{'base': 'USD', 'quote': 'EGP', 'rate': '48.50', 'as_of': '2026-11-19'}]
    if records is None or now is None:
        raise ValueError('records and now are both required (omit both for the built-in example)')
    now_dt = _ts(now, 'now')
    records = _list(records, 'records', MAX_RECORDS, 1)
    max_age = _num(max_age_days, 0, 3650, 'max_age_days', low_open=True)
    fx_age = _num(fx_max_age_days, 0, 365, 'fx_max_age_days')
    target = None if target_currency is None else _currency(target_currency, 'target_currency')
    rates = []
    for i, r in enumerate(_list(fx_rates or [], 'fx_rates', 1000)):
        name = f'fx_rates[{i}]'
        _dict(r, name, {'base', 'quote', 'rate', 'as_of', 'source'}, ('base', 'quote', 'rate', 'as_of'))
        rate = _decimal(r['rate'], f'{name}.rate')
        if rate <= 0:
            raise ValueError(f'{name}.rate must be positive')
        rates.append({'base': _currency(r['base'], f'{name}.base'), 'quote': _currency(r['quote'], f'{name}.quote'),
                      'rate': rate, 'as_of': _ts(r['as_of'], f'{name}.as_of'), 'index': i})

    accepted, rejected, refused, ids = [], [], [], set()
    for i, rec in enumerate(records):
        name = f'records[{i}]'
        _dict(rec, name, {'id', 'value', 'currency', 'source_url', 'observed_at', 'context'})
        rid = str(rec.get('id', i))
        if rid in ids:
            raise ValueError(f'duplicate record id {rid!r}')
        ids.add(rid)

        def reject(reason):
            rejected.append({'id': rid, 'reason': reason})
        try:
            value = _decimal(rec.get('value'), f'{name}.value')
            cur = _currency(rec.get('currency'), f'{name}.currency')
            src, _, _ = _canonical(rec.get('source_url'), f'{name}.source_url')
            context = _str(rec.get('context', ''), f'{name}.context', 500, allow_empty=True)
        except ValueError as exc:
            reject(str(exc))
            continue
        if rec.get('observed_at') is None:
            reject('missing observed_at timestamp: an undated price cannot be trusted')
            continue
        try:
            obs = _ts(rec['observed_at'], f'{name}.observed_at')
        except ValueError as exc:
            reject(str(exc))
            continue
        if obs > now_dt + timedelta(minutes=5):
            reject('observed_at is in the future relative to now')
            continue
        age = (now_dt - obs).total_seconds() / 86_400
        if age > max_age:
            reject(f'stale: observed {age:.1f} days before now (max {max_age:g})')
            continue
        item = {'id': rid, 'value': str(value), 'currency': cur, 'source_url': src,
                'observed_at': _iso(obs), 'age_days': round(age, 3), 'context': context}
        if target and cur != target:
            best = None
            for r in rates:
                if {r['base'], r['quote']} != {cur, target} or r['as_of'] > now_dt:
                    continue
                gap = abs((r['as_of'] - obs).total_seconds()) / 86_400
                if gap > fx_age:
                    continue
                rank = (gap, 0 if r['base'] == cur else 1)
                if best is None or rank < best[0]:
                    best = (rank, r)
            if best is None:
                refused.append({'id': rid, 'currency': cur, 'target_currency': target,
                                'reason': f'no supplied {cur}/{target} rate dated within {fx_age:g} days of the observation'})
                continue
            r = best[1]
            factor = r['rate'] if r['base'] == cur else Decimal(1) / r['rate']
            item.update({'converted_value': str(_quant(value * factor, target)), 'converted_currency': target,
                         'fx': {'base': r['base'], 'quote': r['quote'], 'rate': str(r['rate']),
                                'as_of': _iso(r['as_of']), 'inverted': r['base'] != cur}})
        accepted.append(item)
    stats = {}
    for item in accepted:
        cur = item.get('converted_currency', item['currency'])
        stats.setdefault(cur, []).append(Decimal(item.get('converted_value', item['value'])))
    summary = {cur: {'count': len(v), 'min': str(min(v)), 'max': str(max(v)), 'median': str(_quant(_median(v), cur))}
               for cur, v in stats.items()}
    return _pack('price_records',
                 {'accepted': accepted, 'rejected': rejected, 'refused': refused, 'summary': summary,
                  'now': _iso(now_dt), 'target_currency': target, 'example': example},
                 ['"now" is supplied by the caller (no wall clock), so results are reproducible',
                  'timestamps without a zone are taken as UTC; values are exact decimals, rounded half-even to the currency minor unit only after conversion',
                  'an FX rate is usable only if dated on/before now and within fx_max_age_days of the observation; the inverse of a supplied rate may be used',
                  'the context text (VAT, shipping, unit) is carried through but not interpreted'],
                 ['<= 500 records and 1000 FX rates; built-in ISO-4217 list of 74 common codes',
                  'no taxes, shipping or unit normalisation; price trust still depends on the source being approved'])


# --------------------------------------------------------------------------- 22.05 html_text

def html_text(*, html=None, max_chars=200_000, **extra):
    """Extract readable text from supplied HTML with html.parser: drops script/style/noscript/
    template, keeps headings ('#' markers) and paragraph breaks, decodes entities, survives
    malformed markup. JavaScript is never evaluated."""
    _no_extra(extra)
    example = html is None
    if example:
        html = ('<html><head><title>Demo &amp; test</title><style>p{color:red}</style></head>'
                '<body><h1>Heading</h1><p>First &lt;para&gt; &copy; 2026<p>Second<div>Unclosed'
                '<script>document.write("never shown")</script><li>item</body>')
    html = _text(html, 'html')
    max_chars = _int(max_chars, 100, MAX_TEXT_BYTES, 'max_chars')
    ex = _extract(html, max_chars)
    ex.pop('links')
    ex['javascript_evaluated'] = False
    ex['example'] = example
    return _pack('html_text', ex,
                 ['entities are decoded by html.parser (convert_charrefs); whitespace is collapsed, paragraph-level tags become blank lines',
                  'headings are kept inline as "#" markers and listed separately; comments are dropped',
                  'malformed markup is tolerated; an unclosed <script>/<noscript> hides the rest of the page (reported as a warning)'],
                 ['input <= 2 MB; output <= max_chars characters',
                  'no CSS evaluation: text hidden by CSS (display:none) is still included; no JavaScript is run, so script-rendered content is absent'])


# --------------------------------------------------------------------------- 22.06 source_link

def source_link(*, results=None, later_copies=None, **extra):
    """Build citation records {canonical url (lowercase host, no fragment, no utm_*/click-id
    tracking params), title, retrieved_at, content_sha256} for supplied results, and verify
    later supplied copies by hash."""
    _no_extra(extra)
    example = results is None and later_copies is None
    if example:
        results = [{'url': 'HTTPS://Docs.Example.COM:443/a/b?id=7&utm_source=news&fbclid=xyz#part2',
                    'title': 'Spec page', 'retrieved_at': '2026-11-20T10:00:00Z', 'content': 'Torque: 25 Nm'}]
        later_copies = [{'url': 'https://docs.example.com/a/b?id=7', 'content': 'Torque: 25 Nm'},
                        {'url': 'https://docs.example.com/a/b?id=7&utm_medium=x', 'content': 'Torque: 30 Nm'}]
    if results is None:
        raise ValueError('results is required (omit everything for the built-in example)')
    results = _list(results, 'results', MAX_RECORDS, 1)
    total = 0
    citations, by_url = [], {}
    for i, r in enumerate(results):
        name = f'results[{i}]'
        _dict(r, name, {'url', 'title', 'retrieved_at', 'content'}, ('url', 'title', 'retrieved_at', 'content'))
        content = _text(r['content'], f'{name}.content')
        total += len(content.encode('utf-8'))
        if total > MAX_TEXT_BYTES:
            raise ValueError(f'total content must be at most {MAX_TEXT_BYTES} bytes')
        url, removed, _ = _canonical(r['url'], f'{name}.url')
        digest = _sha256(content)
        rec = {'citation_id': _sha256(url + '\n' + digest)[:16], 'url': url, 'original_url': r['url'].strip(),
               'removed_params': removed, 'title': _str(r['title'], f'{name}.title', 1000).strip(),
               'retrieved_at': _iso(_ts(r['retrieved_at'], f'{name}.retrieved_at')),
               'content_sha256': digest, 'content_bytes': len(content.encode('utf-8'))}
        citations.append(rec)
        by_url[url] = rec  # latest citation per canonical URL
    checks = []
    for i, c in enumerate(_list(later_copies or [], 'later_copies', MAX_RECORDS)):
        name = f'later_copies[{i}]'
        _dict(c, name, {'url', 'content'}, ('url', 'content'))
        content = _text(c['content'], f'{name}.content')
        total += len(content.encode('utf-8'))
        if total > 2 * MAX_TEXT_BYTES:
            raise ValueError('total content (results + later copies) must be at most 4 MB')
        url, _, _ = _canonical(c['url'], f'{name}.url')
        actual = _sha256(content)
        cited = by_url.get(url)
        if cited is None:
            checks.append({'url': url, 'status': 'no_citation', 'verified': False, 'actual_sha256': actual})
        else:
            ok = actual == cited['content_sha256']
            checks.append({'url': url, 'citation_id': cited['citation_id'],
                           'status': 'verified' if ok else 'content_changed', 'verified': ok,
                           'expected_sha256': cited['content_sha256'], 'actual_sha256': actual})
    return _pack('source_link', {'citations': citations, 'verifications': checks, 'example': example},
                 ['canonical URL: lowercase scheme and host, default port removed, fragment removed, utm_* and common click-id params removed, other params kept in order',
                  'content_sha256 is over the exact supplied text (UTF-8); any byte change fails verification',
                  'a later copy is matched to the latest citation with the same canonical URL'],
                 ['<= 500 results and 500 later copies; total content <= 2 MB for results (4 MB with copies)',
                  'the hash proves the text is unchanged since retrieval, not that the source is correct or that the title is accurate'])


# --------------------------------------------------------------------------- 22.07 dedupe_content

_TOKEN_RE = re.compile(r'\w+(?:[.,/\-]\w+)*')


def _tokens(text):
    text = unicodedata.normalize('NFKC', text).translate(_DIGITS).casefold()
    return _TOKEN_RE.findall(text)


def _numbers(tokens):
    sig = []
    for t in tokens:
        if any(c.isdigit() for c in t):
            if re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', t):
                t = t.replace(',', '')
            sig.append(t)
    return tuple(sig)


def _simhash(shingles):
    acc = [0] * 64
    for sh in shingles:
        h = int.from_bytes(hashlib.blake2b(sh.encode('utf-8'), digest_size=8).digest(), 'big')
        for b in range(64):
            acc[b] += 1 if (h >> b) & 1 else -1
    return sum(1 << b for b in range(64) if acc[b] > 0)


def dedupe_content(*, records=None, shingle_size=3, max_hamming=3, min_jaccard=0.8, **extra):
    """Exact + near-duplicate detection over supplied texts: normalised token hash (case,
    spacing, punctuation, Arabic-Indic digits), word shingles, 64-bit SimHash and Jaccard.
    Records are merged only if every number / part-number token is identical."""
    _no_extra(extra)
    example = records is None
    if example:
        records = [{'id': 'a', 'text': 'Brake pad set 0986494524, price 1250 EGP.'},
                   {'id': 'b', 'text': '  brake   pad set 0986494524,   price 1250 EGP. '},
                   {'id': 'c', 'text': 'Brake pad set 0986494525, price 1250 EGP.'},
                   {'id': 'd', 'text': 'Oil filter for diesel engines, 5 litres.'}]
    records = _list(records, 'records', MAX_RECORDS, 1)
    k = _int(shingle_size, 1, 10, 'shingle_size')
    max_hamming = _int(max_hamming, 0, 32, 'max_hamming')
    min_jaccard = _num(min_jaccard, 0, 1, 'min_jaccard')
    items, ids, total = [], set(), 0
    for i, rec in enumerate(records):
        name = f'records[{i}]'
        _dict(rec, name, {'id', 'text'}, ('id', 'text'))
        rid = rec['id']
        if isinstance(rid, bool) or not isinstance(rid, (str, int)):
            raise ValueError(f'{name}.id must be a string or integer')
        rid = str(rid)
        if rid in ids:
            raise ValueError(f'duplicate record id {rid!r}')
        ids.add(rid)
        text = _text(rec['text'], f'{name}.text')
        total += len(text.encode('utf-8'))
        if total > MAX_TEXT_BYTES:
            raise ValueError(f'total text must be at most {MAX_TEXT_BYTES} bytes')
        toks = _tokens(text)[:50_000]
        masked = ['<num>' if any(c.isdigit() for c in t) else t for t in toks]
        shingles = {' '.join(masked[j:j + k]) for j in range(max(1, len(masked) - k + 1))} if masked else {''}
        items.append({'id': rid, 'exact': _sha256(' '.join(toks)), 'numbers': _numbers(toks),
                      'shingles': shingles, 'simhash': _simhash(shingles)})
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    merged, kept_apart = [], []
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            x, y = items[a], items[b]
            if x['exact'] == y['exact']:
                parent[find(b)] = find(a)
                merged.append({'a': x['id'], 'b': y['id'], 'reason': 'exact (after case/spacing/punctuation normalisation)'})
                continue
            dist = bin(x['simhash'] ^ y['simhash']).count('1')
            union = len(x['shingles'] | y['shingles'])
            jac = len(x['shingles'] & y['shingles']) / union if union else 1.0
            near = dist <= max_hamming or jac >= min_jaccard
            if not near:
                continue
            if x['numbers'] != y['numbers']:
                diff = sorted(set(x['numbers']) ^ set(y['numbers']))[:20]
                kept_apart.append({'a': x['id'], 'b': y['id'], 'hamming': dist, 'jaccard': round(jac, 4),
                                   'reason': 'numbers differ (protected)', 'differing_numbers': diff})
            elif dist <= max_hamming and jac >= min_jaccard:
                parent[find(b)] = find(a)
                merged.append({'a': x['id'], 'b': y['id'], 'hamming': dist, 'jaccard': round(jac, 4),
                               'reason': 'near duplicate'})
    clusters = {}
    for idx, it in enumerate(items):
        clusters.setdefault(find(idx), []).append(it['id'])
    return _pack('dedupe_content',
                 {'clusters': list(clusters.values()), 'merged_pairs': merged, 'kept_apart': kept_apart,
                  'records': [{'id': it['id'], 'exact_sha256': it['exact'], 'simhash': f"{it['simhash']:016x}",
                               'numbers': list(it['numbers'])} for it in items],
                  'example': example},
                 ['normalisation: NFKC, casefold, Arabic-Indic digits -> ASCII, tokens of letters/digits (punctuation and spacing ignored)',
                  'near duplicate = SimHash Hamming distance <= max_hamming AND shingle Jaccard >= min_jaccard, both measured with digit-bearing tokens masked',
                  'number protection: any difference in digit-bearing tokens (prices, part numbers, dates) blocks merging, even for exact-looking text',
                  'thousands separators like 1,250 are unified with 1250; "1,5" is kept as written (decimal comma ambiguity)'],
                 ['<= 500 records, total text <= 2 MB, <= 50000 tokens per record; O(n^2) pair comparison',
                  'a part number split by spaces ("0 986 494 524") tokenises differently from the joined form: normalise with oem_normalise first'])


# --------------------------------------------------------------------------- 22.08 retry_policy

_RETRYABLE_STATUS = {408, 500, 502, 503, 504}
_TIMEOUTS = {'timeout', 'connect_timeout', 'read_timeout'}
_MONTHS = {m: i for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
                                       'oct', 'nov', 'dec'), 1)}


def _retry_after(value, now_dt, name):
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    s = _str(value, name, 64).strip()
    if re.fullmatch(r'\d{1,8}', s):
        return float(int(s))
    m = re.fullmatch(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), (\d{2}) ([A-Za-z]{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT', s)
    if not m or m.group(2).lower() not in _MONTHS:
        raise ValueError(f'{name} must be delay-seconds or an HTTP-date (IMF-fixdate)')
    if now_dt is None:
        raise ValueError(f'{name} is an HTTP-date; supply now to compute the wait')
    try:
        when = datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)), int(m.group(4)),
                        int(m.group(5)), int(m.group(6)), tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f'{name} is not a valid date') from None
    return max(0.0, (when - now_dt).total_seconds())


def retry_policy(*, events=None, base_delay_s=1.0, max_delay_s=60.0, max_attempts=5, jitter=0.25, seed=0,
                 min_429_wait_s=60.0, max_wait_s=3600.0, now=None, **extra):
    """Decide, for a supplied sequence of attempt outcomes ({status} or {error}, optional
    retry_after), whether to retry, wait or stop. Retries (exponential backoff, seeded jitter,
    capped) only for 408/500/502/503/504 and timeouts; honours Retry-After; 401/403 stop and
    are reported (never retried or ignored); 429 means stop and wait, never aggressive retry."""
    _no_extra(extra)
    example = events is None
    if example:
        events = [{'status': 503}, {'status': 503}, {'error': 'timeout'}, {'status': 429, 'retry_after': 120},
                  {'status': 200}, {'status': 403}, {'status': 503}]
    events = _list(events, 'events', 100, 1)
    base = _num(base_delay_s, 0.01, 60, 'base_delay_s')
    cap = _num(max_delay_s, base, 3600, 'max_delay_s')
    max_attempts = _int(max_attempts, 1, 10, 'max_attempts')
    jitter = _num(jitter, 0, 1, 'jitter')
    seed = _int(seed, 0, 2 ** 32 - 1, 'seed')
    min_429 = _num(min_429_wait_s, 1, 86_400, 'min_429_wait_s')
    max_wait = _num(max_wait_s, 1, 604_800, 'max_wait_s')
    now_dt = None if now is None else _ts(now, 'now')
    rng = random.Random(seed)
    decisions, failures, consecutive_429, stopped, total_wait = [], 0, 0, False, 0.0
    report = []
    for i, ev in enumerate(events):
        name = f'events[{i}]'
        _dict(ev, name, {'status', 'error', 'retry_after'})
        if (ev.get('status') is None) == (ev.get('error') is None):
            raise ValueError(f'{name} needs exactly one of status or error')
        status = None if ev.get('status') is None else _int(ev['status'], 100, 599, f'{name}.status')
        error = None
        if ev.get('error') is not None:
            error = _str(ev['error'], f'{name}.error', 64).strip().lower()
            if not re.fullmatch(r'[a-z_]+', error):
                raise ValueError(f'{name}.error must be a short name such as timeout')
        ra = _retry_after(ev.get('retry_after'), now_dt, f'{name}.retry_after')
        d = {'index': i, 'status': status, 'error': error, 'retry_after_s': ra}
        if stopped:
            d.update(action='ignored', delay_s=0.0, reason='an earlier decision stopped this sequence')
        elif status is not None and status < 400:
            failures, consecutive_429 = 0, 0
            d.update(action='done', delay_s=0.0, reason='success/redirect: nothing to retry')
        elif status in (401, 403):
            stopped = True
            d.update(action='stop', delay_s=0.0,
                     reason=f'HTTP {status}: access denied - report to the owner; never retried, ignored, or worked around with logins')
            report.append(f'event {i}: HTTP {status} access denied')
        elif status == 429:
            consecutive_429 += 1
            wait = max(ra or 0.0, min_429 * 2 ** (consecutive_429 - 1))
            if consecutive_429 >= 3 or wait > max_wait:
                stopped = True
                d.update(action='stop', delay_s=0.0,
                         reason='HTTP 429 repeated or wait above max_wait_s: stop and report rate limiting')
                report.append(f'event {i}: rate limited (429)')
            else:
                total_wait += wait
                d.update(action='stop_and_wait', delay_s=wait,
                         reason='HTTP 429: pause all requests to this host for at least Retry-After; no aggressive retry')
        elif status in _RETRYABLE_STATUS or error in _TIMEOUTS:
            failures += 1
            if failures >= max_attempts:
                stopped = True
                d.update(action='stop', delay_s=0.0, reason=f'retry budget of {max_attempts} attempts exhausted')
                report.append(f'event {i}: gave up after {failures} transient failures')
            else:
                raw = base * 2 ** (failures - 1)
                delay = min(cap, raw * (1 + jitter * rng.random()))
                if ra is not None:
                    if ra > max_wait:
                        stopped = True
                        d.update(action='stop', delay_s=0.0, reason='Retry-After exceeds max_wait_s: stop and report')
                        report.append(f'event {i}: server asked to wait {ra:g}s')
                        decisions.append(d)
                        continue
                    delay = max(delay, ra)
                total_wait += delay
                d.update(action='retry', delay_s=round(delay, 6),
                         reason=f'transient {"HTTP " + str(status) if status else error}: exponential backoff #{failures}')
        else:
            stopped = True
            what = f'HTTP {status}' if status else f'error {error}'
            d.update(action='stop', delay_s=0.0,
                     reason=f'{what} is not retryable (client error, TLS/certificate problem or unknown); report, never ignore')
            report.append(f'event {i}: {what}')
        decisions.append(d)
    retry_delays = [d['delay_s'] for d in decisions if d['action'] == 'retry']
    return _pack('retry_policy',
                 {'decisions': decisions, 'retry_delays_s': retry_delays, 'total_planned_wait_s': round(total_wait, 6),
                  'stopped': stopped, 'report': report, 'seed': seed, 'example': example},
                 ['events are consecutive outcomes for one host/request; a success resets the failure counters',
                  'backoff k = min(max_delay_s, base * 2^(k-1) * (1 + jitter * u)), u from random.Random(seed); with jitter <= 1 the delays grow until the cap',
                  'Retry-After (seconds or HTTP-date relative to the supplied now) is a floor and may exceed max_delay_s, up to max_wait_s',
                  '429: wait max(Retry-After, min_429_wait_s * 2^(n-1)); a third consecutive 429 stops the sequence'],
                 ['<= 100 events, <= 10 attempts; this only plans delays: it sleeps for nothing and sends nothing',
                  'connection resets, DNS and TLS errors are not retried (only timeouts are), by design'])


# --------------------------------------------------------------------------- 22.09 export_json

_FIELD_TYPES = ('string', 'integer', 'number', 'boolean', 'url', 'datetime', 'decimal', 'string_list')


def _check_type(value, ftype, name):
    if ftype == 'string':
        _str(value, name, 100_000, allow_empty=True)
    elif ftype == 'integer':
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f'{name} must be an integer')
    elif ftype == 'number':
        _num(value, -1e300, 1e300, name)
    elif ftype == 'boolean':
        _bool(value, name)
    elif ftype == 'url':
        _url(value, name)
    elif ftype == 'datetime':
        _ts(value, name)
    elif ftype == 'decimal':
        if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,15}(?:\.\d{1,8})?', value.strip()):
            raise ValueError(f'{name} must be a decimal string')
    elif ftype == 'string_list':
        for j, v in enumerate(_list(value, name, 1000)):
            _str(v, f'{name}[{j}]', 10_000, allow_empty=True)


def _canon_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def export_json(*, schema=None, records=None, drop_undeclared=False, **extra):
    """Validate supplied records against a declared schema {version, source_field,
    fields: {name: {type, required}}} and export canonical JSON plus a manifest (count,
    sha256, schema version). Undeclared fields reject the record unless drop_undeclared is
    true, in which case every dropped field is reported - nothing is lost silently."""
    _no_extra(extra)
    example = schema is None and records is None
    if example:
        schema = {'version': '1.0', 'source_field': 'source_url',
                  'fields': {'part': {'type': 'string', 'required': True},
                             'price': {'type': 'decimal', 'required': True},
                             'source_url': {'type': 'url', 'required': True},
                             'observed_at': {'type': 'datetime', 'required': True},
                             'note': {'type': 'string', 'required': False}}}
        records = [{'part': '0986494524', 'price': '1250.00', 'source_url': 'https://shop.example/p/1',
                    'observed_at': '2026-11-20T08:00:00Z', 'colour': 'n/a'},
                   {'part': '0986494525', 'source_url': 'https://shop.example/p/2', 'observed_at': '2026-11-20'}]
        drop_undeclared = True
    if schema is None or records is None:
        raise ValueError('schema and records are both required (omit both for the built-in example)')
    _dict(schema, 'schema', {'version', 'fields', 'source_field'}, ('version', 'fields', 'source_field'))
    version = _str(schema['version'], 'schema.version', 50).strip()
    fields = schema['fields']
    if not isinstance(fields, dict) or not 1 <= len(fields) <= 100:
        raise ValueError('schema.fields must be a dict of 1..100 field definitions')
    spec = {}
    for fname, fdef in fields.items():
        if not isinstance(fname, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', fname):
            raise ValueError(f'schema field name {fname!r} must be an identifier')
        _refuse_keys([fname], 'schema.fields')
        _dict(fdef, f'schema.fields.{fname}', {'type', 'required', 'description'}, ('type',))
        if fdef['type'] not in _FIELD_TYPES:
            raise ValueError(f'schema.fields.{fname}.type must be one of {list(_FIELD_TYPES)}')
        spec[fname] = (fdef['type'], _bool(fdef.get('required', False), f'schema.fields.{fname}.required'))
    source_field = _str(schema['source_field'], 'schema.source_field', 64)
    if spec.get(source_field) != ('url', True):
        raise ValueError('schema.source_field must name a required field of type url (every record needs a source link)')
    records = _list(records, 'records', 5000, 1)
    drop_undeclared = _bool(drop_undeclared, 'drop_undeclared')
    accepted, rejected, dropped = [], [], []
    for i, rec in enumerate(records):
        name = f'records[{i}]'
        if not isinstance(rec, dict) or not all(isinstance(k, str) for k in rec):
            raise ValueError(f'{name} must be a dict with string keys')
        _refuse_keys(rec, name)
        errors = [f'missing required field {f!r}' for f, (_, req) in spec.items() if req and rec.get(f) is None]
        for f, v in rec.items():
            if f in spec and v is not None:
                try:
                    _check_type(v, spec[f][0], f'{name}.{f}')
                except ValueError as exc:
                    errors.append(str(exc))
        extra_fields = sorted(set(rec) - set(spec))
        if extra_fields and not drop_undeclared:
            errors.append(f'undeclared field(s) {extra_fields}: declare them or set drop_undeclared')
        if errors:
            rejected.append({'index': i, 'errors': errors})
            continue
        out = {f: v for f, v in rec.items() if f in spec}
        if extra_fields:
            dropped.append({'index': i, 'fields': extra_fields})
        if set(out) | set(extra_fields) != set(rec):  # accounting guard: nothing vanishes
            raise RuntimeError('field accounting mismatch')
        accepted.append(out)
    body = _canon_json(accepted)
    data = body.encode('utf-8')
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError(f'export would exceed {MAX_TEXT_BYTES} bytes')
    schema_canon = _canon_json({'version': version, 'source_field': source_field,
                                'fields': {f: {'type': t, 'required': r} for f, (t, r) in spec.items()}})
    manifest = {'schema_version': version, 'schema_sha256': _sha256(schema_canon), 'count': len(accepted),
                'rejected': len(rejected), 'input_count': len(records), 'sha256': hashlib.sha256(data).hexdigest(),
                'bytes': len(data), 'dropped_fields': dropped, 'format': 'canonical JSON array (sorted keys, no spaces, UTF-8)'}
    return _pack('export_json', {'json': body, 'manifest': manifest, 'rejected': rejected, 'example': example},
                 ['values are exported unchanged (no coercion); null values in optional fields are kept as null',
                  'undeclared fields reject the record by default; with drop_undeclared they are dropped and listed per record',
                  'the source field must be a required http(s) URL so every exported record keeps its source link'],
                 ['<= 5000 records, <= 100 fields, export <= 2 MB; the JSON text is returned, not written to disk',
                  'types are flat (no nested objects except string lists); no cross-record uniqueness checks'])


# --------------------------------------------------------------------------- 22.10 data_licence

USES = ('view', 'quote', 'store', 'redistribute', 'commercial')
_ALL = dict.fromkeys(USES, True)
LICENCES = {
    'CC0-1.0': (_ALL, []), 'PDDL-1.0': (_ALL, []),
    'CC-BY-4.0': (_ALL, ['attribution']),
    'CC-BY-SA-4.0': (_ALL, ['attribution', 'share_alike']),
    'CC-BY-ND-4.0': (_ALL, ['attribution', 'no_derivatives']),
    'CC-BY-NC-4.0': ({**_ALL, 'commercial': False}, ['attribution', 'non_commercial']),
    'CC-BY-NC-SA-4.0': ({**_ALL, 'commercial': False}, ['attribution', 'non_commercial', 'share_alike']),
    'CC-BY-NC-ND-4.0': ({**_ALL, 'commercial': False}, ['attribution', 'non_commercial', 'no_derivatives']),
    'ODC-BY-1.0': (_ALL, ['attribution']),
    'ODBL-1.0': (_ALL, ['attribution', 'share_alike', 'keep_open']),
    'OGL-UK-3.0': (_ALL, ['attribution']),
}
_ALIASES = {'CC0': 'CC0-1.0', 'CC-BY': 'CC-BY-4.0', 'CC-BY-SA': 'CC-BY-SA-4.0', 'CC-BY-ND': 'CC-BY-ND-4.0',
            'CC-BY-NC': 'CC-BY-NC-4.0', 'CC-BY-NC-SA': 'CC-BY-NC-SA-4.0', 'CC-BY-NC-ND': 'CC-BY-NC-ND-4.0',
            'ODBL': 'ODBL-1.0', 'ODC-BY': 'ODC-BY-1.0', 'PDDL': 'PDDL-1.0', 'OGL-UK': 'OGL-UK-3.0'}
_W = r'[^.;\n]{0,80}'
_TERMS = [
    ('all_rights_reserved', re.compile(r'all rights reserved|جميع الحقوق محفوظة|كل الحقوق محفوظة', re.I),
     ('store', 'redistribute', 'commercial'), False),
    ('no_scraping', re.compile(r'no (?:scraping|crawling|harvesting)|(?:scraping|crawling|harvesting|automated (?:access|collection|retrieval)|'
                               r'(?:ro)?bots?|spiders?)' + _W + r'(?:prohibited|forbidden|not (?:permitted|allowed))|'
                               r'يمنع (?:النسخ|الاستخراج|السحب|الزحف)|ممنوع (?:النسخ|الاستخراج|السحب)', re.I),
     ('store', 'redistribute', 'commercial'), True),
    ('tdm_reserved', re.compile(r'(?:text and data mining|data mining|\btdm\b)' + _W + r'(?:reserved|prohibited|forbidden|opt(?:ed)?[- ]out|not (?:permitted|allowed))', re.I),
     ('store', 'redistribute', 'commercial'), True),
    ('no_extraction', re.compile(r'(?:may not|must not|shall not|not permitted to|prohibited from|you agree not to)' + _W +
                                 r'(?:extract|re-?utili[sz]|re-?use|systematic(?:ally)? (?:copy|download))', re.I),
     ('store', 'redistribute', 'commercial'), True),
    ('no_copying', re.compile(r'(?:may not|must not|shall not|not permitted to)' + _W + r'(?:copy|reproduce|store|download|cache)', re.I),
     ('store', 'redistribute', 'commercial'), False),
    ('no_redistribution', re.compile(r'no redistribution|(?:may not|must not|shall not)' + _W + r'(?:redistribut|republish|resell|share)', re.I),
     ('redistribute',), False),
    ('non_commercial', re.compile(r'non[- ]?commercial|personal use only|for personal use|للاستخدام الشخصي', re.I),
     ('commercial',), False),
]


def data_licence(*, licence_id=None, terms_text=None, intended_uses=None, **extra):
    """Classify a dataset's licence id and/or supplied terms text into allowed uses (view,
    quote, store, redistribute, commercial). Unknown -> not allowed. Restrictive terms always
    win over a permissive licence id. Copying a protected database (terms forbidding
    extraction/reuse/scraping) is refused."""
    _no_extra(extra)
    example = licence_id is None and terms_text is None and intended_uses is None
    if example:
        licence_id, intended_uses = 'CC-BY-4.0', ['store', 'redistribute']
    if licence_id is None and terms_text is None:
        raise ValueError('licence_id or terms_text is required (omit everything for the built-in example)')
    known = None
    if licence_id is not None:
        raw = re.sub(r'[\s_]+', '-', _str(licence_id, 'licence_id', 100).strip()).upper()
        key = _ALIASES.get(raw, raw)
        known = key if key in LICENCES else None
        licence_norm = key
    else:
        licence_norm = None
    terms = '' if terms_text is None else _text(terms_text, 'terms_text')
    uses_req = []
    for u in ([] if intended_uses is None else _list(intended_uses, 'intended_uses', len(USES))):
        if not isinstance(u, str) or u not in USES:
            raise ValueError(f'intended_uses items must be one of {list(USES)}')
        if u not in uses_req:
            uses_req.append(u)
    if known:
        base, conditions = dict(LICENCES[known][0]), list(LICENCES[known][1])
        basis = {u: f'licence {known}' for u in USES}
    else:
        base = {u: False for u in USES}
        conditions = []
        basis = {u: 'no recognised licence: not allowed by default (conservative)' for u in USES}
        if terms or licence_id is not None:
            base['view'] = True
            basis['view'] = 'viewing a publicly available page is not copying'
        basis['quote'] = 'no recognised licence: short quotation may be lawful under local quotation/fair-use rules - needs human review'
    matched, protected = [], False
    for label, rx, blocks, protects in _TERMS:
        m = rx.search(terms)
        if not m:
            continue
        matched.append({'term': label, 'text': m.group(0)[:120]})
        protected = protected or protects
        for u in blocks:
            if base[u]:
                base[u] = False
            basis[u] = f'blocked by terms ({label})'
    uses = {u: {'allowed': base[u], 'basis': basis[u]} for u in USES}
    copy_uses = [u for u in uses_req if u in ('store', 'redistribute', 'commercial')]
    refused = protected and bool(copy_uses)
    decisions = {u: ('refused: copying a protected database (terms forbid extraction/reuse)' if refused and u in copy_uses
                     else 'allowed' + (f' with conditions {conditions}' if conditions else '') if base[u]
                     else 'not allowed') for u in uses_req}
    return _pack('data_licence',
                 {'licence_id': licence_norm, 'recognised': known is not None, 'uses': uses, 'conditions': conditions,
                  'matched_terms': matched, 'protected_database': protected, 'intended_uses': uses_req,
                  'decisions': decisions, 'refused': refused, 'example': example},
                 ['built-in table of common open licences (CC0, CC BY family 4.0, ODbL, ODC-By, PDDL, OGL-UK); anything else is unknown and not allowed',
                  'restrictive phrases in the terms (English and Arabic patterns) always override a permissive licence id',
                  'protected database = terms forbidding scraping, extraction, re-use or text-and-data mining; copying it (store/redistribute/commercial) is refused',
                  'conditions such as attribution and share-alike must be honoured by whoever uses the data'],
                 ['pattern matching is not legal advice; ambiguous or translated terms need a human review',
                  'terms_text <= 2 MB; jurisdiction-specific rights (EU database right, fair use) are flagged conservatively, not decided'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'permitted_extract': permitted_extract, 'crawl_policy': crawl_policy, 'oem_normalise': oem_normalise,
    'price_records': price_records, 'html_text': html_text, 'source_link': source_link,
    'dedupe_content': dedupe_content, 'retry_policy': retry_policy, 'export_json': export_json,
    'data_licence': data_licence,
}


def run(op, params=None):
    """Validate and dispatch: run('html_text', {'html': '<p>x</p>'}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    _refuse_keys(params, 'params')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
