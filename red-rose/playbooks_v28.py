"""Red Rose V28: catalog skill descriptions -> structured, searchable PLAYBOOKS.

Standard library only (sqlite3, re, json, hashlib, contextlib, pathlib,
collections, math) plus the native Red Rose modules fusion_map_v27 (domain
classification), knowledge_v25 (Arabic/English normalisation) and agents_v22
(task_contract). No network, no child processes, no dynamic code evaluation,
no printing.

Interface (same pattern as physics_v20 / knowledge_v25): OPS, EFFECTS and
run(op, params) -> {'op', 'result', 'assumptions', 'limits'}. Every parameter
is validated strictly (ValueError) and unknown parameter names are rejected.

Safety rules:
- Descriptions are DATA. Nothing described in a title or summary is executed,
  imported, opened or followed; instruction-like or command-like text is only
  flagged ('injection_like', 'mentions_commands').
- Source databases are opened in SQLite read-only URI mode. The owner's
  private memory (anything under ~/.red-rose) is refused unless
  allow_private_db=True is passed explicitly.
- build_index never copies the source table: it writes only derived playbook
  fields (no raw summary, no source_path, no sha of the source row) into a NEW
  file inside a caller-supplied existing work_dir, and needs approve_write=True.
  Rows of kind lesson/rule and rows with origin 'owner' are skipped, so private
  lessons stay private.
- Parsing is a pure keyword/regex heuristic; 'confidence' only measures how
  many playbook fields the heuristic found, not whether the playbook is right.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

import agents_v22
import fusion_map_v27
from knowledge_v25 import normalise

MAX_PARAMS = 24
MAX_TITLE = 500
MAX_SUMMARY = 20_000
MAX_QUERY = 500
MAX_ROWS = 1_000_000
MAX_LIST = 12
SCHEMA_VERSION = 'playbooks_v28/1'

PRIVATE_DIR = Path.home() / '.red-rose'

SOURCE_TABLE = 'fused_knowledge'
SOURCE_KINDS = ('catalog-skill', 'skill', 'tool', 'lib', 're', 'program', 'mcp')
PRIVATE_KINDS = frozenset({'lesson', 'rule'})
FIELDS = ('goal', 'triggers', 'inputs', 'steps', 'checks', 'outputs')
BANDS = ('low', 'medium', 'high')

EFFECTS = {
    'parse_description': 'read',
    'build_index': 'write',
    'search': 'read',
    'plan_from_playbook': 'read',
    'stats': 'read',
}


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _str(value, name, *, max_len=200, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} is required')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _num(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _strlist(value, name, *, max_items=50, max_len=500):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or len(value) > max_items:
        raise ValueError(f'{name} must be a list of at most {max_items} strings')
    return [_str(v, f'{name}[{i}]', max_len=max_len) for i, v in enumerate(value)]


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions), 'limits': list(limits)}


def _approval(op, action):
    return {'op': op, 'status': 'approval_required',
            'result': {'status': 'approval_required', 'action': action, 'needs': ['approve_write'],
                       'written': False},
            'assumptions': ['nothing was opened or written'],
            'limits': ['write actions need approve_write=True']}


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# --------------------------------------------------------------------------- paths

def _is_private(path):
    private = str(PRIVATE_DIR.resolve()).casefold().rstrip('\\/')
    p = str(path).casefold()
    return p == private or p.startswith(private + '\\') or p.startswith(private + '/')


def _db_path(db, allow_private_db, name='db'):
    """Resolve an existing SQLite file path; refuse ~/.red-rose unless explicitly allowed."""
    allow_private_db = _bool(allow_private_db, 'allow_private_db')
    if isinstance(db, Path):
        db = str(db)
    db = _str(db, name, max_len=1000)
    if db == ':memory:' or db.lower().startswith('file:'):
        raise ValueError(f'{name} must be a plain path to an existing SQLite file')
    path = Path(db).expanduser().resolve()
    # The derived playbook index (built by build_index) may live in ~/.red-rose; it holds
    # no private lessons, so it opens without the flag. The owner's memory still needs it.
    derived = path.name.startswith('playbooks_v28') and path.suffix in ('.sqlite3', '.sqlite', '.db')
    if _is_private(path) and not allow_private_db and not derived:
        raise ValueError("refusing the owner's private memory under ~/.red-rose; "
                         'pass allow_private_db=True explicitly to use it')
    if path.is_dir():
        raise ValueError(f'{name} must be a file path, not a directory')
    if not path.is_file():
        raise ValueError(f'{name} file does not exist')
    return path


def _connect_ro(path):
    """Read-only connection; the caller wraps it in contextlib.closing."""
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)


def _has_table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
                        (name,)).fetchone() is not None


# --------------------------------------------------------------------------- text heuristics

_WS = re.compile(r'\s+')
_SENT_SPLIT = re.compile(r'(?<=[.!?؟])\s+|\n+')
_CLAUSE_SPLIT = re.compile(r'\s*(?:;|؛|→|->|=>|•|\.(?=\s|$)|[!?؟](?=\s|$)|\n|\s\d{1,2}[.)]\s|\bthen\b)\s*',
                           re.IGNORECASE)
_COMMA_SPLIT = re.compile(r'(\s*,\s*(?:and\s+)?|\s+and\s+|\s*،\s*)', re.IGNORECASE)

_TRIGGER_EN = re.compile(
    r'\b(?:use\s+(?:this\s+(?:skill|tool|playbook)\s+|it\s+)?(?:when(?:ever)?|for|if)'
    r'|triggers?(?:\s+(?:on|when|for|with))?'
    r'|activate\s+when'
    r'|when\s+(?:the\s+)?user\s+(?:asks|says|wants|mentions|needs))\b\s*:?\s*(.+?)(?=\.\s|\.$|;|\n|$)',
    re.IGNORECASE | re.DOTALL)
_TRIGGER_AR = re.compile(
    r'(?:استخدم\w*|استعمل\w*)\s+(?:(?:دي|ده|هذه|هذا|المهارة|المهاره|الأداة|الاداة)\s+)?'
    r'(?:(?:لما|عند|عندما|لو|في|مع|ل)\s+)?(.+?)(?=[.؛;\n]|$)')
_QUOTED = re.compile(r'«([^»]{1,120})»|“([^”]{1,120})”|"([^"]{1,120})"|‘([^’]{1,120})’')
_TRIG_SPLIT = re.compile(r'\s*(?:,|،|\bor\b|\s+أو\s+|/)\s*', re.IGNORECASE)

_INPUT_CUE = re.compile(r'\b(?:from|given|with)\s+', re.IGNORECASE)
_OUTPUT_CUE = re.compile(r'\b(?:produces?|produced|generates?|generated|writes?|returns?|reports?'
                         r'|outputs?)\s+', re.IGNORECASE)

_CHECK_EN = re.compile(r'\b(?:verif(?:y|ies|ied)|checks?|checked|tests?|tested|ensures?|never|must'
                       r'|validat(?:e|es|ed))\b', re.IGNORECASE)
_CHECK_AR = re.compile(r'(?:تحقق|تأكد|افحص|فحص|(?:^|\s)لا(?:\s|$)|ممنوع|لازم)')

_INJECTION = re.compile(
    r'(ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts|rules)'
    r'|disregard\s+.{0,30}instructions|system\s+prompt|you\s+are\s+now\b|developer\s+mode'
    r'|act\s+as\s+(?:an?\s+)?(?:admin|root|system)|exfiltrat\w*|send\s+.{0,40}(?:password|token|cookie)s?'
    r'|تجاهل\s+.{0,20}التعليمات)', re.IGNORECASE)
_COMMANDS = re.compile(
    r'(`[^`\n]{2,}`|\$\(|\bsudo\b|\brm\s+-rf\b|\bcurl\b|\bwget\b|\bpip\s+install\b|\bnpm\s+(?:i|install)\b'
    r'|\bpowershell\b|\binvoke-expression\b|\biex\b|\bchmod\b|\|\s*(?:ba)?sh\b|\beval\s*\(|\bexec\s*\()',
    re.IGNORECASE)

_ARTICLES = frozenset({'a', 'an', 'the', 'your', 'any', 'their', 'its', 'this', 'these', 'those', 'some',
                       'my', 'our', 'each', 'every', 'all'})
_PHRASE_STOP = frozenset({'to', 'and', 'or', 'for', 'into', 'in', 'on', 'by', 'using', 'via', 'that', 'which',
                          'when', 'while', 'so', 'as', 'then', 'with', 'from', 'at', 'before', 'after', 'if',
                          'use', 'is', 'are', 'be', 'it', 'without', 'across', 'per', 'including', 'like'})
_PRONOUNS = frozenset({'it', 'them', 'this', 'that', 'these', 'those', 'you', 'me', 'us', 'one', 'ease',
                       'care', 'confidence', 'no', 'not'})
_LEAD_FILLERS = re.compile(r'^(?:(?:first|second|third|finally|also|next|and|then|now|lastly|step\s*\d+)'
                           r'\s*[,:)\-]?\s+|(?:it|this\s+(?:skill|tool|playbook))\s+|\d{1,2}[.)]\s*)+',
                           re.IGNORECASE)

_VERBS = frozenset('''
add adjust align analyse analyze animate annotate apply archive assemble assess audit automate
balance benchmark break build bundle calculate capture caption categorize check choose classify clean
cluster collect color colour combine compare compile compose compress compute configure confirm connect
convert copy correct count create crop cross-check cut debug decide decompose define denoise deploy
describe design detect diagnose diff document download draft draw edit enrich encode estimate evaluate
examine explain explore export extract filter find fix flag follow forecast format frame gather generate
grade group guide handle highlight identify implement import improve infer inspect install integrate
interview investigate isolate keep label launch layout lint list load localize localise locate log
look make map mark master match measure merge migrate mix model monitor name normalize normalise
note optimize optimise order organize organise outline package parse pick plan plot polish predict
prepare present preview prioritize prioritise process produce profile prototype provide publish query
rank read rebuild recommend reconcile record recover reduce refactor refine reframe remove render
reorder repair replace report reproduce research resize resolve restore restructure retime review
revise rewrite rig rotate route run sample save scale scan schedule score scope search segment select
separate sequence set shape shoot simulate size sketch slice sort source specify split stabilize
stabilise standardize start store storyboard stream structure style subtitle summarize summarise
suggest sync synthesize synthesise tag test time trace track train transcribe transform translate
trim tune turn update upload upscale use validate verify visualize visualise walk weigh write
'''.split())

_AR_VERBS = frozenset(normalise(v) for v in '''
اعمل استخدم حلل حلّل افحص اكتب شغل شغّل اقرا اقرأ ارسم حول حوّل صدر صدّر قيس قس تحقق تأكد ابدأ اختار اختر
جهز جهّز رتب رتّب ركب ركّب قص قصّ لون لوّن نزل نزّل ابني ابن راجع صمم صمّم احسب قارن استخرج حدد حدّد
اجمع نظف نظّف رندر ارفع احفظ ضيف أضف اضف لخص لخّص ترجم فرغ فرّغ
'''.split())


def _clean(text):
    return _WS.sub(' ', text or '').strip()


def _dedupe(items, limit=MAX_LIST):
    seen, out = set(), []
    for it in items:
        key = it.casefold()
        if it and key not in seen:
            seen.add(key)
            out.append(it)
        if len(out) >= limit:
            break
    return out


def _base_verb(word):
    """Return the base form if word is a known verb (base or 3rd person), else None."""
    w = word.casefold().strip('*_"\'«»“”()[]')
    if w in _VERBS:
        return w
    if w.endswith('ies') and w[:-3] + 'y' in _VERBS:
        return w[:-3] + 'y'
    if w.endswith('es') and w[:-2] in _VERBS:
        return w[:-2]
    if w.endswith('s') and w[:-1] in _VERBS:
        return w[:-1]
    return None


def _imperative(clause):
    """If clause starts with a verb, return it in imperative form, else None."""
    c = _LEAD_FILLERS.sub('', clause.strip(' -–—:,')).strip()
    if not c:
        return None
    first, _, rest = c.partition(' ')
    base = _base_verb(first)
    if base is not None:
        return (base[:1].upper() + base[1:] + (' ' + rest if rest else '')).strip()
    if normalise(first) in _AR_VERBS:
        return c
    return None


def _is_trigger_clause(clause):
    return bool(_TRIGGER_EN.search(clause) or _TRIGGER_AR.search(clause))


def _split_clauses(text):
    """Split on ; . then → etc., then split comma/and lists only where a new verb starts."""
    out = []
    for clause in _CLAUSE_SPLIT.split(text):
        clause = clause.strip(' ,-–—:')
        if not clause:
            continue
        parts = _COMMA_SPLIT.split(clause)
        current = parts[0]
        i = 1
        while i < len(parts):
            sep, part = parts[i], parts[i + 1] if i + 1 < len(parts) else ''
            words = part.split()
            if len(words) >= 2 and _imperative(part) is not None:
                out.append(current.strip())
                current = part
            else:
                current = current + sep + part
            i += 2
        out.append(current.strip())
    return [c for c in out if c]


def _phrase_after(text, cue, max_words=5):
    """Noun phrases (<= max_words) right after each cue word; stops at punctuation/stopwords."""
    found = []
    for m in cue.finditer(text):
        tail = text[m.end():m.end() + 200]
        words = []
        for tok in re.finditer(r'[^\s,.;:()\[\]{}!?؟،؛]+|[,.;:()\[\]{}!?؟،؛]', tail):
            w = tok.group(0)
            lw = w.casefold()
            if re.fullmatch(r'[,.;:()\[\]{}!?؟،؛]', w):
                break
            if not words and lw in _ARTICLES:
                continue
            if lw in _PHRASE_STOP and words:
                break
            if lw in _PHRASE_STOP:
                break
            words.append(w.strip('"\'«»“”'))
            if len(words) >= max_words:
                break
        if words and words[0].casefold() not in _PRONOUNS:
            phrase = ' '.join(w for w in words if w)
            if 1 < len(phrase) <= 80:
                found.append(phrase)
    return _dedupe(found, 10)


def _triggers(text):
    raw = []
    for rx in (_TRIGGER_EN, _TRIGGER_AR):
        for m in rx.finditer(text):
            body = _clean(m.group(1))
            if not body:
                continue
            quoted = [next(g for g in q.groups() if g) for q in _QUOTED.finditer(body)]
            if quoted:
                raw.extend(_clean(q) for q in quoted)
                continue
            for piece in _TRIG_SPLIT.split(body):
                piece = re.sub(r'^(?:the\s+user\s+|users?\s+|when\s+|you\s+|asked\s+to\s+|and\s+)+', '',
                               piece.strip(' .:-'), flags=re.IGNORECASE).strip()
                if 2 <= len(piece) <= 120:
                    raw.append(piece)
    return _dedupe(raw)


def _confidence(found):
    return round(found / len(FIELDS), 3)


def _band(conf):
    return 'low' if conf < 0.34 else ('medium' if conf < 0.67 else 'high')


def _domain(kind, title, summary):
    family, category, adapters = fusion_map_v27.classify(kind, title, summary)
    domain = family.split(':', 1)[1] if ':' in family else family.lower()
    return domain, category, family, list(adapters)


def _parse(title, summary, kind):
    """Core pure heuristic (inputs already validated/coerced to str)."""
    title = _clean(title)
    summary = _clean(summary)
    source_sha = _sha(f'{title}\n{summary}')
    body = summary
    if title and body.casefold().startswith(title.casefold()):
        rest = body[len(title):]
        if rest[:1] in (':', '-', '–', '—'):
            body = rest[1:].strip()
    text = body or title
    sentences = [s.strip() for s in _SENT_SPLIT.split(body) if s.strip()]

    goal = None
    for s in sentences:
        if not _is_trigger_clause(s):
            goal = s[:300]
            break

    triggers = _triggers(text)

    work = ' '.join(s for s in sentences if not _is_trigger_clause(s))
    steps, checks = [], []
    for clause in _split_clauses(work):
        imp = _imperative(clause)
        if imp is not None:
            steps.append(imp[:240])
    for clause in _split_clauses(body):
        if _CHECK_EN.search(clause) or _CHECK_AR.search(clause):
            checks.append(clause[:240])
    steps = _dedupe(steps)
    checks = _dedupe(checks, 10)
    inputs = _phrase_after(work, _INPUT_CUE)
    outputs = _phrase_after(work, _OUTPUT_CUE)

    flags = []
    full = f'{title} {summary}'
    if _INJECTION.search(full):
        flags.append('injection_like')
    if _COMMANDS.search(full):
        flags.append('mentions_commands')

    domain, category, family, adapters = _domain(kind, title, summary)
    found = sum(1 for v in (goal, triggers, inputs, steps, checks, outputs) if v)
    conf = _confidence(found)
    return {
        'id': 'pb_' + source_sha[:20],
        'title': title[:MAX_TITLE],
        'goal': goal,
        'triggers': triggers,
        'inputs': inputs,
        'steps': steps,
        'checks': checks,
        'outputs': outputs,
        'domain': domain,
        'category': category,
        'family': family,
        'related_adapters': adapters,
        'confidence': conf,
        'band': _band(conf),
        'fields_found': [f for f, v in zip(FIELDS, (goal, triggers, inputs, steps, checks, outputs)) if v],
        'flags': flags,
        'kind': kind,
        'source_sha256': source_sha,
        'executable': False,
    }


_PARSE_ASSUMPTIONS = [
    'descriptions are data: nothing in them is executed, opened or followed',
    'goal = first non-trigger sentence; triggers = text after Use when/Use for/Trigger/استخدم '
    '(quoted phrases preferred); inputs = short noun phrases after from/given/with; outputs = after '
    'produce/generate/write/return/report/output; steps = clauses (split on ; . then → and verb-led '
    'comma lists) that start with a known verb, 3rd-person verbs rewritten to imperative; checks = '
    'clauses with verify/check/test/ensure/never/must/validate or تحقق/تأكد/افحص/لا/ممنوع/لازم',
    'domain/category/related_adapters come from fusion_map_v27.classify (keyword heuristic)',
    'confidence = fields found / 6 (goal, triggers, inputs, steps, checks, outputs); band low <0.34, '
    'medium <0.67, high otherwise; it measures extraction coverage, not correctness',
    'source_sha256 = sha256 of whitespace-normalised "title\\nsummary"; id = pb_ + first 20 hex chars',
]
_PARSE_LIMITS = [
    'English verb list is fixed (~300 verbs); nouns that are also verbs can start false steps',
    'Arabic: triggers, checks and a short imperative verb list only; no Arabic input/output extraction',
    'flags (injection_like, mentions_commands) are regex hints, not a security verdict',
    f'title <= {MAX_TITLE} chars, summary <= {MAX_SUMMARY} chars, <= {MAX_LIST} items per list',
]


# --------------------------------------------------------------------------- op: parse_description

def parse_description(*, title=None, summary='', kind='catalog-skill', **extra):
    """Pure: turn one (title, summary) description into a playbook dict."""
    _no_extra(extra)
    title = _str(title, 'title', max_len=MAX_TITLE)
    summary = _str(summary, 'summary', max_len=MAX_SUMMARY, allow_empty=True)
    kind = _str(kind, 'kind', max_len=40)
    if kind in PRIVATE_KINDS:
        raise ValueError('kind lesson/rule is private owner memory and is not turned into a playbook')
    return _pack('parse_description', _parse(title, summary, kind), _PARSE_ASSUMPTIONS, _PARSE_LIMITS)


# --------------------------------------------------------------------------- op: build_index

_OUT_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')

_PB_SCHEMA = [
    'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    'CREATE TABLE playbooks(n INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, title TEXT NOT NULL, '
    'goal TEXT, triggers TEXT NOT NULL, inputs TEXT NOT NULL, steps TEXT NOT NULL, checks TEXT NOT NULL, '
    'outputs TEXT NOT NULL, domain TEXT NOT NULL, category TEXT NOT NULL, family TEXT NOT NULL, '
    'related_adapters TEXT NOT NULL, confidence REAL NOT NULL, band TEXT NOT NULL, flags TEXT NOT NULL, '
    'kind TEXT NOT NULL, license TEXT, source_sha256 TEXT NOT NULL)',
    'CREATE INDEX playbooks_domain ON playbooks(domain)',
    'CREATE INDEX playbooks_band ON playbooks(band)',
    "CREATE VIRTUAL TABLE playbooks_fts USING fts5(title, goal, triggers, steps, tokenize='unicode61')",
]
_PB_COLS = ('id', 'title', 'goal', 'triggers', 'inputs', 'steps', 'checks', 'outputs', 'domain',
            'category', 'family', 'related_adapters', 'confidence', 'band', 'flags', 'kind', 'license',
            'source_sha256')
_JSON_COLS = frozenset({'triggers', 'inputs', 'steps', 'checks', 'outputs', 'related_adapters', 'flags'})


def _as_text(value, limit):
    if value is None:
        return ''
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return str(value).replace('\x00', ' ')[:limit]


def _fts_row(pb):
    return (normalise(pb['title']), normalise(pb['goal'] or ''),
            normalise(' | '.join(pb['triggers'])), normalise(' | '.join(pb['steps'])))


def build_index(*, db=None, work_dir=None, out_name='playbooks_v28.sqlite3', kinds=None,
                max_rows=200_000, overwrite=False, approve_write=False, allow_private_db=False, **extra):
    """Read fused_knowledge (read-only) and write derived playbooks + FTS5 into a NEW file in work_dir."""
    _no_extra(extra)
    approve_write = _bool(approve_write, 'approve_write')
    overwrite = _bool(overwrite, 'overwrite')
    allow_private_db = _bool(allow_private_db, 'allow_private_db')
    if db is None:
        raise ValueError('db is required (path to the SQLite file holding fused_knowledge)')
    src = _db_path(db, allow_private_db)
    if work_dir is None:
        raise ValueError('work_dir is required (an existing folder for the new playbook database)')
    if isinstance(work_dir, Path):
        work_dir = str(work_dir)
    wd = Path(_str(work_dir, 'work_dir', max_len=1000)).expanduser().resolve()
    if not wd.is_dir():
        raise ValueError('work_dir must be an existing folder (it is never created here)')
    if _is_private(wd) and not allow_private_db:
        raise ValueError('refusing to write under ~/.red-rose; pass allow_private_db=True explicitly')
    out_name = _str(out_name, 'out_name', max_len=100)
    if not _OUT_NAME.match(out_name) or out_name.endswith('.partial'):
        raise ValueError('out_name must be a plain file name matching [A-Za-z0-9][A-Za-z0-9_.-]{0,99}')
    out = wd / out_name
    partial = wd / (out_name + '.partial')
    if out.resolve() == src:
        raise ValueError('out_name would overwrite the source database')
    if out.exists() and not overwrite:
        raise ValueError(f'{out_name} already exists in work_dir; pass overwrite=True to replace it')
    if out.is_dir():
        raise ValueError('out_name points to a folder')
    if partial.exists():
        raise ValueError(f'{partial.name} exists (left from an earlier run); remove it first')
    if kinds is None:
        kinds = list(SOURCE_KINDS)
    else:
        kinds = _strlist(kinds, 'kinds', max_items=len(SOURCE_KINDS), max_len=40)
        bad = [k for k in kinds if k not in SOURCE_KINDS]
        if bad or not kinds:
            raise ValueError(f'kinds must be a non-empty subset of {list(SOURCE_KINDS)}')
    kinds = sorted(set(kinds))
    max_rows = _int(max_rows, 1, MAX_ROWS, 'max_rows')
    if not approve_write:
        return _approval('build_index', 'build_index')

    seen_by_kind, by_domain, by_band, by_category = Counter(), Counter(), Counter(), Counter()
    skipped = Counter()
    written = 0
    ids = set()
    try:
        with closing(_connect_ro(src)) as sconn:
            if not _has_table(sconn, SOURCE_TABLE):
                raise ValueError(f'table {SOURCE_TABLE!r} not found in db')
            cols = {r[1] for r in sconn.execute(f'PRAGMA table_info("{SOURCE_TABLE}")')}
            need = {'id', 'kind', 'title', 'summary', 'origin'}
            if need - cols:
                raise ValueError('fused_knowledge is missing column(s): ' + ', '.join(sorted(need - cols)))
            lic_col = 'license' if 'license' in cols else ('licence' if 'licence' in cols else None)
            sel = ('SELECT kind, title, summary, origin, ' + (f'"{lic_col}"' if lic_col else 'NULL') +
                   f' FROM "{SOURCE_TABLE}" WHERE kind IN ({",".join("?" * len(kinds))}) '
                   "AND kind NOT IN ('lesson','rule') AND lower(coalesce(origin,'')) <> 'owner' "
                   'ORDER BY id LIMIT ?')
            with closing(sqlite3.connect(str(partial), timeout=5)) as oconn:
                try:
                    with oconn:
                        for sql in _PB_SCHEMA:
                            oconn.execute(sql)
                except sqlite3.OperationalError as exc:
                    raise ValueError(f'this SQLite build cannot create the FTS5 index: {exc}') from None
                cur = sconn.execute(sel, (*kinds, max_rows))
                while True:
                    batch = cur.fetchmany(1000)
                    if not batch:
                        break
                    pb_rows, fts_rows = [], []
                    for kind, title, summary, origin, lic in batch:
                        kind = _as_text(kind, 40)
                        seen_by_kind[kind] += 1
                        if kind in PRIVATE_KINDS:
                            skipped['private_kind'] += 1
                            continue
                        if _as_text(origin, 200).strip().casefold() == 'owner':
                            skipped['owner_origin'] += 1
                            continue
                        title_t = _clean(_as_text(title, MAX_TITLE))
                        summary_t = _as_text(summary, MAX_SUMMARY)
                        if not title_t:
                            skipped['empty_title'] += 1
                            continue
                        pb = _parse(title_t, summary_t, kind)
                        if pb['id'] in ids:
                            skipped['duplicate'] += 1
                            continue
                        ids.add(pb['id'])
                        pb['license'] = _as_text(lic, 200) or None
                        pb_rows.append(tuple(json.dumps(pb[c], ensure_ascii=False) if c in _JSON_COLS
                                             else pb[c] for c in _PB_COLS))
                        fts_rows.append(_fts_row(pb))
                        by_domain[pb['domain']] += 1
                        by_band[pb['band']] += 1
                        by_category[pb['category']] += 1
                    if not pb_rows:
                        continue
                    with oconn:
                        start = oconn.execute('SELECT coalesce(max(n), 0) FROM playbooks').fetchone()[0]
                        oconn.executemany(
                            f'INSERT INTO playbooks({",".join(_PB_COLS)}) '
                            f'VALUES({",".join("?" * len(_PB_COLS))})', pb_rows)
                        oconn.executemany(
                            'INSERT INTO playbooks_fts(rowid, title, goal, triggers, steps) VALUES(?,?,?,?,?)',
                            [(start + i + 1, *f) for i, f in enumerate(fts_rows)])
                    written += len(pb_rows)
                with oconn:
                    oconn.executemany('INSERT INTO meta(key, value) VALUES(?, ?)', [
                        ('schema', SCHEMA_VERSION),
                        ('kinds', json.dumps(kinds)),
                        ('playbooks', str(written)),
                        ('method', 'heuristic parse of catalog descriptions; derived fields only'),
                    ])
        partial.replace(out)
    except BaseException:
        try:
            partial.unlink()
        except OSError:
            pass
        raise
    return _pack('build_index', {
        'written': True, 'out_file': out.name, 'work_dir': str(wd), 'playbooks': written,
        'source_rows_read': sum(seen_by_kind.values()), 'source_rows_by_kind': dict(seen_by_kind),
        'skipped': dict(skipped),
        'by_domain': dict(by_domain.most_common()),
        'by_confidence_band': {b: by_band.get(b, 0) for b in BANDS},
        'by_category': dict(by_category.most_common()),
    }, ['the source database is opened read-only (SQLite URI mode=ro)',
        'only derived playbook fields are written; the raw summary, source_path, status and the '
        'source row id are never copied',
        "rows of kind lesson/rule and rows with origin 'owner' are skipped (filtered in SQL and again in Python)",
        'identical title+summary pairs collapse to one playbook (same source_sha256)',
        'the file is built as <out_name>.partial and renamed only after it is complete'] + _PARSE_ASSUMPTIONS[1:],
        [f'max_rows <= {MAX_ROWS}', 'the original table is not modified',
         'requires an SQLite build with FTS5'] + _PARSE_LIMITS)


# --------------------------------------------------------------------------- reading the playbook DB

def _open_playbooks(db, allow_private_db):
    path = _db_path(db, allow_private_db)
    conn = _connect_ro(path)
    try:
        if not (_has_table(conn, 'playbooks') and _has_table(conn, 'meta')):
            raise ValueError('db is not a playbook database built by build_index')
        row = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        if row is None or row[0] != SCHEMA_VERSION:
            raise ValueError(f'db schema is not {SCHEMA_VERSION}')
    except BaseException:
        conn.close()
        raise
    return conn


def _row_to_pb(row):
    pb = {}
    for col, val in zip(_PB_COLS, row):
        pb[col] = json.loads(val) if col in _JSON_COLS else val
    pb['executable'] = False
    return pb


# --------------------------------------------------------------------------- op: search

def search(*, db=None, query=None, mode='all', limit=10, domain=None, min_confidence=0.0,
           allow_private_db=False, **extra):
    """BM25-ranked FTS5 search over title/goal/triggers/steps of a playbook database."""
    _no_extra(extra)
    if db is None:
        raise ValueError('db is required (playbook database built by build_index)')
    query = _str(query, 'query', max_len=MAX_QUERY)
    mode = _choice(mode, {'all', 'any'}, 'mode')
    limit = _int(limit, 1, 100, 'limit')
    if domain is not None:
        domain = _str(domain, 'domain', max_len=100)
    min_confidence = _num(min_confidence, 0.0, 1.0, 'min_confidence')
    norm = normalise(query)
    tokens = norm.split()
    if not tokens:
        raise ValueError('query has no searchable words')
    expr = (' OR ' if mode == 'any' else ' ').join('"' + t.replace('"', '""') + '"' for t in tokens[:32])
    sql = ('SELECT ' + ', '.join('p.' + c for c in _PB_COLS) + ', bm25(playbooks_fts, 3.0, 2.0, 2.0, 1.0) '
           'FROM playbooks_fts JOIN playbooks p ON p.n = playbooks_fts.rowid '
           'WHERE playbooks_fts MATCH ? AND p.confidence >= ?')
    args = [expr, min_confidence]
    if domain is not None:
        sql += ' AND p.domain = ?'
        args.append(domain)
    sql += ' ORDER BY bm25(playbooks_fts, 3.0, 2.0, 2.0, 1.0), p.confidence DESC, p.id LIMIT ?'
    args.append(limit)
    with closing(_open_playbooks(db, allow_private_db)) as conn:
        rows = conn.execute(sql, args).fetchall()
    hits = []
    for r in rows:
        pb = _row_to_pb(r[:-1])
        pb['score'] = round(-r[-1], 6)
        hits.append(pb)
    return _pack('search', {'query': query, 'normalised_query': norm, 'fts_expression': expr, 'mode': mode,
                            'domain': domain, 'min_confidence': min_confidence, 'hits': hits,
                            'count': len(hits)},
                 ['same Arabic/English normalisation as knowledge_v25 for index and query',
                  'score = -bm25 with column weights title 3, goal 2, triggers 2, steps 1 (higher is better)',
                  'results are descriptions to follow by hand or through adapters; nothing is executed'],
                 ['query <= 500 characters, first 32 words used, limit <= 100',
                  'mode all = every word must appear; any = at least one word',
                  'no stemming, synonyms or dialect dictionary'])


# --------------------------------------------------------------------------- op: plan_from_playbook

_MANUAL = 'manual/agent step'


def plan_from_playbook(*, db=None, playbook_id=None, task=None, deliverable=None, constraints=None,
                       done_when=None, available_adapters=None, allow_private_db=False, **extra):
    """Turn one playbook + a task text into an agents_v22 task contract and an adapter-mapped step list."""
    _no_extra(extra)
    if db is None:
        raise ValueError('db is required (playbook database built by build_index)')
    playbook_id = _str(playbook_id, 'playbook_id', max_len=40)
    if not re.fullmatch(r'pb_[0-9a-f]{20}', playbook_id):
        raise ValueError('playbook_id must look like pb_ followed by 20 hex characters')
    task = _str(task, 'task', max_len=2000)
    if deliverable is not None:
        deliverable = _str(deliverable, 'deliverable', max_len=2000)
    constraints = [] if constraints is None else _strlist(constraints, 'constraints', max_items=40)
    done_when = [] if done_when is None else _strlist(done_when, 'done_when', max_items=40)
    available = None
    if available_adapters is not None:
        available = set(_strlist(available_adapters, 'available_adapters', max_items=500, max_len=100))
    with closing(_open_playbooks(db, allow_private_db)) as conn:
        row = conn.execute('SELECT ' + ', '.join(_PB_COLS) + ' FROM playbooks WHERE id=?',
                           (playbook_id,)).fetchone()
    if row is None:
        raise ValueError(f'playbook {playbook_id} not found')
    pb = _row_to_pb(row)
    related = list(pb['related_adapters'])

    deliverable_source = 'caller'
    if deliverable is None and pb['outputs']:
        deliverable = '; '.join(pb['outputs'])[:2000]
        deliverable_source = 'playbook_outputs'
    elif deliverable is None:
        deliverable_source = 'missing'
    pb_constraints = [c for c in pb['checks'] if re.search(r'\b(?:never|must)\b|(?:^|\s)لا(?:\s|$)|ممنوع|لازم',
                                                           c, re.IGNORECASE)]
    pb_done = [c for c in pb['checks'] if c not in pb_constraints]
    contract_out = agents_v22.task_contract(
        task=task, deliverable=deliverable,
        constraints=_dedupe(constraints + pb_constraints, 50),
        done_when=_dedupe(done_when + pb_done, 50) or None)
    contract = contract_out['result']

    raw_steps = list(pb['steps']) or ([pb['goal']] if pb['goal'] else [])
    commands_flag = 'mentions_commands' in pb['flags'] or 'injection_like' in pb['flags']
    steps = []
    for i, text in enumerate(raw_steps, 1):
        entry = {'n': i, 'step': text, 'adapter': None, 'adapters': [], 'match': None,
                 'kind': _MANUAL, 'note': None, 'executed': False}
        _fam, cat, own = fusion_map_v27.classify(pb['kind'], text, '')
        if commands_flag and _COMMANDS.search(text):
            entry['note'] = 'mentions a command: review by hand; never run from the description'
        elif not related:
            entry['note'] = 'playbook has no related Red Rose adapter'
        elif cat in ('network', 'paid', 'external_app'):
            entry['note'] = f'step looks {cat}; needs owner approval or an outside program'
        else:
            own_native = own if cat == 'native' else []
            preferred = [a for a in own_native if a in related] or own_native
            if preferred:
                entry['adapters'], entry['match'] = preferred, 'step_keywords'
            else:
                entry['adapters'], entry['match'] = related, 'playbook_domain'
            if available is not None:
                usable = [a for a in entry['adapters'] if a in available]
                if not usable:
                    entry['note'] = 'mapped adapter(s) not in available_adapters'
                    entry['match'] = None
                entry['adapters'] = usable
            if entry['adapters']:
                entry['adapter'] = entry['adapters'][0]
                entry['kind'] = 'adapter'
        steps.append(entry)
    verification = [{'n': i, 'check': c, 'kind': 'verify', 'executed': False}
                    for i, c in enumerate(pb['checks'], 1)]
    mapped = sum(1 for s in steps if s['kind'] == 'adapter')
    return _pack('plan_from_playbook', {
        'status': contract['status'],
        'playbook': {k: pb[k] for k in ('id', 'title', 'goal', 'domain', 'category', 'related_adapters',
                                        'confidence', 'band', 'flags', 'license')},
        'task_contract': contract,
        'deliverable_source': deliverable_source,
        'steps': steps,
        'verification': verification,
        'mapped_steps': mapped,
        'manual_steps': len(steps) - mapped,
        'executed': False,
    }, ['this is a PLAN, not execution: no adapter is called and no step is run',
        'task_contract comes from agents_v22.task_contract; when no deliverable is given, the playbook '
        'outputs are used as the deliverable (deliverable_source says which)',
        'checks with never/must/لا/ممنوع/لازم become constraints, the other checks become done_when',
        'step -> adapter: keywords of the step itself (fusion_map_v27.classify) first, else the playbook '
        "related_adapters ('playbook_domain', weaker); steps without an adapter are 'manual/agent step'",
        'adapter names are not checked against the live REGISTRY unless available_adapters is passed'] +
        contract_out['assumptions'],
        ['steps come from a heuristic parse of a one-paragraph description and may be incomplete',
         'steps mentioning commands are never mapped to an adapter and must be reviewed by hand'] +
        contract_out['limits'])


# --------------------------------------------------------------------------- op: stats

def stats(*, db=None, allow_private_db=False, **extra):
    """Domain / category / confidence breakdown of a playbook database."""
    _no_extra(extra)
    if db is None:
        raise ValueError('db is required (playbook database built by build_index)')
    with closing(_open_playbooks(db, allow_private_db)) as conn:
        total = conn.execute('SELECT count(*) FROM playbooks').fetchone()[0]
        by_domain = dict(conn.execute('SELECT domain, count(*) FROM playbooks GROUP BY domain '
                                      'ORDER BY count(*) DESC, domain').fetchall())
        by_category = dict(conn.execute('SELECT category, count(*) FROM playbooks GROUP BY category '
                                        'ORDER BY count(*) DESC, category').fetchall())
        by_kind = dict(conn.execute('SELECT kind, count(*) FROM playbooks GROUP BY kind '
                                    'ORDER BY count(*) DESC, kind').fetchall())
        bands = dict(conn.execute('SELECT band, count(*) FROM playbooks GROUP BY band').fetchall())
        avg = conn.execute('SELECT avg(confidence) FROM playbooks').fetchone()[0]
        domain_conf = {d: round(c, 4) for d, c in conn.execute(
            'SELECT domain, avg(confidence) FROM playbooks GROUP BY domain ORDER BY domain')}
        field_counts = {}
        for col in ('triggers', 'inputs', 'steps', 'checks', 'outputs'):
            field_counts[col] = conn.execute(f"SELECT count(*) FROM playbooks WHERE {col} <> '[]'").fetchone()[0]
        field_counts['goal'] = conn.execute('SELECT count(*) FROM playbooks WHERE goal IS NOT NULL').fetchone()[0]
        flagged = conn.execute("SELECT count(*) FROM playbooks WHERE flags <> '[]'").fetchone()[0]
        with_adapters = conn.execute("SELECT count(*) FROM playbooks WHERE related_adapters <> '[]'").fetchone()[0]
        meta = dict(conn.execute('SELECT key, value FROM meta').fetchall())
    return _pack('stats', {
        'total': total, 'by_domain': by_domain, 'by_category': by_category, 'by_kind': by_kind,
        'by_confidence_band': {b: bands.get(b, 0) for b in BANDS},
        'avg_confidence': round(avg, 4) if avg is not None else None,
        'avg_confidence_by_domain': domain_conf, 'fields_found': field_counts,
        'with_related_adapters': with_adapters, 'flagged': flagged, 'meta': meta,
    }, ['counts are read from the playbook database only (opened read-only)',
        'confidence measures how many fields the parser found, not playbook quality'],
        ['no per-playbook validation is re-run here'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'parse_description': parse_description,
    'build_index': build_index,
    'search': search,
    'plan_from_playbook': plan_from_playbook,
    'stats': stats,
}


def run(op, params=None):
    """Validate and dispatch: run('search', {'db': path, 'query': 'market size'})."""
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
