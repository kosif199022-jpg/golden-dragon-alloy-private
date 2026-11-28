"""Red Rose V69: the owner's mandatory dua-reel source gate, shown by `brief` itself.

The rule lives in references/DUA_REELS_PLAYBOOK.md ("Mandatory owner rule"). Before V69 it was an
instruction in documents only, and `brief "اعمل ريل دعاء ..."` answered with a generic recut route
that never mentioned it. This extension wraps the `brief` command, without touching the frozen
router in rose_agent.py, so every dua/azkar request (and a follow-up of one) carries the gate.

It is a reminder: it changes no route, grants no approval and verifies no asset.
"""
from __future__ import annotations

import re
import sys

import rose_agent
import rose_io as rio

PLAYBOOK = 'references/DUA_REELS_PLAYBOOK.md'
_ARABIC = ('دعاء', 'دعوات', 'ادعية', 'اذكار')
_LATIN = re.compile(r'(?<![a-z])(?:azkar|adhkar|duaa?)(?![a-z])')
TEXT_AR = ('بوابة الدعاء الإلزامية: اقرأ «Mandatory owner rule» في ' + PLAYBOOK + ' قبل اختيار أي لقطة أو خط '
           'أو رندر. اللقطات من مكتبة صاحب الشغل dua-telegram-complete بس، والخطوط من مكتبته المعتمدة، '
           'ولا بديل من غير موافقته. الناقص يوقف التسليم.')


def dua_gate(text, prev=None):
    """Gate dict when text (or the message it follows) is about dua/azkar, else None. Read-only."""
    hit = None
    for part in (text, prev):
        folded = rose_agent.fold(part or '').lower()
        hit = next((t for t in _ARABIC if rose_agent.fold(t) in folded), None)
        if not hit:
            m = _LATIN.search(folded)
            hit = m.group(0) if m else None
        if hit:
            break
    if not hit:
        return None
    return {
        'id': 'dua-source-gate',
        'matched': hit,
        'read_first': PLAYBOOK,
        'text_ar': TEXT_AR,
        'libraries': ['dua-library-v1', 'dua-owner-library-v1', 'dua-owner-library-v2', 'fonts-library-v1'],
        'blocks_final_without': ['approved footage with sha256 and trim', 'verified font identity',
                                 'owner words and permitted audio', 'measured caption timing'],
        'enforces': 'reminder only: no route change, no approval, no asset check',
    }


def brief(text, prev=None, files=None, depth='auto'):
    """rose_agent.brief plus `mandatory_gate` and a ⛔ line after the approvals line for dua requests."""
    b = rose_agent.brief(text, prev=prev, files=files, depth=depth)
    gate = dua_gate(text, prev)
    if gate:
        b['mandatory_gate'] = gate
        b['text'] = _with_line(b.get('text', ''))
    return b


def _with_line(text):
    lines = text.split('\n') if text else []
    lines.insert(1 if lines else 0, '⛔ ' + TEXT_AR)
    return '\n'.join(lines)


def _h_brief(args):
    if not (args.request or '').strip():
        return rio.fail('empty request', hint='rose.py brief "<the owner words>" [--prev "..."]')
    b = brief(args.request, prev=args.prev, files=args.files, depth=args.depth)
    b.pop('text', None)
    if args.text:
        text = rose_agent.render_brief(b)
        if b.get('mandatory_gate'):
            text = _with_line(text)
        sys.stdout.buffer.write((text + '\n').encode('utf-8'))
        return 0
    rio.emit(b)
    return 0


def _h_gate(args):
    gate = dua_gate(args.text, args.prev)
    rio.emit({'applies': gate is not None, 'gate': gate})
    return 0


def register(subparsers):
    # The fast CLI registers this module alone; the full loader registers rose_agent before it.
    if 'brief' not in subparsers.choices:
        rose_agent.register(subparsers)
    subparsers.choices['brief'].set_defaults(ext_func=_h_brief)
    p = subparsers.add_parser('dua-gate', help='does the mandatory dua source gate apply to these words? (read only)')
    p.add_argument('text', nargs='?', default='')
    p.add_argument('--prev', default=None)
    p.set_defaults(ext_func=_h_gate)
