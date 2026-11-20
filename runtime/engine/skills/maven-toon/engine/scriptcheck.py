"""Script check: python toon.py script PROJECT [--seconds 30] [--pace 2.1]

Reads PROJECT/script.txt (one sentence per line) and checks it against the Maven Toon script rules
(references/script-ar.md for Arabic, references/STYLE.md for English): length at the voice pace, a hook that fits
the first 3.5 s, short sentences, a turn ("تدري ليش؟" / "You see,"), a short payoff, no voice tags.
It never rewrites the script; it prints what to fix. Exit code 0 = OK, 1 = something to fix.
"""
import os
import re

from .words import script_words, is_arabic, SENT_END

TAG = re.compile(r'\[[^\]]+\]|\([^)]*(whisper|softly|laugh|sigh|يهمس|بهمس)[^)]*\)', re.I)
TURN_AR = ('تدري ليش', 'تدرون ليش', 'تعرف ليش', 'السبب', 'لأن', 'لان', 'السر', 'الحقيقة', 'بالحقيقة', 'والسبب', 'تدري شنو',
           'هل تعلم', 'والسر')
TURN_EN = ('you see', 'because', "here's why", 'the reason', 'turns out', 'the trick', 'the secret')


def sentences(text):
    out, cur = [], []
    for w in script_words(text):
        cur.append(w['w'])
        if SENT_END.search(w['w']):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def check(text, seconds=None, pace=None):
    ar = is_arabic(text)
    pace = pace or (2.1 if ar else 2.5)
    sents = sentences(text)
    words = [w for s in sents for w in s]
    n = len(words)
    est = n / pace + 0.35 * max(0, len(sents) - 1)
    notes, bad = [], 0
    print('language: %s | %d words, %d sentences | about %.1f s at %.1f words/s (+ pauses)'
          % ('Arabic' if ar else 'English', n, len(sents), est, pace))
    if seconds:
        lo, hi = seconds * 0.85, seconds * 1.08
        if est > hi:
            cut = int((est - seconds) * pace + 0.5)
            notes.append('too long for %d s: cut about %d words' % (seconds, cut)); bad += 1
        elif est < lo:
            notes.append('short for %d s: room for about %d more words' % (seconds, int((seconds - est) * pace))); bad += 0
    if sents:
        h = sents[0]
        if len(h) / pace > 3.5:
            notes.append('hook is %d words (%.1f s): the first sentence should land in 3.5 s (%d words or fewer)'
                         % (len(h), len(h) / pace, int(3.5 * pace))); bad += 1
        if h[-1].endswith(('?', '؟')):
            notes.append('hook is a question: state the strange fact instead (a question only after it)'); bad += 1
        last = sents[-1]
        if len(last) > 9:
            notes.append('payoff is %d words: keep the last sentence short (9 words or fewer)' % len(last)); bad += 1
    for i, s in enumerate(sents):
        if len(s) > (14 if ar else 18):
            notes.append('sentence %d has %d words: split it (one picture per sentence)' % (i + 1, len(s))); bad += 1
    if TAG.search(text):
        notes.append('remove voice tags like [whispers] or (softly): write the feeling into the words'); bad += 1
    low = text.lower()
    if not any(t in (text if ar else low) for t in (TURN_AR if ar else TURN_EN)):
        notes.append('no turn found: add the explanation beat ("%s")' % ('تدري ليش؟ ...' if ar else 'You see, ...'))
    if ar and re.search(r'\d', text):
        notes.append('digits in an Arabic voice script: write numbers as words so the voice reads them right')
    for k, s in enumerate(sents):
        print('  %2d. %s' % (k + 1, ' '.join(s)))
    if notes:
        print('\nto fix:')
        for x in notes:
            print('  - ' + x)
    else:
        print('\nSCRIPT OK')
    return 1 if bad else 0


def main(argv):
    proj = argv[0]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    p = proj if proj.endswith('.txt') else os.path.join(proj, 'script.txt')
    if not os.path.exists(p):
        print('ERROR: no script.txt in %s' % proj)
        return 2
    text = open(p, encoding='utf-8-sig').read()
    sec = opt('--seconds')
    pace = opt('--pace')
    return check(text, float(sec) if sec else None, float(pace) if pace else None)
