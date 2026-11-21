"""Red Rose V24: small, bounded, deterministic app-building helpers (topics 10.01-10.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no printing,
no clock reads (callers pass timestamps). Every op validates its inputs strictly
(ValueError on wrong types, unknown parameter names and out-of-range values) and
caps its work so it cannot run away.

Generated projects, pages, specs and manifests are returned IN MEMORY as
{relative_path: text} or plain JSON values; nothing is written to disk here.
Writing results to disk is a separate, approval-gated step outside this module.
Generated Python is validated with ast.parse and generated JSON with json.loads
inside the module; generated code is never executed.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import html
import json
import keyword
import re
import string
from html.parser import HTMLParser

MAX_PARAMS = 24
MAX_TEXT = 2_000
MAX_SOURCE = 200_000

TOPICS = {
    '10.01': 'scaffold',
    '10.02': 'rtl_ui',
    '10.03': 'openapi_spec',
    '10.04': 'sql_schema',
    '10.05': 'session_tokens',
    '10.06': 'router_spec',
    '10.07': 'feature_tests',
    '10.08': 'docs_from_code',
    '10.09': 'package_manifest',
    '10.10': 'deploy_plan',
}

TOPIC_NAMES_AR = {
    '10.01': 'مولد هيكل تطبيق من مواصفة',
    '10.02': 'بناء واجهات عربية RTL',
    '10.03': 'إنشاء REST API موثق',
    '10.04': 'مصمم قواعد بيانات أولية',
    '10.05': 'إدارة حسابات ومصادقة',
    '10.06': 'بناء نموذج متعدد الصفحات',
    '10.07': 'إضافة اختبار تلقائي مع كل ميزة',
    '10.08': 'توليد وثائق من الكود',
    '10.09': 'تحزيم تطبيق قابل للتثبيت',
    '10.10': 'إعداد نشر مبدئي آمن',
}

IN_MEMORY_NOTE = ('returned in memory only; writing to disk is a separate, '
                  'approval-gated step outside this module')

# --------------------------------------------------------------------------- validation

_IDENT_RE = re.compile(r'^[a-z_][a-z0-9_]{0,39}$')
_SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
_SEMVER_RE = re.compile(r'^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})'
                        r'(?:-[0-9A-Za-z.-]{1,32})?$')


def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _text(value, name, max_len=MAX_TEXT, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL characters')
    return value


def _pattern(value, regex, name, hint):
    if not isinstance(value, str) or not regex.match(value):
        raise ValueError(f'{name} must be {hint}')
    return value


def _ident(value, name):
    _pattern(value, _IDENT_RE, name,
             'a lowercase Python identifier (letters, digits, underscore; max 40)')
    if keyword.iskeyword(value) or keyword.issoftkeyword(value):
        raise ValueError(f'{name} must not be a Python keyword')
    return value


def _list(value, name, low, high):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low} to {high} items')
    return list(value)


def _dict(value, name, low=0, high=64):
    if not isinstance(value, dict) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a dict with {low} to {high} keys')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _unique(items, name):
    seen = set()
    for item in items:
        if item in seen:
            raise ValueError(f'duplicate {name}: {item}')
        seen.add(item)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False)


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _camel(name):
    return ''.join(part[:1].upper() + part[1:] for part in name.split('_') if part) or 'App'


def _check_python(files):
    """ast.parse every .py file; return the sorted list of validated paths."""
    checked = []
    for path in sorted(files):
        if path.endswith('.py'):
            try:
                ast.parse(files[path], filename=path)
            except SyntaxError as exc:  # pragma: no cover - templates are fixed
                raise RuntimeError(f'generated {path} does not parse: {exc}') from exc
            checked.append(path)
    return checked


def _check_json(files):
    checked = []
    for path in sorted(files):
        if path.endswith('.json'):
            json.loads(files[path])
            checked.append(path)
    return checked


def _assigned_literal(source, target):
    """Return ast.literal_eval of the top-level `target = <literal>` assignment."""
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == target):
            return ast.literal_eval(node.value)
    raise RuntimeError(f'{target} not found in generated source')  # pragma: no cover


# --------------------------------------------------------------------------- 10.01 scaffold

_STORE_TMPL = string.Template('''"""$title: generated $kind app with an in-memory store."""
$imports

DESCRIPTION = $desc_lit
ENTITIES = $entities_lit


class Store:
    """In-memory store: one list of records per entity."""

    def __init__(self):
        self.data = {name: [] for name in ENTITIES}

    def _bucket(self, entity):
        if entity not in self.data:
            raise ValueError('unknown entity: ' + str(entity))
        return self.data[entity]

    def add(self, entity, title):
        """Add a record and return it."""
        bucket = self._bucket(entity)
        record = {'id': len(bucket) + 1, 'title': str(title)}
        bucket.append(record)
        return record

    def list(self, entity):
        """Return a copy of the records of one entity."""
        return list(self._bucket(entity))

    def get(self, entity, record_id):
        for record in self._bucket(entity):
            if record['id'] == record_id:
                return record
        return None

    def delete(self, entity, record_id):
        bucket = self._bucket(entity)
        before = len(bucket)
        bucket[:] = [r for r in bucket if r['id'] != record_id]
        return len(bucket) < before
$extra
''')

_CLI_EXTRA = '''

def build_parser():
    parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION)
    parser.add_argument('entity', choices=ENTITIES)
    parser.add_argument('title')
    return parser


def main(argv=None, store=None):
    """Parse argv, add one record, return it as JSON text."""
    args = build_parser().parse_args(argv)
    store = store if store is not None else Store()
    return json.dumps(store.add(args.entity, args.title), ensure_ascii=False)


if __name__ == '__main__':
    print(main())
'''

_API_EXTRA = '''

def handle(store, method, path, body=None):
    """Route one request; returns (status, payload). No network server here."""
    parts = [p for p in str(path).split('/') if p]
    if not parts or parts[0] not in ENTITIES or len(parts) > 2:
        return 404, {'error': 'not found'}
    entity = parts[0]
    if len(parts) == 1:
        if method == 'GET':
            return 200, store.list(entity)
        if method == 'POST':
            title = (body or {}).get('title')
            if not isinstance(title, str) or not title:
                return 400, {'error': 'title required'}
            return 201, store.add(entity, title)
        return 405, {'error': 'method not allowed'}
    if not parts[1].isdigit():
        return 400, {'error': 'id must be an integer'}
    record_id = int(parts[1])
    if method == 'GET':
        record = store.get(entity, record_id)
        return (200, record) if record else (404, {'error': 'not found'})
    if method == 'DELETE':
        return (204, None) if store.delete(entity, record_id) else (404, {'error': 'not found'})
    return 405, {'error': 'method not allowed'}
'''

_WEB_EXTRA = '''

def render(store, entity):
    """Render one entity as an escaped HTML list fragment."""
    items = ''.join('<li>' + html.escape(r['title']) + '</li>' for r in store.list(entity))
    return '<section><h2>' + html.escape(entity) + '</h2><ul>' + items + '</ul></section>'
'''

_TEST_TMPL = string.Template('''"""Generated tests for $name."""
import unittest

import $name


class Test$cls(unittest.TestCase):
    def test_add_and_list_every_entity(self):
        store = $name.Store()
        for entity in $name.ENTITIES:
            record = store.add(entity, 'first')
            self.assertEqual(record['id'], 1)
            self.assertEqual(len(store.list(entity)), 1)

    def test_unknown_entity_rejected(self):
        with self.assertRaises(ValueError):
            $name.Store().add('__unknown__', 'x')
$extra

if __name__ == '__main__':
    unittest.main()
''')

_TEST_EXTRA = {
    'cli': '''
    def test_main_returns_json(self):
        import json
        out = json.loads($name.main([$name.ENTITIES[0], 'hello']))
        self.assertEqual(out['title'], 'hello')
''',
    'api': '''
    def test_handle_crud(self):
        store = $name.Store()
        entity = $name.ENTITIES[0]
        status, created = $name.handle(store, 'POST', '/' + entity, {'title': 'a'})
        self.assertEqual(status, 201)
        self.assertEqual($name.handle(store, 'GET', '/' + entity + '/1')[0], 200)
        self.assertEqual($name.handle(store, 'DELETE', '/' + entity + '/1')[0], 204)
        self.assertEqual($name.handle(store, 'GET', '/' + entity + '/1')[0], 404)
''',
    'web_static': '''
    def test_render_escapes(self):
        store = $name.Store()
        entity = $name.ENTITIES[0]
        store.add(entity, '<b>x</b>')
        self.assertIn('&lt;b&gt;', $name.render(store, entity))
''',
}


def scaffold(*, spec=None, **extra):
    """Generate a minimal original project file map from a small spec.

    spec: {'name': identifier, 'kind': 'cli'|'web_static'|'api',
           'entities': [identifier, ...], 'description': optional text}.
    Names are validated as lowercase identifiers (so 'x; import os' is rejected);
    free text only enters Python as a repr() literal and HTML via html.escape.
    """
    _no_extra(extra)
    if spec is None:
        spec = {'name': 'notes_app', 'kind': 'cli', 'entities': ['note', 'tag'],
                'description': 'تطبيق ملاحظات بسيط'}
    spec = _dict(spec, 'spec', 1, 4)
    unknown = set(spec) - {'name', 'kind', 'entities', 'description'}
    if unknown:
        raise ValueError('unknown spec key(s): ' + ', '.join(sorted(unknown)))
    if 'name' not in spec:
        raise ValueError('spec.name is required')
    name = _ident(spec['name'], 'spec.name')
    kind = _choice(spec.get('kind', 'cli'), {'cli', 'web_static', 'api'}, 'spec.kind')
    entities = _list(spec.get('entities', ['item']), 'spec.entities', 1, 12)
    entities = [_ident(e, f'spec.entities[{i}]') for i, e in enumerate(entities)]
    _unique(entities, 'entity')
    desc = _text(spec.get('description', ''), 'spec.description', 500, allow_empty=True)

    imports = {'cli': 'import argparse\nimport json', 'api': '', 'web_static': 'import html'}
    extra_code = {'cli': _CLI_EXTRA, 'api': _API_EXTRA, 'web_static': _WEB_EXTRA}[kind]
    head = imports[kind]
    if kind == 'cli':
        extra_code = '\nPROG = ' + repr(name) + extra_code
    main_src = _STORE_TMPL.substitute(title=name, kind=kind, imports=head,
                                      desc_lit=repr(desc), entities_lit=repr(entities),
                                      extra=extra_code.rstrip('\n'))
    main_src = re.sub(r'\n{4,}', '\n\n\n', main_src)
    test_extra = string.Template(_TEST_EXTRA[kind]).substitute(name=name)
    test_src = _TEST_TMPL.substitute(name=name, cls=_camel(name), extra=test_extra)

    readme = '\n'.join([
        f'# {name}', '',
        html.escape(desc) if desc else f'A generated {kind} app.', '',
        f'Kind: `{kind}`. Entities: ' + ', '.join(f'`{e}`' for e in entities) + '.', '',
        '## Run tests', '', '```', f'python -m unittest test_{name} -v', '```', '',
    ])
    files = {'README.md': readme, f'{name}.py': main_src, f'test_{name}.py': test_src}
    if kind == 'web_static':
        lis = ''.join(f'<li><a href="#{e}">{html.escape(e)}</a></li>' for e in entities)
        files['index.html'] = (
            '<!doctype html>\n<html lang="ar" dir="rtl">\n<head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(name)}</title></head>\n<body><h1>{html.escape(name)}</h1>'
            f'<p>{html.escape(desc)}</p><ul>{lis}</ul></body>\n</html>\n')
    manifest = {'name': name, 'kind': kind, 'entities': entities,
                'files': sorted(files) + ['project.json']}
    files['project.json'] = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'

    py_ok = _check_python(files)
    json_ok = _check_json(files)
    # The description must round-trip exactly through the generated literal.
    desc_roundtrip = _assigned_literal(main_src, 'DESCRIPTION') == desc
    if not desc_roundtrip:  # pragma: no cover
        raise RuntimeError('description did not round-trip safely')
    return _pack('scaffold', {
        'files': files, 'python_parsed': py_ok, 'json_parsed': json_ok,
        'description_roundtrip': desc_roundtrip, 'written': False, 'note': IN_MEMORY_NOTE,
    }, ['templates are fixed and original; only validated identifiers are spliced into code',
        'free text enters Python only as repr() literals and HTML only via html.escape',
        'generated code is parsed with ast but never executed here'],
       ['entities <= 12, identifiers <= 40 chars, description <= 500 chars',
        'minimal in-memory store only: no persistence, auth or real HTTP server',
        IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.02 rtl_ui

_RTL_CSS = '''*{box-sizing:border-box}
body{margin:0;font-family:"Noto Naskh Arabic","Segoe UI",Tahoma,sans-serif;line-height:1.7;
background:#fafafa;color:#1a1a1a}
header,main{max-width:960px;margin:0 auto;padding:16px}
[role="tablist"]{display:flex;flex-wrap:wrap;gap:8px;border-bottom:2px solid #ddd}
[role="tab"]{font:inherit;padding:10px 16px;border:0;background:none;cursor:pointer;
border-bottom:3px solid transparent}
[role="tab"][aria-selected="true"]{border-bottom-color:#b00020;font-weight:700}
[role="tab"]:focus-visible{outline:3px solid #1565c0;outline-offset:2px}
[role="tabpanel"]{padding:16px 0}
@media (max-width:640px){[role="tablist"]{flex-direction:column}[role="tab"]{text-align:right;width:100%}}
@media (min-width:1024px){header,main{padding:24px 32px}body{font-size:1.125rem}}'''

_RTL_JS = '''(function(){var tabs=Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
function show(t){tabs.forEach(function(x){var on=x===t;x.setAttribute('aria-selected',on?'true':'false');
x.tabIndex=on?0:-1;document.getElementById(x.getAttribute('aria-controls')).hidden=!on;});t.focus();}
tabs.forEach(function(t,i){t.addEventListener('click',function(){show(t);});
t.addEventListener('keydown',function(e){var n=null;
if(e.key==='ArrowLeft'){n=tabs[(i+1)%tabs.length];}
if(e.key==='ArrowRight'){n=tabs[(i-1+tabs.length)%tabs.length];}
if(e.key==='Home'){n=tabs[0];}if(e.key==='End'){n=tabs[tabs.length-1];}
if(n){e.preventDefault();show(n);}});});})();'''


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def _audit_rtl(page, n_sections, with_script):
    parser = _TagCollector()
    parser.feed(page)
    parser.close()
    tags = parser.tags
    by_id = {a.get('id'): (t, a) for t, a in tags if a.get('id')}
    html_tag = next(a for t, a in tags if t == 'html')
    tabs = [a for t, a in tags if a.get('role') == 'tab']
    panels = [a for t, a in tags if a.get('role') == 'tabpanel']
    scripts = [a for t, a in tags if t == 'script']
    controls_ok = all(by_id.get(a.get('aria-controls'), ('', {}))[1].get('role') == 'tabpanel'
                      for a in tabs)
    labelled_ok = all(by_id.get(a.get('aria-labelledby'), ('', {}))[1].get('role') == 'tab'
                      for a in panels)
    checks = {
        'dir_rtl': html_tag.get('dir') == 'rtl',
        'lang_ar': html_tag.get('lang') == 'ar',
        'has_tablist': sum(1 for _, a in tags if a.get('role') == 'tablist') == 1,
        'tab_count': len(tabs) == n_sections and len(panels) == n_sections,
        'one_selected': sum(1 for a in tabs if a.get('aria-selected') == 'true') == 1,
        'aria_selected_on_all_tabs': all(a.get('aria-selected') in ('true', 'false')
                                         for a in tabs),
        'tabs_control_panels': controls_ok,
        'panels_labelled_by_tabs': labelled_ok,
        'no_external_scripts': all('src' not in a for a in scripts),
        'script_count_expected': len(scripts) == (1 if with_script else 0),
        'no_inline_event_handlers': not any(k.startswith('on') for _, a in tags for k in a),
        'no_external_resources': not any(t in ('link', 'iframe', 'img', 'object', 'embed')
                                         for t, _ in tags),
        'has_mobile_and_desktop_breakpoints': ('max-width:640px' in page
                                               and 'min-width:1024px' in page),
    }
    return checks


def rtl_ui(*, title='لوحة التطبيق', sections=None, include_script=True, **extra):
    """Static Arabic RTL page with accessible tabs; every text is html-escaped.

    sections: [{'id': slug, 'title': text, 'body': text}, ...] (1..12).
    The optional tab script is inline (no external scripts, no network).
    """
    _no_extra(extra)
    title = _text(title, 'title', 200)
    include_script = _bool(include_script, 'include_script')
    if sections is None:
        sections = [
            {'id': 'home', 'title': 'الرئيسية', 'body': 'مرحبًا بك في التطبيق.'},
            {'id': 'reports', 'title': 'التقارير', 'body': 'ملخص الأرقام هنا.'},
            {'id': 'settings', 'title': 'الإعدادات', 'body': 'اختر تفضيلاتك.'},
        ]
    sections = _list(sections, 'sections', 1, 12)
    clean = []
    for i, sec in enumerate(sections):
        sec = _dict(sec, f'sections[{i}]', 2, 3)
        bad = set(sec) - {'id', 'title', 'body'}
        if bad or 'id' not in sec or 'title' not in sec:
            raise ValueError(f'sections[{i}] needs id and title (and optional body) only')
        clean.append({'id': _pattern(sec['id'], _SLUG_RE, f'sections[{i}].id',
                                     'a lowercase slug (a-z, 0-9, -; max 32)'),
                      'title': _text(sec['title'], f'sections[{i}].title', 120),
                      'body': _text(sec.get('body', ''), f'sections[{i}].body',
                                    MAX_TEXT, allow_empty=True)})
    _unique([s['id'] for s in clean], 'section id')

    esc = html.escape
    tab_html, panel_html = [], []
    for i, s in enumerate(clean):
        sel = 'true' if i == 0 else 'false'
        tab_html.append(
            f'<button type="button" role="tab" id="tab-{s["id"]}" aria-selected="{sel}" '
            f'aria-controls="panel-{s["id"]}" tabindex="{0 if i == 0 else -1}">'
            f'{esc(s["title"])}</button>')
        paras = ''.join(f'<p>{esc(line)}</p>' for line in s['body'].split('\n') if line.strip())
        panel_html.append(
            f'<section role="tabpanel" id="panel-{s["id"]}" aria-labelledby="tab-{s["id"]}" '
            f'tabindex="0"{"" if i == 0 else " hidden"}><h2>{esc(s["title"])}</h2>{paras}</section>')
    script = f'<script>{_RTL_JS}</script>\n' if include_script else ''
    page = ('<!doctype html>\n<html lang="ar" dir="rtl">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)}</title>\n<style>\n{_RTL_CSS}\n</style>\n</head>\n<body>\n'
            f'<header><h1>{esc(title)}</h1></header>\n<main>\n'
            f'<div role="tablist" aria-label="{esc(title)}">' + ''.join(tab_html) + '</div>\n'
            + '\n'.join(panel_html) + f'\n</main>\n{script}</body>\n</html>\n')
    checks = _audit_rtl(page, len(clean), include_script)
    if not all(checks.values()):  # pragma: no cover - fixed template
        raise RuntimeError('generated page failed its own audit: '
                           + ', '.join(k for k, v in checks.items() if not v))
    return _pack('rtl_ui', {
        'files': {'index.html': page}, 'html': page, 'checks': checks,
        'bytes': len(page.encode('utf-8')), 'written': False, 'note': IN_MEMORY_NOTE,
    }, ['all user text passes through html.escape (quotes included)',
        'tabs follow the WAI-ARIA tabs pattern; arrow keys are mirrored for RTL',
        'breakpoints: <=640px stacks tabs, >=1024px widens padding and type'],
       ['sections <= 12, body <= 2000 chars each; plain text only (no markup passthrough)',
        'audit is structural (tags/attributes); no browser rendering or contrast measurement',
        'font stack names system fonts; no web fonts are bundled', IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.03 openapi_spec

_OAS_TYPES = {'string': {'type': 'string'}, 'integer': {'type': 'integer'},
              'number': {'type': 'number'}, 'boolean': {'type': 'boolean'}}
_READ_METHODS = {'get'}


def _resolve_refs(node, spec, missing):
    if isinstance(node, dict):
        ref = node.get('$ref')
        if isinstance(ref, str):
            cur = spec
            for part in ref.lstrip('#/').split('/'):
                cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                missing.append(ref)
        for v in node.values():
            _resolve_refs(v, spec, missing)
    elif isinstance(node, list):
        for v in node:
            _resolve_refs(v, spec, missing)


def _validate_openapi(spec, resources):
    problems = []
    if not str(spec.get('openapi', '')).startswith('3.0'):
        problems.append('openapi version must be 3.0.x')
    for key in ('info', 'paths', 'components'):
        if key not in spec:
            problems.append(f'missing {key}')
    op_ids = []
    write_ops_ok = True
    read_ops_ok = True
    for path, item in spec.get('paths', {}).items():
        for method, op in item.items():
            if method == 'parameters':
                continue
            op_ids.append(op.get('operationId'))
            if not op.get('responses'):
                problems.append(f'{method} {path} has no responses')
            sec = op.get('security') or []
            scopes = [s for req in sec for s in req.get('oauth2', [])]
            res = op.get('x-resource')
            if not scopes:
                problems.append(f'{method} {path} has no security requirement')
            if method in _READ_METHODS:
                read_ops_ok &= scopes == [f'{res}:read']
            else:
                write_ops_ok &= scopes == [f'{res}:write']
    if len(op_ids) != len(set(op_ids)):
        problems.append('operationId values are not unique')
    missing = []
    _resolve_refs(spec, spec, missing)
    problems += [f'unresolved $ref {m}' for m in missing]
    expected = {}
    for r in resources:
        plural = r + 's'
        expected[f'/{plural}'] = {'get', 'post'}
        expected[f'/{plural}/{{id}}'] = {'get', 'put', 'delete'}
    crud_ok = all(set(spec['paths'].get(p, {})) - {'parameters'} == m for p, m in expected.items())
    return {'problems': problems, 'write_ops_require_write_scope': write_ops_ok,
            'read_ops_require_read_scope': read_ops_ok, 'crud_paths_complete': crud_ok,
            'operation_count': len(op_ids), 'valid': not problems and write_ops_ok
            and read_ops_ok and crud_ok}


def openapi_spec(*, title='Notes API', version='1.0.0', resources=None, **extra):
    """OpenAPI 3.0 JSON for CRUD resources with per-resource read/write OAuth2 scopes.

    resources: [{'name': identifier, 'fields': {field: string|integer|number|boolean}}].
    Each resource gets list/create on /<name>s and get/update/delete on /<name>s/{id}.
    GET requires '<name>:read'; POST/PUT/DELETE require '<name>:write'.
    """
    _no_extra(extra)
    title = _text(title, 'title', 120)
    version = _pattern(version, _SEMVER_RE, 'version', 'a SemVer string like 1.0.0')
    if resources is None:
        resources = [{'name': 'note', 'fields': {'title': 'string', 'done': 'boolean'}},
                     {'name': 'tag', 'fields': {'label': 'string'}}]
    resources = _list(resources, 'resources', 1, 12)
    clean = []
    for i, r in enumerate(resources):
        r = _dict(r, f'resources[{i}]', 1, 2)
        if set(r) - {'name', 'fields'} or 'name' not in r:
            raise ValueError(f'resources[{i}] needs name and optional fields only')
        name = _ident(r['name'], f'resources[{i}].name')
        fields = _dict(r.get('fields', {}), f'resources[{i}].fields', 0, 32)
        for f, t in fields.items():
            _ident(f, f'resources[{i}].fields key')
            if f == 'id':
                raise ValueError('field name "id" is reserved')
            _choice(t, set(_OAS_TYPES), f'resources[{i}].fields.{f}')
        clean.append((name, dict(sorted(fields.items()))))
    _unique([n for n, _ in clean], 'resource name')

    schemas, paths, scopes = {}, {}, {}
    err = {'description': 'Error', 'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/Error'}}}}
    schemas['Error'] = {'type': 'object', 'required': ['error'],
                        'properties': {'error': {'type': 'string'}}}
    for name, fields in clean:
        cls = _camel(name)
        props = {f: dict(_OAS_TYPES[t]) for f, t in fields.items()}
        schemas[f'{cls}Input'] = {'type': 'object', 'properties': props,
                                  'required': sorted(fields), 'additionalProperties': False}
        schemas[cls] = {'allOf': [{'$ref': f'#/components/schemas/{cls}Input'},
                                  {'type': 'object', 'required': ['id'], 'properties': {
                                      'id': {'type': 'integer', 'readOnly': True}}}]}
        scopes[f'{name}:read'] = f'Read {name} records'
        scopes[f'{name}:write'] = f'Create, update and delete {name} records'
        ref = {'$ref': f'#/components/schemas/{cls}'}
        body = {'required': True, 'content': {'application/json': {
            'schema': {'$ref': f'#/components/schemas/{cls}Input'}}}}

        def op(op_id, scope, responses, request=None, _name=name):
            out = {'operationId': op_id, 'tags': [_name], 'x-resource': _name,
                   'security': [{'oauth2': [f'{_name}:{scope}']}], 'responses': responses}
            if scope == 'write':
                out['responses'] = dict(responses, **{'401': err, '403': err})
            else:
                out['responses'] = dict(responses, **{'401': err})
            if request:
                out['requestBody'] = request
            return out

        one = {'description': 'OK', 'content': {'application/json': {'schema': ref}}}
        paths[f'/{name}s'] = {
            'get': op(f'list_{name}', 'read', {'200': {'description': 'OK', 'content': {
                'application/json': {'schema': {'type': 'array', 'items': ref}}}}}),
            'post': op(f'create_{name}', 'write', {'201': dict(one, description='Created'),
                                                   '400': err}, body),
        }
        paths[f'/{name}s/{{id}}'] = {
            'parameters': [{'name': 'id', 'in': 'path', 'required': True,
                            'schema': {'type': 'integer', 'minimum': 1}}],
            'get': op(f'get_{name}', 'read', {'200': one, '404': err}),
            'put': op(f'update_{name}', 'write', {'200': one, '400': err, '404': err}, body),
            'delete': op(f'delete_{name}', 'write', {'204': {'description': 'Deleted'},
                                                     '404': err}),
        }
    spec = {'openapi': '3.0.3', 'info': {'title': title, 'version': version},
            'servers': [{'url': '/api'}], 'paths': paths,
            'components': {'schemas': schemas, 'securitySchemes': {'oauth2': {
                'type': 'oauth2', 'flows': {'clientCredentials': {
                    'tokenUrl': '/oauth/token', 'scopes': scopes}}}}},
            'security': []}
    text = json.dumps(spec, ensure_ascii=False, indent=2)
    spec_back = json.loads(text)
    checks = _validate_openapi(spec_back, [n for n, _ in clean])
    return _pack('openapi_spec', {
        'spec': spec_back, 'files': {'openapi.json': text + '\n'}, 'checks': checks,
        'written': False, 'note': IN_MEMORY_NOTE,
    }, ['OAuth2 client-credentials scheme; per-resource <name>:read and <name>:write scopes',
        'plural path = name + "s" (no English inflection rules)',
        'global security is empty so every operation states its own requirement'],
       ['resources <= 12, fields <= 32 of primitive types only (no nested objects, no pagination)',
        'structural self-validation only; not a full OpenAPI JSON-Schema validation',
        IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.04 sql_schema

_SQL_TYPES = {'INTEGER', 'TEXT', 'REAL', 'BLOB', 'NUMERIC'}
_DESTRUCTIVE_OPS = {'drop_table', 'drop_column', 'rename_table', 'rename_column'}
_SAFE_OPS = {'create_table', 'add_column'}
_RAW_FORBIDDEN = re.compile(r'\b(DROP|RENAME|DELETE|TRUNCATE|UPDATE|INSERT|REPLACE|ATTACH|'
                            r'DETACH|PRAGMA|VACUUM)\b', re.I)
_RAW_DESTRUCTIVE = re.compile(r'\b(DROP|RENAME|DELETE|TRUNCATE)\b', re.I)
_RAW_SAFE = re.compile(r'^\s*(CREATE\s+(TABLE|INDEX|UNIQUE\s+INDEX)\s+IF\s+NOT\s+EXISTS\s|'
                       r'ALTER\s+TABLE\s+"?[a-z_][a-z0-9_]*"?\s+ADD\s+COLUMN\s)', re.I)


def _q(name):
    return '"' + name + '"'


def _sql_literal(value, name):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int) and abs(value) < 2 ** 63:
        return str(value)
    if isinstance(value, float) and value == value and abs(value) < 1e300:
        return repr(value)
    if isinstance(value, str) and len(value) <= 200 and '\x00' not in value:
        return "'" + value.replace("'", "''") + "'"
    raise ValueError(f'{name} must be null, a bool, a number or a short string')


def _column(col, where):
    col = _dict(col, where, 2, 6)
    bad = set(col) - {'name', 'type', 'pk', 'not_null', 'default', 'ref'}
    if bad or 'name' not in col or 'type' not in col:
        raise ValueError(f'{where} needs name and type (optional pk, not_null, default, ref)')
    c = {'name': _ident(col['name'], f'{where}.name'),
         'type': _choice(col['type'], _SQL_TYPES, f'{where}.type'),
         'pk': _bool(col.get('pk', False), f'{where}.pk'),
         'not_null': _bool(col.get('not_null', False), f'{where}.not_null'),
         'default': col.get('default'), 'ref': col.get('ref')}
    if 'default' in col:
        _sql_literal(c['default'], f'{where}.default')
    if c['ref'] is not None:
        if not isinstance(c['ref'], str) or not re.match(r'^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$',
                                                         c['ref']):
            raise ValueError(f'{where}.ref must look like "table.column"')
    c['has_default'] = 'default' in col
    return c


def _col_sql(c):
    parts = [_q(c['name']), c['type']]
    if c['pk']:
        parts.append('PRIMARY KEY')
    if c['not_null']:
        parts.append('NOT NULL')
    if c['has_default']:
        parts.append('DEFAULT ' + _sql_literal(c['default'], 'default'))
    if c['ref']:
        t, col = c['ref'].split('.')
        parts.append(f'REFERENCES {_q(t)}({_q(col)})')
    return ' '.join(parts)


def _table(tbl, where):
    tbl = _dict(tbl, where, 2, 2)
    if set(tbl) != {'name', 'columns'}:
        raise ValueError(f'{where} needs exactly name and columns')
    name = _ident(tbl['name'], f'{where}.name')
    cols = [_column(c, f'{where}.columns[{i}]')
            for i, c in enumerate(_list(tbl['columns'], f'{where}.columns', 1, 64))]
    _unique([c['name'] for c in cols], f'column in {name}')
    if sum(c['pk'] for c in cols) != 1:
        raise ValueError(f'{where} must have exactly one primary-key column')
    return name, cols


def _check_ref(state, c, where):
    if c['ref']:
        t, col = c['ref'].split('.')
        if t not in state['tables'] or col not in state['tables'][t]:
            raise ValueError(f'{where}: foreign key {c["ref"]} references a missing table/column')


def _normalise_migration(m, i, allow_destructive):
    where = f'migrations[{i}]'
    m = _dict(m, where, 2, 6)
    mid = _pattern(m.get('id'), re.compile(r'^[0-9]{4}[a-z0-9_]{0,40}$'), f'{where}.id',
                   'a sortable id like "0001" or "0001_add_done"')
    if 'sql' in m:
        if set(m) != {'id', 'sql'}:
            raise ValueError(f'{where}: raw sql migrations take only id and sql')
        sql = _text(m['sql'], f'{where}.sql', 2000).strip().rstrip(';').strip()
        if ';' in sql:
            raise ValueError(f'{where}: one statement per raw migration')
        if _RAW_DESTRUCTIVE.search(sql) and not allow_destructive:
            raise ValueError(f'{where}: destructive SQL (DROP/RENAME/DELETE/TRUNCATE) refused; '
                             'set allow_destructive=true only after an approved backup')
        if _RAW_FORBIDDEN.search(sql) and not _RAW_DESTRUCTIVE.search(sql):
            raise ValueError(f'{where}: data-changing or connection SQL is not a schema migration')
        if not _RAW_SAFE.match(sql) and not (allow_destructive and _RAW_DESTRUCTIVE.search(sql)):
            raise ValueError(f'{where}: raw SQL must be CREATE ... IF NOT EXISTS or ADD COLUMN')
        return {'id': mid, 'op': 'raw', 'sql': sql}
    op = _choice(m.get('op'), _SAFE_OPS | _DESTRUCTIVE_OPS, f'{where}.op')
    if op in _DESTRUCTIVE_OPS and not allow_destructive:
        raise ValueError(f'{where}: {op} is destructive and refused; '
                         'set allow_destructive=true only after an approved backup')
    return dict(m, id=mid, op=op)


def _apply(tables, migrations, state):
    """Plan statements against an in-memory schema state; mutates state."""
    plan = []

    def emit(mid, sql):
        plan.append({'migration': mid, 'sql': sql, 'sha256': _sha(sql)})

    for name, cols in tables:
        base_id = '0000_base:' + name
        if base_id in state['applied'] or name in state['tables']:
            state['applied'].add(base_id)
            continue
        state['applied'].add(base_id)
        for c in cols:
            if c['ref'] and c['ref'].split('.')[0] != name:
                _check_ref(state, c, f'table {name}')
        body = ', '.join(_col_sql(c) for c in cols)
        emit('0000_base', f'CREATE TABLE IF NOT EXISTS {_q(name)} ({body})')
        state['tables'][name] = {c['name']: c for c in cols}
    for i, m in enumerate(migrations):
        if m['id'] in state['applied']:
            continue
        where = f'migrations[{i}]'
        op = m['op']
        if op == 'raw':
            emit(m['id'], m['sql'])
        elif op == 'create_table':
            name, cols = _table(m.get('table'), f'{where}.table')
            if name not in state['tables']:
                for c in cols:
                    _check_ref(state, c, where)
                body = ', '.join(_col_sql(c) for c in cols)
                emit(m['id'], f'CREATE TABLE IF NOT EXISTS {_q(name)} ({body})')
                state['tables'][name] = {c['name']: c for c in cols}
        elif op == 'add_column':
            t = _ident(m.get('table'), f'{where}.table')
            if t not in state['tables']:
                raise ValueError(f'{where}: table {t} does not exist')
            c = _column(m.get('column'), f'{where}.column')
            if c['pk']:
                raise ValueError(f'{where}: SQLite cannot ADD a PRIMARY KEY column')
            if c['not_null'] and (not c['has_default'] or c['default'] is None):
                raise ValueError(f'{where}: NOT NULL ADD COLUMN needs a non-null default')
            _check_ref(state, c, where)
            if c['name'] not in state['tables'][t]:
                emit(m['id'], f'ALTER TABLE {_q(t)} ADD COLUMN {_col_sql(c)}')
                state['tables'][t][c['name']] = c
        elif op == 'drop_table':
            t = _ident(m.get('table'), f'{where}.table')
            emit(m['id'], f'DROP TABLE IF EXISTS {_q(t)}')
            state['tables'].pop(t, None)
        elif op == 'drop_column':
            t = _ident(m.get('table'), f'{where}.table')
            col = _ident(m.get('column'), f'{where}.column')
            if col in state['tables'].get(t, {}):
                emit(m['id'], f'ALTER TABLE {_q(t)} DROP COLUMN {_q(col)}')
                del state['tables'][t][col]
        elif op == 'rename_table':
            t = _ident(m.get('table'), f'{where}.table')
            new = _ident(m.get('new_name'), f'{where}.new_name')
            if t in state['tables'] and new not in state['tables']:
                emit(m['id'], f'ALTER TABLE {_q(t)} RENAME TO {_q(new)}')
                state['tables'][new] = state['tables'].pop(t)
        elif op == 'rename_column':
            t = _ident(m.get('table'), f'{where}.table')
            col = _ident(m.get('column'), f'{where}.column')
            new = _ident(m.get('new_name'), f'{where}.new_name')
            cols = state['tables'].get(t, {})
            if col in cols and new not in cols:
                emit(m['id'], f'ALTER TABLE {_q(t)} RENAME COLUMN {_q(col)} TO {_q(new)}')
                cols[new] = dict(cols.pop(col), name=new)
        state['applied'].add(m['id'])
    return plan


def sql_schema(*, tables=None, migrations=None, allow_destructive=False, **extra):
    """SQLite DDL with primary/foreign keys plus ordered, non-destructive migrations.

    tables: [{'name', 'columns': [{'name','type','pk','not_null','default','ref'}]}].
    migrations: ordered [{'id': '0001...', 'op': 'create_table'|'add_column', ...}] or
    [{'id', 'sql'}] (raw CREATE ... IF NOT EXISTS / ADD COLUMN only). DROP/RENAME are
    refused unless allow_destructive=true. Idempotency: planning the same migration list
    twice on the resulting state yields no new statements and identical hashes.
    """
    _no_extra(extra)
    allow_destructive = _bool(allow_destructive, 'allow_destructive')
    if tables is None:
        tables = [
            {'name': 'note', 'columns': [
                {'name': 'id', 'type': 'INTEGER', 'pk': True},
                {'name': 'title', 'type': 'TEXT', 'not_null': True}]},
            {'name': 'tag', 'columns': [
                {'name': 'id', 'type': 'INTEGER', 'pk': True},
                {'name': 'note_id', 'type': 'INTEGER', 'not_null': True, 'ref': 'note.id'},
                {'name': 'label', 'type': 'TEXT', 'not_null': True}]},
        ]
    if migrations is None:
        migrations = [
            {'id': '0001_add_done', 'op': 'add_column', 'table': 'note',
             'column': {'name': 'done', 'type': 'INTEGER', 'not_null': True, 'default': 0}},
            {'id': '0002_audit', 'op': 'create_table', 'table': {'name': 'audit', 'columns': [
                {'name': 'id', 'type': 'INTEGER', 'pk': True},
                {'name': 'note_id', 'type': 'INTEGER', 'ref': 'note.id'},
                {'name': 'action', 'type': 'TEXT', 'default': 'created'}]}},
            {'id': '0003_tag_index',
             'sql': 'CREATE INDEX IF NOT EXISTS "tag_note_idx" ON "tag" ("note_id")'},
        ]
    tables = [_table(t, f'tables[{i}]')
              for i, t in enumerate(_list(tables, 'tables', 0, 32))]
    _unique([n for n, _ in tables], 'table name')
    migrations = [_normalise_migration(m, i, allow_destructive)
                  for i, m in enumerate(_list(migrations, 'migrations', 0, 100))]
    ids = [m['id'] for m in migrations]
    _unique(ids, 'migration id')
    if ids != sorted(ids):
        raise ValueError('migrations must be listed in ascending id order')

    state = {'tables': {}, 'applied': set()}
    plan = _apply(tables, migrations, state)
    second = _apply(tables, migrations, state)
    fresh = _apply(tables, migrations, {'tables': {}, 'applied': set()})
    hashes = [p['sha256'] for p in plan]
    idempotent = not second and hashes == [p['sha256'] for p in fresh]
    ddl = ';\n'.join(p['sql'] for p in plan) + (';\n' if plan else '')
    destructive = [p['migration'] for p in plan if _RAW_DESTRUCTIVE.search(p['sql'])]
    schema = {t: sorted(cols) for t, cols in sorted(state['tables'].items())}
    return _pack('sql_schema', {
        'ddl': ddl, 'plan': plan, 'plan_sha256': _sha('\n'.join(hashes)),
        'idempotent': idempotent, 'second_pass_statements': len(second),
        'final_schema': schema, 'destructive_statements': destructive,
        'files': {'schema.sql': ddl}, 'executed': False, 'note': IN_MEMORY_NOTE,
    }, ['SQLite dialect; identifiers are validated lowercase names and double-quoted',
        'idempotency is simulated on an in-memory schema model (applied ids + existing '
        'tables/columns), not on a live database',
        'raw SQL migrations are tracked by id only; their effect on the schema model is not parsed'],
       ['tables <= 32, columns <= 64 each, migrations <= 100',
        'DROP/RENAME/DELETE/TRUNCATE refused unless allow_destructive=true; '
        'INSERT/UPDATE/PRAGMA/ATTACH always refused',
        'SQL is generated text only; nothing is executed against a database', IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.05 session_tokens

_DEMO_KEY = 'demo-only-key-not-a-secret-0123456789'
_SUBJECT_RE = re.compile(r'^[A-Za-z0-9_.@-]{1,64}$')
_SCOPE_RE = re.compile(r'^[a-z][a-z0-9_.:-]{0,31}$')
_TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{1,3000}\.[A-Za-z0-9_-]{43}$')
_MAX_TS = 4_102_444_800  # 2100-01-01


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _key_bytes(key):
    _text(key, 'key', 512)
    if len(key) < 16:
        raise ValueError('key must be at least 16 characters')
    return key.encode('utf-8')


def _sign(key, payload_part):
    return _b64(hmac.new(key, payload_part.encode('ascii'), hashlib.sha256).digest())


def _issue(key, subject, scopes, issued_at, ttl):
    payload = {'v': 1, 'sub': subject, 'scope': scopes, 'iat': issued_at,
               'exp': issued_at + ttl}
    part = _b64(_canon(payload).encode('utf-8'))
    return part + '.' + _sign(key, part), payload


def _verify(key, token, now, required_scope, leeway):
    if not isinstance(token, str) or not _TOKEN_RE.match(token):
        return {'valid': False, 'reason': 'malformed'}
    part, sig = token.split('.')
    if not hmac.compare_digest(_sign(key, part), sig):
        return {'valid': False, 'reason': 'bad_signature'}
    try:
        payload = json.loads(_unb64(part).decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return {'valid': False, 'reason': 'malformed'}
    if not isinstance(payload, dict) or payload.get('v') != 1:
        return {'valid': False, 'reason': 'malformed'}
    if now >= payload.get('exp', 0) + leeway:
        return {'valid': False, 'reason': 'expired', 'payload': payload}
    if payload.get('iat', 0) > now + leeway:
        return {'valid': False, 'reason': 'not_yet_valid', 'payload': payload}
    if required_scope is not None and required_scope not in payload.get('scope', []):
        return {'valid': False, 'reason': 'wrong_scope', 'payload': payload}
    return {'valid': True, 'reason': 'ok', 'payload': payload}


def session_tokens(*, action='demo', key=None, subject='user_1', scopes=('notes:read',),
                   issued_at=1_700_000_000, ttl=3600, token=None, now=None,
                   required_scope=None, leeway=0, **extra):
    """HMAC-SHA256 signed session tokens: issue, verify, or a self-checking demo.

    The caller supplies the key (>= 16 chars); it is never stored, logged or returned.
    Time is supplied by the caller (issued_at, now: Unix seconds) so results are
    deterministic. Token = base64url(canonical JSON payload) '.' base64url(HMAC).
    Verification compares the whole signature text in constant time, so changing any
    character fails; it then rejects expired, not-yet-valid and wrong-scope tokens.
    """
    _no_extra(extra)
    action = _choice(action, {'demo', 'issue', 'verify'}, 'action')
    if key is None:
        if action != 'demo':
            raise ValueError('key is required for issue/verify (supplied by the caller)')
        key = _DEMO_KEY
    kb = _key_bytes(key)
    subject = _pattern(subject, _SUBJECT_RE, 'subject', '1-64 chars of A-Z a-z 0-9 _ . @ -')
    scopes = [_pattern(s, _SCOPE_RE, f'scopes[{i}]', 'a lowercase scope like notes:read')
              for i, s in enumerate(_list(scopes, 'scopes', 1, 16))]
    _unique(scopes, 'scope')
    issued_at = _int(issued_at, 0, _MAX_TS, 'issued_at')
    ttl = _int(ttl, 1, 30 * 86400, 'ttl')
    leeway = _int(leeway, 0, 300, 'leeway')
    if required_scope is not None:
        required_scope = _pattern(required_scope, _SCOPE_RE, 'required_scope', 'a scope')
    limits = ['key >= 16 chars, ttl <= 30 days, leeway <= 300 s, scopes <= 16, token <= 3000 chars',
              'no revocation list, rotation or refresh tokens; payload is signed, not encrypted',
              'the key never appears in the output; callers must keep it out of logs themselves']
    assumptions = ['caller supplies the current time; no clock is read',
                   'HMAC-SHA256 over the base64url payload text; constant-time comparison']

    if action == 'issue':
        tok, payload = _issue(kb, subject, scopes, issued_at, ttl)
        return _pack('session_tokens', {'action': 'issue', 'token': tok, 'payload': payload,
                                        'expires_at': payload['exp']}, assumptions, limits)
    if action == 'verify':
        if token is None:
            raise ValueError('token is required for verify')
        _text(token, 'token', 3100)
        if now is None:
            raise ValueError('now is required for verify (Unix seconds)')
        now = _int(now, 0, _MAX_TS, 'now')
        res = _verify(kb, token, now, required_scope, leeway)
        return _pack('session_tokens', dict(res, action='verify'), assumptions, limits)
    # demo: issue one token, then check it against the main failure modes
    tok, payload = _issue(kb, subject, scopes, issued_at, ttl)
    i = len(tok) // 3
    tampered = tok[:i] + ('A' if tok[i] != 'A' else 'B') + tok[i + 1:]
    cases = {
        'fresh': _verify(kb, tok, issued_at + 1, scopes[0], leeway),
        'expired': _verify(kb, tok, issued_at + ttl + leeway, scopes[0], leeway),
        'tampered': _verify(kb, tampered, issued_at + 1, scopes[0], leeway),
        'wrong_scope': _verify(kb, tok, issued_at + 1, 'admin:all', leeway),
        'wrong_key': _verify(b'another-key-0123456789', tok, issued_at + 1, scopes[0], leeway),
    }
    summary = {k: {'valid': v['valid'], 'reason': v['reason']} for k, v in cases.items()}
    return _pack('session_tokens', {
        'action': 'demo', 'token': tok, 'payload': payload, 'cases': summary,
        'demo_key_used': key == _DEMO_KEY,
        'all_as_expected': summary['fresh']['valid'] and not any(
            summary[k]['valid'] for k in ('expired', 'tampered', 'wrong_scope', 'wrong_key')),
    }, assumptions + ['demo mode uses a fixed, public demo key unless one is supplied'], limits)


# --------------------------------------------------------------------------- 10.06 router_spec

_ROUTE_RE = re.compile(r'^#/[a-z0-9/-]{0,62}$')


def router_spec(*, pages=None, routes=None, start='#/', navigation=None, **extra):
    """Hash-router spec for a multi-page static app with history simulation.

    pages: [{'id': slug, 'component': CamelName, 'links': ['#/path', ...]}]
    routes: [{'path': '#/...', 'page': page id}] (duplicate paths are rejected)
    navigation: ['#/path' (push) | 'back' | 'forward', ...] simulated on a history stack.
    Reports pages unreachable from `start`, pages without a route and broken links.
    """
    _no_extra(extra)
    if pages is None:
        pages = [
            {'id': 'home', 'component': 'HomePage', 'links': ['#/about', '#/contact']},
            {'id': 'about', 'component': 'AboutPage', 'links': ['#/', '#/contact']},
            {'id': 'contact', 'component': 'ContactPage', 'links': ['#/']},
            {'id': 'archive', 'component': 'ArchivePage', 'links': ['#/']},
        ]
    if routes is None:
        routes = [{'path': '#/', 'page': 'home'}, {'path': '#/about', 'page': 'about'},
                  {'path': '#/contact', 'page': 'contact'},
                  {'path': '#/archive', 'page': 'archive'}]
    if navigation is None:
        navigation = ['#/about', '#/contact', 'back', 'back', 'forward']
    pages = _list(pages, 'pages', 1, 50)
    page_map = {}
    for i, p in enumerate(pages):
        p = _dict(p, f'pages[{i}]', 2, 3)
        if set(p) - {'id', 'component', 'links'} or 'id' not in p or 'component' not in p:
            raise ValueError(f'pages[{i}] needs id, component and optional links')
        pid = _pattern(p['id'], _SLUG_RE, f'pages[{i}].id', 'a lowercase slug')
        if pid in page_map:
            raise ValueError(f'duplicate page id: {pid}')
        comp = _pattern(p['component'], re.compile(r'^[A-Z][A-Za-z0-9]{0,39}$'),
                        f'pages[{i}].component', 'a CamelCase component name')
        links = [_pattern(l, _ROUTE_RE, f'pages[{i}].links[{j}]', 'a hash route like #/about')
                 for j, l in enumerate(_list(p.get('links', []), f'pages[{i}].links', 0, 50))]
        page_map[pid] = {'component': comp, 'links': links}
    route_map = {}
    for i, r in enumerate(_list(routes, 'routes', 1, 100)):
        r = _dict(r, f'routes[{i}]', 2, 2)
        if set(r) != {'path', 'page'}:
            raise ValueError(f'routes[{i}] needs exactly path and page')
        path = _pattern(r['path'], _ROUTE_RE, f'routes[{i}].path', 'a hash route like #/about')
        if path in route_map:
            raise ValueError(f'duplicate route: {path}')
        if r['page'] not in page_map:
            raise ValueError(f'routes[{i}].page {r["page"]!r} is not a known page')
        route_map[path] = r['page']
    start = _pattern(start, _ROUTE_RE, 'start', 'a hash route')
    if start not in route_map:
        raise ValueError('start must be one of the routes')
    navigation = _list(navigation, 'navigation', 0, 200)

    broken = sorted({(pid, l) for pid, p in page_map.items() for l in p['links']
                     if l not in route_map})
    seen, queue = {start}, [start]
    while queue:
        path = queue.pop(0)
        for link in page_map[route_map[path]]['links']:
            if link in route_map and link not in seen:
                seen.add(link)
                queue.append(link)
    reached_pages = {route_map[p] for p in seen}
    routed_pages = set(route_map.values())
    unreachable = sorted(set(page_map) - reached_pages)
    orphans = sorted(set(page_map) - routed_pages)

    stack, idx, trail, events = [start], 0, [start], []
    for i, step in enumerate(navigation):
        if step == 'back':
            if idx > 0:
                idx -= 1
                events.append({'step': step, 'at': stack[idx]})
            else:
                events.append({'step': step, 'ignored': 'no earlier entry'})
        elif step == 'forward':
            if idx < len(stack) - 1:
                idx += 1
                events.append({'step': step, 'at': stack[idx]})
            else:
                events.append({'step': step, 'ignored': 'no later entry'})
        else:
            path = _pattern(step, _ROUTE_RE, f'navigation[{i}]',
                            "a hash route, 'back' or 'forward'")
            if path not in route_map:
                events.append({'step': step, 'ignored': 'unknown route (404)'})
            else:
                del stack[idx + 1:]
                stack.append(path)
                idx += 1
                events.append({'step': step, 'at': path})
        trail.append(stack[idx])
    table = [{'path': p, 'page': route_map[p], 'component': page_map[route_map[p]]['component']}
             for p in sorted(route_map)]
    spec_json = json.dumps({'mode': 'hash', 'start': start, 'routes': table},
                           ensure_ascii=False, indent=2)
    json.loads(spec_json)
    return _pack('router_spec', {
        'routes': table, 'start': start, 'unreachable_pages': unreachable,
        'pages_without_route': orphans,
        'broken_links': [{'page': p, 'link': l} for p, l in broken],
        'history': {'stack': stack, 'index': idx, 'current': stack[idx]},
        'trail': trail, 'events': events, 'files': {'routes.json': spec_json + '\n'},
        'note': IN_MEMORY_NOTE,
    }, ['reachability = breadth-first search over page links starting at `start`',
        'history behaves like the browser: a new push discards forward entries',
        'navigating to an unknown route is ignored and reported (404), not pushed'],
       ['pages <= 50, routes <= 100, links <= 50 per page, navigation <= 200 steps',
        'static paths only: no route parameters, guards or lazy loading',
        'specification and simulation only; no router JavaScript is executed'])


# --------------------------------------------------------------------------- 10.07 feature_tests

_EXC_NAMES = {'ValueError', 'TypeError', 'KeyError', 'IndexError', 'ZeroDivisionError',
              'ArithmeticError', 'LookupError', 'RuntimeError', 'OverflowError', 'Exception'}


def _literal(value, name, depth=0):
    if depth > 3:
        raise ValueError(f'{name} is nested too deeply (max 3)')
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) >= 10 ** 15:
            raise ValueError(f'{name} integer is too large')
        return value
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            raise ValueError(f'{name} must be finite')
        return value
    if isinstance(value, str):
        return _text(value, name, 200, allow_empty=True)
    if isinstance(value, (list, tuple)):
        if len(value) > 20:
            raise ValueError(f'{name} has more than 20 items')
        return [_literal(v, f'{name}[{i}]', depth + 1) for i, v in enumerate(value)]
    if isinstance(value, dict):
        if len(value) > 20 or not all(isinstance(k, str) and len(k) <= 40 for k in value):
            raise ValueError(f'{name} must be a dict of <= 20 short string keys')
        return {k: _literal(v, f'{name}.{k}', depth + 1) for k, v in value.items()}
    raise ValueError(f'{name} must be a JSON-like literal (null, bool, number, string, list, dict)')


def _mutate(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, str):
        return value + '_mutated'
    if value is None:
        return 0
    if isinstance(value, list):
        return value + [0]
    return dict(value, _mutated=1)


def _has_float(value):
    if isinstance(value, float):
        return True
    if isinstance(value, list):
        return any(_has_float(v) for v in value)
    if isinstance(value, dict):
        return any(_has_float(v) for v in value.values())
    return False


def _render_tests(mod, fn, params, examples, invalid):
    cls = _camel(fn)
    lines = [f'"""Generated tests for {mod}.{fn} (one per example, one per invalid input)."""',
             'import unittest', '', f'from {mod} import {fn}', '', '',
             f'class Test{cls}(unittest.TestCase):']
    for i, ex in enumerate(examples, 1):
        call = f'{fn}(' + ', '.join(repr(a) for a in ex['args']) + ')'
        lines.append(f'    def test_example_{i}(self):')
        if isinstance(ex['expected'], float):
            lines.append(f'        self.assertAlmostEqual({call}, {ex["expected"]!r}, places=7)')
        else:
            lines.append(f'        self.assertEqual({call}, {ex["expected"]!r})')
        lines.append('')
    for i, bad in enumerate(invalid, 1):
        call = f'{fn}(' + ', '.join(repr(a) for a in bad['args']) + ')'
        lines += [f'    def test_invalid_{i}(self):',
                  f'        with self.assertRaises({bad["raises"]}):',
                  f'            {call}', '']
    cases = '[' + ', '.join(f'({tuple(ex["args"])!r}, {ex["expected"]!r})' for ex in examples) + ']'
    bad_cases = '[' + ', '.join(f'({tuple(b["args"])!r}, {b["raises"]})' for b in invalid) + ']'
    lines += ['    def test_integration_all_examples_after_invalid_calls(self):',
              '        """Invalid calls must not corrupt later valid calls."""',
              f'        for args, exc in {bad_cases}:',
              '            with self.assertRaises(exc):',
              f'                {fn}(*args)',
              f'        for args, expected in {cases}:',
              '            with self.subTest(args=args):',
              f'                self.assertEqual({fn}(*args), expected)', '', '',
              "if __name__ == '__main__':", '    unittest.main()', '']
    return '\n'.join(lines), len(params)


def _asserted_values(text):
    """Map test_example_N -> asserted expected literal, read back via ast."""
    out = {}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_example_'):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in ('assertEqual', 'assertAlmostEqual')):
                    out[node.name] = ast.literal_eval(sub.args[1])
    return out


def feature_tests(*, function=None, **extra):
    """Generate a unittest module for one function spec and self-check it.

    function: {'module': ident, 'name': ident, 'params': [ident...],
               'examples': [{'args': [...], 'expected': value}],
               'invalid': [{'args': [...], 'raises': 'ValueError'|...}]}.
    Output: one test per example, one per invalid input and one integration-style test.
    Self-check: the text parses with ast, asserted values read back equal the spec, and a
    mutant with altered expected values asserts different values (so it would fail).
    """
    _no_extra(extra)
    if function is None:
        function = {'module': 'mathutils', 'name': 'safe_div', 'params': ['a', 'b'],
                    'examples': [{'args': [6, 3], 'expected': 2.0},
                                 {'args': [1, 4], 'expected': 0.25},
                                 {'args': [0, 5], 'expected': 0.0}],
                    'invalid': [{'args': [1, 0], 'raises': 'ZeroDivisionError'},
                                {'args': ['x', 1], 'raises': 'TypeError'}]}
    f = _dict(function, 'function', 4, 5)
    bad = set(f) - {'module', 'name', 'params', 'examples', 'invalid'}
    missing = {'module', 'name', 'params', 'examples'} - set(f)
    if bad or missing:
        raise ValueError('function needs module, name, params, examples and optional invalid')
    mod = _ident(f['module'], 'function.module')
    fn = _ident(f['name'], 'function.name')
    params = [_ident(p, f'function.params[{i}]')
              for i, p in enumerate(_list(f['params'], 'function.params', 0, 8))]
    _unique(params, 'param')
    examples = []
    for i, ex in enumerate(_list(f['examples'], 'function.examples', 1, 20)):
        ex = _dict(ex, f'examples[{i}]', 2, 2)
        if set(ex) != {'args', 'expected'}:
            raise ValueError(f'examples[{i}] needs exactly args and expected')
        args = _literal(_list(ex['args'], f'examples[{i}].args', len(params), len(params)),
                        f'examples[{i}].args')
        examples.append({'args': args, 'expected': _literal(ex['expected'],
                                                            f'examples[{i}].expected')})
    invalid = []
    for i, b in enumerate(_list(f.get('invalid', []), 'function.invalid', 0, 20)):
        b = _dict(b, f'invalid[{i}]', 2, 2)
        if set(b) != {'args', 'raises'}:
            raise ValueError(f'invalid[{i}] needs exactly args and raises')
        invalid.append({'args': _literal(_list(b['args'], f'invalid[{i}].args', 0, 8),
                                         f'invalid[{i}].args'),
                        'raises': _choice(b['raises'], _EXC_NAMES, f'invalid[{i}].raises')})
    for i, ex in enumerate(examples):
        if _has_float(ex['expected']) and not isinstance(ex['expected'], float):
            raise ValueError(f'examples[{i}].expected: floats are only supported at top level')

    text, _ = _render_tests(mod, fn, params, examples, invalid)
    ast.parse(text)
    asserted = _asserted_values(text)
    roundtrip = all(asserted.get(f'test_example_{i}') == ex['expected']
                    for i, ex in enumerate(examples, 1))
    mutant_examples = [dict(ex, expected=_mutate(ex['expected'])) for ex in examples]
    mutant_text, _ = _render_tests(mod, fn, params, mutant_examples, invalid)
    mutant_vals = _asserted_values(mutant_text)
    detected = sum(1 for i, ex in enumerate(examples, 1)
                   if mutant_vals.get(f'test_example_{i}') != ex['expected'])
    test_names = [n.name for n in ast.walk(ast.parse(text))
                  if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    return _pack('feature_tests', {
        'files': {f'test_{fn}.py': text}, 'test_names': test_names,
        'counts': {'examples': len(examples), 'invalid': len(invalid), 'integration': 1,
                   'total': len(test_names)},
        'self_check': {'parses': True, 'asserted_values_match_spec': roundtrip,
                       'mutants': len(examples), 'mutants_detected': detected,
                       'all_mutants_detected': detected == len(examples)},
        'written': False, 'note': IN_MEMORY_NOTE,
    }, ['examples are pure: same args give the same output; positional args only',
        'values are JSON-like literals rendered with repr(); float results use assertAlmostEqual',
        'mutation self-check compares asserted literals statically; the target function is '
        'never imported or run here'],
       ['params <= 8, examples <= 20, invalid cases <= 20, literals nested <= 3 levels',
        'allowed exception names: ' + ', '.join(sorted(_EXC_NAMES)),
        'floats nested inside lists/dicts are refused (exact equality would be fragile)',
        IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.08 docs_from_code

_DEMO_SOURCE = '''"""Notes CLI helpers.

Commands: add (create a note) and list (show notes).
"""


def add(store, title: str) -> dict:
    """Add a note titled `title` and return it."""
    return store.add(title)


def list_notes(store, limit: int = 10):
    """Return at most `limit` notes."""
    return store.all()[:limit]


def purge(store):
    return store.clear()


class Store:
    """In-memory note store."""

    def add(self, title):
        """Append one note."""

    def _private(self):
        pass
'''


def _signature(node):
    prefix = 'async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def '
    sig = prefix + node.name + '(' + ast.unparse(node.args) + ')'
    if node.returns is not None:
        sig += ' -> ' + ast.unparse(node.returns)
    return sig


def _md(text):
    return html.escape(text, quote=False)


def docs_from_code(*, source=None, module_name='notes_cli', cli=None, **extra):
    """Markdown docs from module/function/class docstrings and signatures (via ast).

    cli: argparse-like spec {'prog': name, 'commands': [{'name': cmd, 'help': text}]}.
    A command counts as documented only when its name appears as a whole word in some
    docstring of the source; the spec's own help text does not count.
    """
    _no_extra(extra)
    if source is None:
        source = _DEMO_SOURCE
        if cli is None:
            cli = {'prog': 'notes', 'commands': [{'name': 'add', 'help': 'add a note'},
                                                 {'name': 'list', 'help': 'list notes'},
                                                 {'name': 'purge', 'help': 'delete all'}]}
    source = _text(source, 'source', MAX_SOURCE)
    module_name = _pattern(module_name, re.compile(r'^[A-Za-z_][A-Za-z0-9_.]{0,79}$'),
                           'module_name', 'a dotted module name')
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f'source does not parse: {exc.msg} (line {exc.lineno})') from None
    commands = []
    prog = None
    if cli is not None:
        cli = _dict(cli, 'cli', 1, 2)
        if set(cli) - {'prog', 'commands'} or 'commands' not in cli:
            raise ValueError('cli needs commands and optional prog')
        prog = _pattern(cli.get('prog', module_name), re.compile(r'^[A-Za-z0-9_.-]{1,40}$'),
                        'cli.prog', 'a program name')
        for i, c in enumerate(_list(cli['commands'], 'cli.commands', 0, 100)):
            if isinstance(c, str):
                c = {'name': c}
            c = _dict(c, f'cli.commands[{i}]', 1, 2)
            if set(c) - {'name', 'help'} or 'name' not in c:
                raise ValueError(f'cli.commands[{i}] needs name and optional help')
            commands.append({'name': _pattern(c['name'], _SLUG_RE, f'cli.commands[{i}].name',
                                              'a lowercase command name'),
                             'help': _text(c.get('help', ''), f'cli.commands[{i}].help', 300,
                                           allow_empty=True)})
        _unique([c['name'] for c in commands], 'cli command')

    mod_doc = ast.get_docstring(tree) or ''
    items, missing_doc, docstrings = [], [], [mod_doc]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
            doc = ast.get_docstring(node) or ''
            docstrings.append(doc)
            items.append({'kind': 'function', 'name': node.name, 'signature': _signature(node),
                          'doc': doc, 'line': node.lineno})
            if not doc:
                missing_doc.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
            doc = ast.get_docstring(node) or ''
            docstrings.append(doc)
            if not doc:
                missing_doc.append(node.name)
            methods = []
            for sub in node.body:
                if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and (not sub.name.startswith('_') or sub.name == '__init__')):
                    mdoc = ast.get_docstring(sub) or ''
                    docstrings.append(mdoc)
                    methods.append({'name': sub.name, 'signature': _signature(sub), 'doc': mdoc})
                    if not mdoc:
                        missing_doc.append(f'{node.name}.{sub.name}')
            items.append({'kind': 'class', 'name': node.name, 'doc': doc, 'line': node.lineno,
                          'methods': methods})
    if len(items) > 500:
        raise ValueError('source defines more than 500 public items')

    corpus = '\n'.join(docstrings)
    undocumented = [c['name'] for c in commands
                    if not re.search(r'(?<![\w-])' + re.escape(c['name']) + r'(?![\w-])', corpus)]

    def fence(sig):
        return '```python\n' + sig.replace('```', '`​``') + '\n```'

    md = [f'# `{module_name}`', '']
    if mod_doc:
        md += [_md(mod_doc), '']
    for it in items:
        if it['kind'] == 'function':
            md += [f'## {it["name"]}', '', fence(it['signature']), '',
                   _md(it['doc']) if it['doc'] else '_No docstring._', '']
        else:
            md += [f'## class {it["name"]}', '', _md(it['doc']) if it['doc'] else '_No docstring._', '']
            for m in it['methods']:
                md += [f'### {it["name"]}.{m["name"]}', '', fence(m['signature']), '',
                       _md(m['doc']) if m['doc'] else '_No docstring._', '']
    if commands:
        md += [f'## CLI: `{prog}`', '', '| command | help | documented in code |', '|---|---|---|']
        for c in commands:
            ok = 'yes' if c['name'] not in undocumented else '**no**'
            md.append(f'| `{c["name"]}` | {_md(c["help"]).replace("|", "&#124;")} | {ok} |')
        md.append('')
    markdown = '\n'.join(md)
    return _pack('docs_from_code', {
        'markdown': markdown, 'files': {'DOCS.md': markdown}, 'module_docstring': mod_doc,
        'items': items, 'missing_docstrings': missing_doc,
        'cli_commands': [c['name'] for c in commands], 'undocumented_cli_commands': undocumented,
        'cli_fully_documented': not undocumented, 'note': IN_MEMORY_NOTE,
    }, ['source is parsed with ast only; it is never imported or executed',
        'public = top-level names and methods not starting with "_" (plus __init__)',
        'a CLI command is documented when its name appears as a whole word in a docstring'],
       ['source <= 200000 chars, <= 500 public items, <= 100 CLI commands',
        'docstrings are HTML-escaped into Markdown; reST/Google sections are not parsed',
        'nested functions and module-level variables are not documented', IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.09 package_manifest

_PATH_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$')
_DEP_RE = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]{0,63})==(\d{1,6}(?:\.\d{1,6}){1,3})$')


def _file_entries(files):
    return [{'path': p, 'sha256': _sha(files[p]), 'bytes': len(files[p].encode('utf-8'))}
            for p in sorted(files)]


def package_manifest(*, name='notes_app', version='1.0.0', files=None, dependencies=None,
                     tamper=None, **extra):
    """Release manifest with sha256 of supplied file contents and pinned dependencies.

    files: {relative_path: text}; dependencies: ['pkg==1.2.3', ...] (exact pins only).
    Then simulates installing into a fresh in-memory environment (a dict) and verifies
    the installed hashes match. `tamper` ({path: text}) replaces contents in transit to
    show that verification fails.
    """
    _no_extra(extra)
    name = _ident(name, 'name')
    version = _pattern(version, _SEMVER_RE, 'version', 'SemVer like 1.0.0 or 1.0.0-rc.1')
    if files is None:
        files = {'notes_app.py': '"""Notes app."""\n\n\ndef main():\n    return 0\n',
                 'README.md': '# notes_app\n'}
    files = _dict(files, 'files', 1, 200)
    total = 0
    for p, text in files.items():
        _pattern(p, _PATH_RE, f'files key {p!r}', 'a relative POSIX path without .. or drive')
        if '..' in p.split('/') or len(p) > 160:
            raise ValueError(f'files key {p!r} must not contain .. and be <= 160 chars')
        _text(text, f'files[{p!r}]', 500_000, allow_empty=True)
        total += len(text)
    if total > 2_000_000:
        raise ValueError('total file content must be <= 2,000,000 characters')
    if dependencies is None:
        dependencies = []
    deps = []
    for i, d in enumerate(_list(dependencies, 'dependencies', 0, 100)):
        if not isinstance(d, str) or not _DEP_RE.match(d.strip()):
            raise ValueError(f'dependencies[{i}] {d!r} is not pinned; use exact name==X.Y.Z')
        pkg, ver = _DEP_RE.match(d.strip()).groups()
        deps.append({'name': pkg.lower(), 'pin': '==' + ver})
    _unique([d['name'] for d in deps], 'dependency')
    deps.sort(key=lambda d: d['name'])
    if tamper is not None:
        tamper = _dict(tamper, 'tamper', 1, 200)
        for p, text in tamper.items():
            if p not in files:
                raise ValueError(f'tamper path {p!r} is not a release file')
            _text(text, f'tamper[{p!r}]', 500_000, allow_empty=True)

    body = {'name': name, 'version': version, 'files': _file_entries(files),
            'dependencies': deps}
    manifest = dict(body, manifest_sha256=_sha(_canon(body)))
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    loaded = json.loads(manifest_json)

    # install simulation into a fresh in-memory environment
    env = {'site': {}, 'requirements': {}}
    for p in sorted(files):
        env['site'][f'{name}/{p}'] = (tamper or {}).get(p, files[p])
    for d in loaded['dependencies']:
        env['requirements'][d['name']] = d['pin']
    installed = {e['path']: _sha(env['site'][f'{name}/{e["path"]}']) for e in loaded['files']}
    mismatched = sorted(e['path'] for e in loaded['files'] if installed[e['path']] != e['sha256'])
    recomputed = _sha(_canon({k: loaded[k] for k in ('name', 'version', 'files',
                                                     'dependencies')}))
    verified = not mismatched and recomputed == loaded['manifest_sha256'] and (
        env['requirements'] == {d['name']: d['pin'] for d in deps})
    return _pack('package_manifest', {
        'manifest': loaded, 'files': {'release-manifest.json': manifest_json + '\n'},
        'install_simulation': {'environment': 'fresh in-memory dict', 'files_installed':
                               len(env['site']), 'mismatched_files': mismatched,
                               'manifest_hash_ok': recomputed == loaded['manifest_sha256'],
                               'verified': verified},
        'verified': verified, 'written': False, 'note': IN_MEMORY_NOTE,
    }, ['file hashes are sha256 of the UTF-8 text supplied by the caller',
        'dependencies must be exact pins (name==X.Y[.Z[.W]]); they are recorded, not resolved',
        'the manifest hash covers name, version, files and dependencies in canonical JSON'],
       ['<= 200 files, <= 2,000,000 chars total; text files only (no binary payloads)',
        'no signing key, no wheel/sdist build, no dependency download or resolution',
        'install is simulated in a dict; nothing is installed on the machine', IN_MEMORY_NOTE])


# --------------------------------------------------------------------------- 10.10 deploy_plan

_SECRET_RE = re.compile(r'^[A-Z][A-Z0-9_]{1,63}$')
_STAGING_STEPS = ['build_artifact', 'deploy_staging', 'smoke_test_staging',
                  'rollback_drill_staging']
_STEP_RESULTS = {'pass', 'fail', 'skipped'}


def deploy_plan(*, app='notes_app', version='1.0.0', previous_version='0.9.0', secrets=None,
                staging_results=None, approved_by=None, **extra):
    """Staged staging -> production plan with secret isolation and a rollback gate.

    secrets: list of secret NAMES only (values are refused). staging_results:
    {step: 'pass'|'fail'|'skipped'} for the staging steps (default: all pass).
    Production is refused unless the rollback drill passed in staging, and blocked
    until approved_by names who approved. This simulates the plan; it deploys nothing.
    """
    _no_extra(extra)
    app = _ident(app, 'app')
    version = _pattern(version, _SEMVER_RE, 'version', 'SemVer')
    previous_version = _pattern(previous_version, _SEMVER_RE, 'previous_version', 'SemVer')
    if previous_version == version:
        raise ValueError('previous_version must differ from version (rollback target)')
    if secrets is None:
        secrets = ['DATABASE_URL', 'SESSION_SIGNING_KEY']
    if isinstance(secrets, dict):
        raise ValueError('secrets must be a list of names only; secret values are never accepted')
    secrets = [_pattern(s, _SECRET_RE, f'secrets[{i}]', 'an UPPER_SNAKE secret name')
               for i, s in enumerate(_list(secrets, 'secrets', 0, 50))]
    _unique(secrets, 'secret')
    results = {s: 'pass' for s in _STAGING_STEPS}
    if staging_results is not None:
        staging_results = _dict(staging_results, 'staging_results', 0, len(_STAGING_STEPS))
        for k, v in staging_results.items():
            _choice(k, set(_STAGING_STEPS), 'staging_results key')
            results[k] = _choice(v, _STEP_RESULTS, f'staging_results[{k}]')
    if approved_by is not None:
        approved_by = _pattern(approved_by, _SUBJECT_RE, 'approved_by', 'an approver name')

    refs = [f'secret_ref:{s}' for s in secrets]

    def step(sid, stage, action, uses_secrets=False, requires=()):
        return {'id': sid, 'stage': stage, 'action': action,
                'secrets': [r.replace('secret_ref:', f'secret_ref:{stage}/') for r in refs]
                if uses_secrets else [], 'requires': list(requires)}

    plan = [
        step('build_artifact', 'build', f'build {app} {version} once; record artifact sha256'),
        step('deploy_staging', 'staging', f'deploy the same artifact {version} to staging',
             True, ['build_artifact']),
        step('smoke_test_staging', 'staging', 'run smoke tests against staging',
             True, ['deploy_staging']),
        step('rollback_drill_staging', 'staging',
             f'roll staging back to {previous_version}, verify, then redeploy {version}',
             True, ['smoke_test_staging']),
        step('approval_gate', 'gate', 'human approval recorded in chat/ticket before production',
             False, ['rollback_drill_staging']),
        step('deploy_production', 'production', f'deploy artifact {version} to production',
             True, ['approval_gate']),
        step('smoke_test_production', 'production', 'run smoke tests against production',
             True, ['deploy_production']),
        step('rollback_ready_production', 'production',
             f'keep {previous_version} ready; roll back automatically if smoke tests fail',
             False, ['smoke_test_production']),
    ]

    log, status, reason = [], None, None
    for sid in _STAGING_STEPS:
        log.append({'step': sid, 'result': results[sid]})
        if results[sid] != 'pass':
            break
    staging_ok = all(results[s] == 'pass' for s in _STAGING_STEPS[:3])
    rollback_ok = results['rollback_drill_staging'] == 'pass'
    if not staging_ok:
        status, reason = 'refused', 'staging build/deploy/smoke did not pass'
    elif not rollback_ok:
        status, reason = 'refused', ('rollback was not verified in staging '
                                     f'(rollback_drill_staging = {results["rollback_drill_staging"]})')
    elif approved_by is None:
        status, reason = 'blocked', 'awaiting approval at approval_gate'
        log.append({'step': 'approval_gate', 'result': 'waiting'})
    else:
        status, reason = 'ready_simulated', f'approved by {approved_by}; production steps simulated'
        log.append({'step': 'approval_gate', 'result': 'approved', 'by': approved_by})
        log += [{'step': s, 'result': 'simulated'} for s in
                ('deploy_production', 'smoke_test_production', 'rollback_ready_production')]
    if status == 'refused':
        log.append({'step': 'deploy_production', 'result': 'refused', 'reason': reason})
    plan_json = json.dumps({'app': app, 'version': version, 'steps': plan},
                           ensure_ascii=False, indent=2)
    json.loads(plan_json)
    return _pack('deploy_plan', {
        'plan': plan, 'secret_names': secrets, 'simulation': log,
        'production_status': status, 'reason': reason,
        'rollback_verified_in_staging': rollback_ok,
        'files': {'deploy-plan.json': plan_json + '\n'}, 'executed': False,
        'note': 'plan and simulation only; any real deployment is a separate, approval-gated step',
    }, ['secrets are referenced by name (secret_ref:<stage>/<NAME>) and resolved by the '
        'deployment platform; separate stores per stage',
        'the same build artifact is promoted from staging to production',
        'approval is represented by an approver name; it is not authenticated here'],
       ['two environments only (staging, production); no canary or blue/green traffic split',
        'step results are supplied by the caller; nothing is built, deployed or tested here',
        'secret values are refused (names only) and never appear in the plan'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'scaffold': scaffold, 'rtl_ui': rtl_ui, 'openapi_spec': openapi_spec,
    'sql_schema': sql_schema, 'session_tokens': session_tokens, 'router_spec': router_spec,
    'feature_tests': feature_tests, 'docs_from_code': docs_from_code,
    'package_manifest': package_manifest, 'deploy_plan': deploy_plan,
}


def run(op, params=None):
    """Validate and dispatch: run('scaffold', {}) -> {'op','result','assumptions','limits'}."""
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
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
