"""Red Rose V21: bounded, deterministic accounting checks on owner-provided records.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Records arrive as lists of dicts inside the parameters (at most 50,000 rows per
list). All money is decimal.Decimal parsed from strings (or ints); floats are
rejected for money. Money is rounded ROUND_HALF_UP to `currency_places`
(default 2) and returned as strings. Dates are ISO 'YYYY-MM-DD'.

Every op validates strictly (ValueError on unknown parameter names, floats for
money, malformed dates, out-of-range values) and caps its work. Each op returns
{'op', 'result', 'assumptions', 'limits'}. These are checking aids for the
owner's own data: they give no professional (audit, tax, legal) opinion, file
nothing with any authority and pay nothing.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import difflib
import functools
import json
import math
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

MAX_PARAMS = 24
MAX_ROWS = 50_000
MAX_WORK = 20_000_000

TOPICS = {
    '24.01': 'bank_reconcile',
    '24.02': 'duplicate_invoices',
    '24.03': 'trial_balance',
    '24.04': 'payroll_check',
    '24.05': 'inventory_codes',
    '24.06': 'meat_costing',
    '24.07': 'cash_flow',
    '24.08': 'cost_allocation',
    '24.09': 'standards_checklist',
    '24.10': 'journal_approval',
}

TOPIC_NAMES_AR = {
    '24.01': 'مطابقة حساب بنكي',
    '24.02': 'اكتشاف فواتير مكررة',
    '24.03': 'تجهيز ميزان مراجعة',
    '24.04': 'الرقابة على الرواتب',
    '24.05': 'تحليل مخزون وبدائل',
    '24.06': 'حساب تكلفة منتج لحوم',
    '24.07': 'تقدير تدفقات نقدية',
    '24.08': 'تحليل مراكز التكلفة',
    '24.09': 'تطبيق معايير محاسبة',
    '24.10': 'تدقيق صلاحيات القيود',
}

COMMON_LIMITS = [
    'checking aid on owner-provided data only: no professional, audit, tax or legal opinion',
    'files nothing with any authority and makes or schedules no payment',
]

NON_DEFINITIVE_NOTE = ('non-definitive, requires qualified review '
                       '(غير نهائي، يتطلب مراجعة مهنية مؤهلة)')

_CTX = decimal.Context(prec=40, rounding=ROUND_HALF_UP,
                       traps=[decimal.InvalidOperation, decimal.DivisionByZero,
                              decimal.Overflow])

_MONEY_RE = re.compile(r'^[+-]?\d{1,15}(\.\d{1,8})?$')
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_DT_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$')


# --------------------------------------------------------------------------- validation

def _decimal_ctx(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with decimal.localcontext(_CTX):
            try:
                return fn(*args, **kwargs)
            except decimal.DecimalException as exc:
                raise ValueError(f'{fn.__name__}: invalid decimal arithmetic ({type(exc).__name__})') from exc
    return wrapper


def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits) + COMMON_LIMITS}


def _dec(value, name, *, low=None, high=None, low_open=False):
    """Decimal from a string or int; floats and bools are rejected."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f'{name} must be a decimal string (floats are not accepted)')
    if isinstance(value, int):
        if abs(value) >= 10 ** 15:
            raise ValueError(f'{name} is out of range')
        d = Decimal(value)
    elif isinstance(value, str):
        s = value.strip().replace(',', '')
        if not _MONEY_RE.match(s):
            raise ValueError(f'{name} must be a plain decimal string like "1234.50"')
        d = Decimal(s)
    else:
        raise ValueError(f'{name} must be a decimal string')
    if low is not None and (d < low or (low_open and d <= low)):
        raise ValueError(f'{name} must be {">" if low_open else ">="} {low}')
    if high is not None and d > high:
        raise ValueError(f'{name} must be <= {high}')
    return d


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    if not low <= value <= high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return float(value)


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _text(value, name, *, max_len=200, allow_empty=False):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'{name} must be a string')
    s = str(value).strip()
    if not s and not allow_empty:
        raise ValueError(f'{name} must not be empty')
    if len(s) > max_len:
        raise ValueError(f'{name} is longer than {max_len} characters')
    return s


def _date(value, name):
    if not isinstance(value, str) or not _DATE_RE.match(value.strip()):
        raise ValueError(f'{name} must be an ISO date YYYY-MM-DD')
    try:
        return _dt.date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError(f'{name} is not a valid calendar date') from None


def _datetime(value, name):
    if not isinstance(value, str) or not _DT_RE.match(value.strip()):
        raise ValueError(f'{name} must be an ISO timestamp YYYY-MM-DDTHH:MM[:SS] (no offset)')
    try:
        return _dt.datetime.fromisoformat(value.strip().replace(' ', 'T'))
    except ValueError:
        raise ValueError(f'{name} is not a valid timestamp') from None


def _rows(value, name, required, *, max_rows=MAX_ROWS):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= max_rows:
        raise ValueError(f'{name} must be a list of 1..{max_rows} records')
    for i, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValueError(f'{name}[{i}] must be a dict')
        for key in required:
            if key not in row or row[key] is None:
                raise ValueError(f'{name}[{i}] is missing {key!r}')
    return value


def _places(currency_places):
    return _int(currency_places, 0, 4, 'currency_places')


def _q(d, places):
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _s(d, places):
    return str(_q(d, places))


def _fits(d, places, name):
    if _q(d, places) != d:
        raise ValueError(f'{name} has more decimals than currency_places={places}')
    return d


def _unique_ids(ids, name):
    seen = set()
    for i in ids:
        if i in seen:
            raise ValueError(f'{name} ids must be unique (duplicate {i!r})')
        seen.add(i)


def _pair_given(a, b, na, nb):
    if (a is None) != (b is None):
        raise ValueError(f'{na} and {nb} must be given together')
    return a is None


# --------------------------------------------------------------------------- 24.01 bank_reconcile

_EX_LEDGER = [
    {'id': 'L1', 'date': '2026-01-05', 'amount': '1500.00', 'ref': 'INV-1001'},
    {'id': 'L2', 'date': '2026-01-07', 'amount': '-320.50', 'ref': 'CHQ 4411'},
    {'id': 'L3', 'date': '2026-01-10', 'amount': '799.00', 'ref': 'INV-1002'},
]
_EX_BANK = [
    {'id': 'B1', 'date': '2026-01-06', 'amount': '1500.00', 'ref': 'TRF INV1001'},
    {'id': 'B2', 'date': '2026-01-08', 'amount': '-320.50', 'ref': '4411'},
    {'id': 'B3', 'date': '2026-01-10', 'amount': '800.00', 'ref': 'INV1002'},
]


def _ref_norm(s):
    return re.sub(r'[^0-9A-Z]', '', s.upper())


def _similarity(a, b):
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


def _bank_lines(rows, name, places):
    out = []
    for i, r in enumerate(_rows(rows, name, ('id', 'date', 'amount'))):
        amt = _fits(_dec(r['amount'], f'{name}[{i}].amount'), places, f'{name}[{i}].amount')
        out.append({'id': _text(r['id'], f'{name}[{i}].id'),
                    'date': _date(r['date'], f'{name}[{i}].date'),
                    'amount': amt,
                    'ref': _text(r.get('ref', ''), f'{name}[{i}].ref', allow_empty=True)})
    _unique_ids([x['id'] for x in out], name)
    for x in out:
        x['nref'] = _ref_norm(x['ref'])
    return out


@_decimal_ctx
def bank_reconcile(*, ledger=None, bank=None, date_window_days=3, near_miss_amount='1.00',
                   near_miss_extra_days=7, min_ref_similarity=0.0, currency_places=2,
                   max_near_misses=5000, **extra):
    """Match ledger lines to bank lines: equal amount, then date within
    ±date_window_days, then best reference similarity (difflib ratio on refs
    reduced to A-Z0-9). Greedy in ledger (date, id) order; ties go to the
    smaller date gap then the bank id. Unmatched lines are reported per side,
    and near-misses list unmatched pairs that differ by 0 < |amount| <=
    near_miss_amount within the window ('amount'), equal amounts just outside
    the window ('date'), or equal amounts whose reference similarity is below
    min_ref_similarity ('reference'). Near-misses are never counted as matched.
    """
    _no_extra(extra)
    places = _places(currency_places)
    window = _int(date_window_days, 0, 366, 'date_window_days')
    extra_days = _int(near_miss_extra_days, 0, 366, 'near_miss_extra_days')
    tol = _dec(near_miss_amount, 'near_miss_amount', low=Decimal(0))
    min_sim = _num(min_ref_similarity, 0, 1, 'min_ref_similarity')
    cap = _int(max_near_misses, 0, 50_000, 'max_near_misses')
    if _pair_given(ledger, bank, 'ledger', 'bank'):
        ledger, bank = _EX_LEDGER, _EX_BANK
    L = _bank_lines(ledger, 'ledger', places)
    B = _bank_lines(bank, 'bank', places)
    work = 0

    by_amount = defaultdict(list)
    for b in sorted(range(len(B)), key=lambda k: (B[k]['date'], B[k]['id'])):
        by_amount[B[b]['amount']].append(b)
    used_b = [False] * len(B)
    matched = []
    unmatched_l = []
    ref_rejected = []
    for li in sorted(range(len(L)), key=lambda k: (L[k]['date'], L[k]['id'])):
        l = L[li]
        best = None
        bucket = by_amount.get(l['amount'], ())
        work += len(bucket)
        if work > MAX_WORK:
            raise ValueError('bank_reconcile work budget exceeded; split the period')
        for bi in bucket:
            if used_b[bi]:
                continue
            b = B[bi]
            gap = abs((b['date'] - l['date']).days)
            if gap > window:
                continue
            sim = _similarity(l['nref'], b['nref'])
            key = (-sim, gap, b['id'])
            if best is None or key < best[0]:
                best = (key, bi, sim, gap)
        if best is not None and best[2] >= min_sim:
            used_b[best[1]] = True
            b = B[best[1]]
            matched.append({'ledger_id': l['id'], 'bank_id': b['id'], 'amount': _s(l['amount'], places),
                            'ledger_date': l['date'].isoformat(), 'bank_date': b['date'].isoformat(),
                            'days_apart': best[3], 'ref_similarity': best[2]})
        else:
            unmatched_l.append(li)
            if best is not None:
                ref_rejected.append((li, best[1], best[2], best[3]))

    near = []
    truncated = False

    def add(entry):
        nonlocal truncated
        if len(near) >= cap:
            truncated = True
            return
        near.append(entry)

    for li, bi, sim, gap in ref_rejected:
        l, b = L[li], B[bi]
        add({'type': 'reference', 'ledger_id': l['id'], 'bank_id': b['id'],
             'amount_difference': _s(b['amount'] - l['amount'], places), 'days_apart': gap,
             'ref_similarity': sim})
    by_date = defaultdict(list)
    for bi in range(len(B)):
        if not used_b[bi]:
            by_date[B[bi]['date'].toordinal()].append(bi)
    for bi_list in by_date.values():
        bi_list.sort(key=lambda k: B[k]['id'])
    seen_pairs = {(L[li]['id'], B[bi]['id']) for li, bi, _, _ in ref_rejected}
    reach = window + extra_days
    for li in unmatched_l:
        l = L[li]
        o = l['date'].toordinal()
        for d in range(-reach, reach + 1):
            cands = by_date.get(o + d)
            if not cands:
                continue
            work += len(cands)
            if work > MAX_WORK:
                raise ValueError('bank_reconcile work budget exceeded; split the period')
            for bi in cands:
                b = B[bi]
                if (l['id'], b['id']) in seen_pairs:
                    continue
                diff = b['amount'] - l['amount']
                gap = abs(d)
                if gap <= window and diff != 0 and abs(diff) <= tol:
                    kind = 'amount'
                elif gap > window and diff == 0:
                    kind = 'date'
                else:
                    continue
                seen_pairs.add((l['id'], b['id']))
                add({'type': kind, 'ledger_id': l['id'], 'bank_id': b['id'],
                     'amount_difference': _s(diff, places), 'days_apart': gap,
                     'ref_similarity': _similarity(l['nref'], b['nref'])})
    near.sort(key=lambda e: (e['ledger_id'], e['bank_id'], e['type']))

    def side(rows, idxs):
        return [{'id': rows[i]['id'], 'date': rows[i]['date'].isoformat(),
                 'amount': _s(rows[i]['amount'], places), 'ref': rows[i]['ref']} for i in idxs]
    ub = [i for i in sorted(range(len(B)), key=lambda k: (B[k]['date'], B[k]['id'])) if not used_b[i]]
    tot_l = sum((x['amount'] for x in L), Decimal(0))
    tot_b = sum((x['amount'] for x in B), Decimal(0))
    result = {
        'matched': matched, 'unmatched_ledger': side(L, unmatched_l), 'unmatched_bank': side(B, ub),
        'near_misses': near, 'near_misses_truncated': truncated,
        'counts': {'ledger': len(L), 'bank': len(B), 'matched': len(matched),
                   'unmatched_ledger': len(unmatched_l), 'unmatched_bank': len(ub),
                   'near_misses': len(near)},
        'totals': {'ledger': _s(tot_l, places), 'bank': _s(tot_b, places),
                   'difference': _s(tot_b - tot_l, places)},
    }
    return _pack('bank_reconcile', result,
                 ['amounts are signed in the same convention on both sides (receipts positive)',
                  'one-to-one matching only (no split or batched deposits)',
                  'greedy matching in ledger date order; a global optimum is not searched',
                  'reference similarity is a text heuristic, not proof of identity'],
                 [f'<= {MAX_ROWS} rows per side', f'work budget {MAX_WORK} comparisons',
                  f'near-misses reported up to max_near_misses ({cap})'])


# --------------------------------------------------------------------------- 24.02 duplicate_invoices

_EX_INVOICES = [
    {'id': 1, 'supplier': 'Al Noor Trading', 'invoice_no': 'INV-0012', 'amount': '2300.00', 'date': '2026-02-01'},
    {'id': 2, 'supplier': 'al noor trading ', 'invoice_no': 'INV0012', 'amount': '2300.00', 'date': '2026-02-03'},
    {'id': 3, 'supplier': 'Al Noor Trading', 'invoice_no': 'INV-0013', 'amount': '2300.00', 'date': '2026-02-05'},
    {'id': 4, 'supplier': 'Gulf Supplies', 'invoice_no': '0012', 'amount': '410.00', 'date': '2026-02-02'},
]


def _supplier_norm(s):
    return re.sub(r'\s+', ' ', s).strip().casefold()


def _invoice_norm(s):
    return re.sub(r'[\s\-‐-―−]+', '', s).upper()


@_decimal_ctx
def duplicate_invoices(*, invoices=None, window_days=7, currency_places=2, max_suspects=10_000,
                       **extra):
    """Exact duplicates: same normalised supplier (trimmed, case-folded, single
    spaces), same normalised invoice number (spaces and dashes removed,
    upper-cased, leading zeros kept) and same amount. Suspects: same supplier
    and amount, different invoice number, dates within window_days. Rows with
    the same supplier+number but different amounts are listed separately as
    number_reuse (not duplicates)."""
    _no_extra(extra)
    places = _places(currency_places)
    window = _int(window_days, 0, 366, 'window_days')
    cap = _int(max_suspects, 0, 100_000, 'max_suspects')
    if invoices is None:
        invoices = _EX_INVOICES
    rows = []
    for i, r in enumerate(_rows(invoices, 'invoices', ('supplier', 'invoice_no', 'amount'))):
        inv_raw = _text(r['invoice_no'], f'invoices[{i}].invoice_no')
        inv = _invoice_norm(inv_raw)
        if not inv:
            raise ValueError(f'invoices[{i}].invoice_no is empty after normalisation')
        rows.append({'id': _text(r.get('id', i), f'invoices[{i}].id'),
                     'supplier': _supplier_norm(_text(r['supplier'], f'invoices[{i}].supplier')),
                     'invoice_no': inv_raw, 'inv': inv,
                     'amount': _q(_dec(r['amount'], f'invoices[{i}].amount'), places),
                     'date': _date(r['date'], f'invoices[{i}].date') if r.get('date') is not None else None})
    _unique_ids([x['id'] for x in rows], 'invoices')

    exact = defaultdict(list)
    by_number = defaultdict(set)
    for x in rows:
        exact[(x['supplier'], x['inv'], x['amount'])].append(x)
        by_number[(x['supplier'], x['inv'])].add(x['amount'])
    dup_groups = []
    dup_ids = set()
    for (sup, inv, amt), grp in sorted(exact.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        if len(grp) > 1:
            dup_groups.append({'supplier': sup, 'normalised_invoice_no': inv, 'amount': _s(amt, places),
                               'ids': [g['id'] for g in grp],
                               'raw_invoice_nos': [g['invoice_no'] for g in grp]})
            dup_ids.update(g['id'] for g in grp)
    reuse = [{'supplier': s, 'normalised_invoice_no': n, 'amounts': sorted(_s(a, places) for a in amts)}
             for (s, n), amts in sorted(by_number.items()) if len(amts) > 1]

    by_sa = defaultdict(list)
    for x in rows:
        if x['date'] is not None:
            by_sa[(x['supplier'], x['amount'])].append(x)
    suspects = []
    truncated = False
    work = 0
    for key in sorted(by_sa):
        grp = sorted(by_sa[key], key=lambda x: (x['date'], x['id']))
        for a in range(len(grp)):
            for b in range(a + 1, len(grp)):
                work += 1
                if work > MAX_WORK:
                    raise ValueError('duplicate_invoices work budget exceeded')
                gap = (grp[b]['date'] - grp[a]['date']).days
                if gap > window:
                    break
                if grp[a]['inv'] == grp[b]['inv']:
                    continue
                if len(suspects) >= cap:
                    truncated = True
                    break
                suspects.append({'ids': [grp[a]['id'], grp[b]['id']], 'supplier': key[0],
                                 'amount': _s(key[1], places), 'days_apart': gap,
                                 'invoice_nos': [grp[a]['invoice_no'], grp[b]['invoice_no']]})
    result = {'duplicates': dup_groups, 'duplicate_ids': sorted(dup_ids),
              'suspects': suspects, 'suspects_truncated': truncated,
              'number_reuse_different_amounts': reuse,
              'counts': {'invoices': len(rows), 'duplicate_groups': len(dup_groups),
                         'suspects': len(suspects)}}
    return _pack('duplicate_invoices', result,
                 ['supplier names compared after trimming, case-folding and collapsing spaces only (no fuzzy names)',
                  'invoice numbers: spaces and dashes removed, leading zeros kept, other characters kept',
                  'amounts compared after rounding to currency_places; rows without a date are skipped for suspects'],
                 [f'<= {MAX_ROWS} invoices', f'suspects reported up to max_suspects ({cap})',
                  'a flagged pair is a lead for review, not proof of double payment'])


# --------------------------------------------------------------------------- 24.03 trial_balance

_EX_JOURNAL = [
    {'entry_id': 'JE1', 'account': '1010', 'debit': '5000.00'},
    {'entry_id': 'JE1', 'account': '3000', 'credit': '5000.00'},
    {'entry_id': 'JE2', 'account': '5100', 'debit': '1200.00'},
    {'entry_id': 'JE2', 'account': '1010', 'credit': '1200.00'},
]


@_decimal_ctx
def trial_balance(*, lines=None, currency_places=2, **extra):
    """Aggregate journal lines (entry_id, account, debit, credit) by account.
    Checks that total debit == total credit and that every entry balances;
    unbalanced entries are listed by entry_id with their difference."""
    _no_extra(extra)
    places = _places(currency_places)
    if lines is None:
        lines = _EX_JOURNAL
    acc = defaultdict(lambda: [Decimal(0), Decimal(0)])
    ent = defaultdict(lambda: [Decimal(0), Decimal(0)])
    order = []
    for i, r in enumerate(_rows(lines, 'lines', ('entry_id', 'account'))):
        eid = _text(r['entry_id'], f'lines[{i}].entry_id')
        account = _text(r['account'], f'lines[{i}].account')
        dr = _fits(_dec(r.get('debit') or '0', f'lines[{i}].debit', low=Decimal(0)), places, f'lines[{i}].debit')
        cr = _fits(_dec(r.get('credit') or '0', f'lines[{i}].credit', low=Decimal(0)), places, f'lines[{i}].credit')
        if dr and cr:
            raise ValueError(f'lines[{i}] has both debit and credit; split it into two lines')
        if eid not in ent:
            order.append(eid)
        acc[account][0] += dr
        acc[account][1] += cr
        ent[eid][0] += dr
        ent[eid][1] += cr
    accounts = []
    for a in sorted(acc):
        dr, cr = acc[a]
        bal = dr - cr
        accounts.append({'account': a, 'debit': _s(dr, places), 'credit': _s(cr, places),
                         'balance': _s(abs(bal), places),
                         'side': 'debit' if bal > 0 else 'credit' if bal < 0 else 'zero'})
    unbalanced = [{'entry_id': e, 'debit': _s(ent[e][0], places), 'credit': _s(ent[e][1], places),
                   'difference': _s(ent[e][0] - ent[e][1], places)}
                  for e in order if ent[e][0] != ent[e][1]]
    tdr = sum((v[0] for v in acc.values()), Decimal(0))
    tcr = sum((v[1] for v in acc.values()), Decimal(0))
    result = {'accounts': accounts,
              'totals': {'debit': _s(tdr, places), 'credit': _s(tcr, places),
                         'difference': _s(tdr - tcr, places)},
              'totals_equal': tdr == tcr, 'unbalanced_entries': unbalanced,
              'balanced': tdr == tcr and not unbalanced,
              'counts': {'lines': len(lines), 'entries': len(order), 'accounts': len(accounts)}}
    return _pack('trial_balance', result,
                 ['debit and credit are non-negative and only one is non-zero per line',
                  'balance side is debit-minus-credit; account classification (asset, liability...) is not inferred'],
                 [f'<= {MAX_ROWS} lines', 'amounts must fit currency_places exactly'])


# --------------------------------------------------------------------------- 24.04 payroll_check

_EX_PAYROLL = [
    {'employee_id': 'E01', 'net': '8000.00'},
    {'employee_id': 'E02', 'net': '6500.00'},
    {'employee_id': 'E03', 'net': '7200.00'},
]
_EX_PAYMENTS = [
    {'employee_id': 'E01', 'iban': 'SA0380000000608010167519', 'amount': '8000.00'},
    {'employee_id': 'E02', 'iban': 'SA4420000001234567891234', 'amount': '6000.00'},
    {'employee_id': 'E09', 'iban': 'SA1180000000000000001111', 'amount': '3000.00'},
]


def _mask(iban):
    return '*' * max(0, len(iban) - 4) + iban[-4:]


def _iban_checksum_ok(iban):
    if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$', iban):
        return None
    moved = iban[4:] + iban[:4]
    digits = ''.join(str(int(c, 36)) for c in moved)
    return int(digits) % 97 == 1


@_decimal_ctx
def payroll_check(*, payroll=None, payments=None, tolerance='0.00', currency_places=2, **extra):
    """Reconcile a payroll register (employee_id, net) with a WPS-like payment
    file (employee_id, iban, amount). Flags duplicate employee ids on either
    side, net != paid beyond tolerance, paid but not on payroll, on payroll but
    not paid, one account shared by several employees, and failed IBAN mod-97
    checks. IBANs are only ever returned masked (all but the last 4)."""
    _no_extra(extra)
    places = _places(currency_places)
    tol = _dec(tolerance, 'tolerance', low=Decimal(0))
    if _pair_given(payroll, payments, 'payroll', 'payments'):
        payroll, payments = _EX_PAYROLL, _EX_PAYMENTS
    net = defaultdict(Decimal)
    pay_count = defaultdict(int)
    order = []
    for i, r in enumerate(_rows(payroll, 'payroll', ('employee_id', 'net'))):
        e = _text(r['employee_id'], f'payroll[{i}].employee_id')
        if e not in net:
            order.append(e)
        net[e] += _dec(r['net'], f'payroll[{i}].net')
        pay_count[e] += 1
    paid = defaultdict(Decimal)
    paid_count = defaultdict(int)
    iban_emps = defaultdict(set)
    out_payments = []
    flags = []
    for i, r in enumerate(_rows(payments, 'payments', ('employee_id', 'iban', 'amount'))):
        e = _text(r['employee_id'], f'payments[{i}].employee_id')
        raw = r['iban']
        if not isinstance(raw, str):
            raise ValueError(f'payments[{i}].iban must be a string')
        iban = re.sub(r'\s+', '', raw).upper()
        if not re.match(r'^[A-Z0-9]{8,34}$', iban):
            raise ValueError(f'payments[{i}].iban must be 8..34 letters/digits (value not shown)')
        amt = _dec(r['amount'], f'payments[{i}].amount')
        paid[e] += amt
        paid_count[e] += 1
        iban_emps[iban].add(e)
        ok = _iban_checksum_ok(iban)
        out_payments.append({'row': i, 'employee_id': e, 'iban_masked': _mask(iban),
                             'amount': _s(amt, places), 'iban_checksum_ok': ok})
        if ok is False:
            flags.append({'type': 'iban_checksum_failed', 'employee_id': e, 'iban_masked': _mask(iban)})
    for e in order:
        if pay_count[e] > 1:
            flags.append({'type': 'duplicate_in_payroll', 'employee_id': e, 'count': pay_count[e]})
    for e in sorted(paid_count):
        if paid_count[e] > 1:
            flags.append({'type': 'duplicate_in_payments', 'employee_id': e, 'count': paid_count[e]})
    for e in order:
        if e not in paid:
            flags.append({'type': 'on_payroll_not_paid', 'employee_id': e, 'net': _s(net[e], places)})
        elif abs(net[e] - paid[e]) > tol:
            flags.append({'type': 'net_not_equal_paid', 'employee_id': e, 'net': _s(net[e], places),
                          'paid': _s(paid[e], places), 'difference': _s(paid[e] - net[e], places)})
    for e in sorted(paid):
        if e not in net:
            flags.append({'type': 'paid_not_on_payroll', 'employee_id': e, 'paid': _s(paid[e], places)})
    for iban in sorted(iban_emps, key=_mask):
        if len(iban_emps[iban]) > 1:
            flags.append({'type': 'iban_shared_by_employees', 'iban_masked': _mask(iban),
                          'employee_ids': sorted(iban_emps[iban])})
    tn = sum(net.values(), Decimal(0))
    tp = sum(paid.values(), Decimal(0))
    counts = defaultdict(int)
    for f in flags:
        counts[f['type']] += 1
    result = {'flags': flags, 'flag_counts': dict(sorted(counts.items())), 'payments': out_payments,
              'totals': {'payroll_net': _s(tn, places), 'paid': _s(tp, places),
                         'difference': _s(tp - tn, places)},
              'clean': not flags}
    return _pack('payroll_check', result,
                 ['employee ids are compared exactly after trimming',
                  'several payments to one employee are summed before comparing with net',
                  'IBAN check is the ISO 13616 mod-97 test only; it does not prove account ownership'],
                 [f'<= {MAX_ROWS} rows per side', 'IBANs are never returned unmasked (last 4 characters only)',
                  'not a WPS file validator for any specific bank or ministry format'])


# --------------------------------------------------------------------------- 24.05 inventory_codes

_EX_ITEMS = [
    {'code': 'AB-001', 'name': 'Bolt M8', 'attributes': {'size': 'M8', 'type': 'bolt'}},
    {'code': 'ab 001', 'name': 'bolt m8', 'attributes': {'type': 'Bolt', 'size': 'm8'}},
    {'code': '00123', 'name': 'Washer', 'attributes': {'size': 'M8', 'type': 'washer'}},
    {'code': '123', 'name': 'Washer 8', 'attributes': {'size': 'M8', 'type': 'washer'}},
]


def _code_norm(code):
    s = re.sub(r'[\s\-_./\\‐-―]+', '-', code.strip().upper())
    return s.strip('-')


@_decimal_ctx
def inventory_codes(*, items=None, **extra):
    """Normalise item codes (trim, upper-case, unify separators to '-', keep
    leading zeros) and report duplicates (same normalised code) and alternates
    (different codes with an identical non-empty attribute set; keys and values
    trimmed and case-folded)."""
    _no_extra(extra)
    if items is None:
        items = _EX_ITEMS
    parsed = []
    for i, r in enumerate(_rows(items, 'items', ('code',))):
        raw = _text(r['code'], f'items[{i}].code', max_len=100)
        norm = _code_norm(raw)
        if not norm:
            raise ValueError(f'items[{i}].code is empty after normalisation')
        attrs = r.get('attributes') or {}
        if not isinstance(attrs, dict) or len(attrs) > 50:
            raise ValueError(f'items[{i}].attributes must be a dict of at most 50 entries')
        akey = tuple(sorted((_text(k, f'items[{i}].attributes key').casefold(),
                             _text(v, f'items[{i}].attributes value', allow_empty=True).casefold())
                            for k, v in attrs.items()))
        parsed.append({'row': i, 'code': raw, 'normalised': norm, 'attr': akey,
                       'name': _text(r.get('name', ''), f'items[{i}].name', allow_empty=True)})
    by_code = defaultdict(list)
    for p in parsed:
        by_code[p['normalised']].append(p)
    duplicates = [{'normalised_code': c, 'rows': [p['row'] for p in g], 'raw_codes': [p['code'] for p in g]}
                  for c, g in sorted(by_code.items()) if len(g) > 1]
    by_attr = defaultdict(set)
    for p in parsed:
        if p['attr']:
            by_attr[p['attr']].add(p['normalised'])
    alternates = [{'attributes': {k: v for k, v in a}, 'codes': sorted(codes)}
                  for a, codes in sorted(by_attr.items()) if len(codes) > 1]
    result = {'items': [{'row': p['row'], 'code': p['code'], 'normalised_code': p['normalised']} for p in parsed],
              'duplicates': duplicates, 'alternates': alternates,
              'counts': {'items': len(parsed), 'distinct_codes': len(by_code),
                         'duplicate_groups': len(duplicates), 'alternate_groups': len(alternates)}}
    return _pack('inventory_codes', result,
                 ['separators (space, dash, underscore, dot, slash) are equivalent; leading zeros are significant',
                  'alternates need exactly equal attribute sets after case-folding (no unit conversion or fuzzy match)'],
                 [f'<= {MAX_ROWS} items, <= 50 attributes per item',
                  'an alternate is a candidate substitute for review, not an approved interchange'])


# --------------------------------------------------------------------------- 24.06 meat_costing

@_decimal_ctx
def meat_costing(*, purchase_weight_kg='100', price_per_kg='30.00', trim_pct='10', waste_pct='5',
                 processing_cost='200.00', sale_price_per_kg='45.00', trim_value_per_kg='0',
                 target_margin_pct=None, currency_places=2, **extra):
    """Yield/waste costing of a meat product.

    sellable_kg = purchase_kg * (1 - (trim_pct + waste_pct) / 100)
    total_cost  = purchase_kg * price_per_kg + processing_cost - trim_kg * trim_value_per_kg
    cost_per_sellable_kg = total_cost / sellable_kg  (= break-even sale price per kg)
    gross_profit = sellable_kg * sale_price_per_kg - total_cost
    gross_margin_pct = gross_profit / revenue * 100
    price_for_target_margin = cost_per_kg / (1 - target_margin_pct / 100)
    Intermediate values are exact Decimals; only reported values are rounded.
    """
    _no_extra(extra)
    places = _places(currency_places)
    w = _dec(purchase_weight_kg, 'purchase_weight_kg', low=Decimal(0), low_open=True, high=Decimal(10 ** 9))
    price = _dec(price_per_kg, 'price_per_kg', low=Decimal(0))
    trim = _dec(trim_pct, 'trim_pct', low=Decimal(0), high=Decimal(100))
    waste = _dec(waste_pct, 'waste_pct', low=Decimal(0), high=Decimal(100))
    if trim + waste >= 100:
        raise ValueError('trim_pct + waste_pct must be < 100')
    proc = _dec(processing_cost, 'processing_cost', low=Decimal(0))
    sale = _dec(sale_price_per_kg, 'sale_price_per_kg', low=Decimal(0))
    trim_val = _dec(trim_value_per_kg, 'trim_value_per_kg', low=Decimal(0))
    tm = None
    if target_margin_pct is not None:
        tm = _dec(target_margin_pct, 'target_margin_pct', low=Decimal(0))
        if tm >= 100:
            raise ValueError('target_margin_pct must be < 100')
    trim_kg = w * trim / 100
    waste_kg = w * waste / 100
    sellable = w - trim_kg - waste_kg
    purchase_cost = w * price
    total = purchase_cost + proc - trim_kg * trim_val
    if total < 0:
        raise ValueError('trim credit exceeds purchase plus processing cost')
    cpk = total / sellable
    revenue = sellable * sale
    profit = revenue - total
    margin = (profit / revenue * 100) if revenue else None
    result = {
        'purchase_cost': _s(purchase_cost, places), 'processing_cost': _s(proc, places),
        'trim_credit': _s(trim_kg * trim_val, places), 'total_cost': _s(total, places),
        'trim_kg': str(_q(trim_kg, 3)), 'waste_kg': str(_q(waste_kg, 3)),
        'sellable_kg': str(_q(sellable, 3)), 'yield_pct': str(_q(sellable / w * 100, 2)),
        'cost_per_sellable_kg': _s(cpk, places), 'break_even_price_per_kg': _s(cpk, places),
        'revenue': _s(revenue, places), 'gross_profit': _s(profit, places),
        'gross_margin_pct': None if margin is None else str(_q(margin, 2)),
        'markup_on_cost_pct': str(_q(profit / total * 100, 2)) if total else None,
        'price_for_target_margin': None if tm is None else _s(cpk / (1 - tm / 100), places),
    }
    return _pack('meat_costing', result,
                 ['trim and waste are percentages of purchase weight; waste has no resale value',
                  'trim is credited at trim_value_per_kg (0 = discarded)',
                  'processing_cost is the total for this batch; no overhead allocation, tax or shrink in storage'],
                 ['percentages in [0, 100), trim + waste < 100', 'weights reported to 3 decimals, percentages to 2'])


# --------------------------------------------------------------------------- 24.07 cash_flow

_EX_SALES = ['20000', '22000', '18000', '25000', '24000', '26000']
_EX_PAYMENTS_CF = ['19000', '19000', '21000', '20000', '20500', '21000']
_DEFAULT_SCEN = {'low': {'sales_factor_pct': '85'}, 'base': {'sales_factor_pct': '100'},
                 'high': {'sales_factor_pct': '115'}}


def _month_label(start, k):
    m = start.month - 1 + k
    return f'{start.year + m // 12:04d}-{m % 12 + 1:02d}'


@_decimal_ctx
def cash_flow(*, opening_cash='10000.00', start_date='2026-01-01', months=None, sales=None,
              payments=None, collection_rate_pct='90', collection_delay_months=1, scenarios=None,
              currency_places=2, **extra):
    """Monthly cash projection per scenario. Sales billed in month m are
    collected in month m + delay at collection_rate_pct (the rest is treated as
    never collected). closing = opening + collections - payments. Each scenario
    may scale sales (sales_factor_pct) and payments (payments_factor_pct) and
    override collection_rate_pct. Scenarios low, base and high are required;
    the minimum closing balance month is reported per scenario."""
    _no_extra(extra)
    places = _places(currency_places)
    opening = _dec(opening_cash, 'opening_cash')
    start = _date(start_date, 'start_date')
    rate = _dec(collection_rate_pct, 'collection_rate_pct', low=Decimal(0), high=Decimal(100))
    delay = _int(collection_delay_months, 0, 12, 'collection_delay_months')
    if _pair_given(sales, payments, 'sales', 'payments'):
        sales, payments = _EX_SALES, _EX_PAYMENTS_CF
    for nm, seq in (('sales', sales), ('payments', payments)):
        if not isinstance(seq, (list, tuple)) or not 1 <= len(seq) <= 120:
            raise ValueError(f'{nm} must be a list of 1..120 monthly amounts')
    if months is None:
        months = len(sales)
    months = _int(months, 1, 120, 'months')
    if len(sales) != months or len(payments) != months:
        raise ValueError('sales and payments must each have exactly `months` entries')
    S = [_dec(v, f'sales[{i}]', low=Decimal(0)) for i, v in enumerate(sales)]
    P = [_dec(v, f'payments[{i}]', low=Decimal(0)) for i, v in enumerate(payments)]
    if scenarios is None:
        scenarios = _DEFAULT_SCEN
    if not isinstance(scenarios, dict) or not 3 <= len(scenarios) <= 6:
        raise ValueError('scenarios must be a dict of 3..6 named scenarios')
    for need in ('low', 'base', 'high'):
        if need not in scenarios:
            raise ValueError('scenarios must include low, base and high')
    out = {}
    for name in sorted(scenarios):
        cfg = scenarios[name]
        _text(name, 'scenario name', max_len=40)
        if not isinstance(cfg, dict):
            raise ValueError(f'scenarios[{name!r}] must be a dict')
        bad = set(cfg) - {'sales_factor_pct', 'payments_factor_pct', 'collection_rate_pct'}
        if bad:
            raise ValueError(f'scenarios[{name!r}] has unknown key(s): {", ".join(sorted(map(str, bad)))}')
        sf = _dec(cfg.get('sales_factor_pct', '100'), f'{name}.sales_factor_pct', low=Decimal(0), high=Decimal(1000))
        pf = _dec(cfg.get('payments_factor_pct', '100'), f'{name}.payments_factor_pct', low=Decimal(0), high=Decimal(1000))
        r = _dec(cfg.get('collection_rate_pct', collection_rate_pct),f'{name}.collection_rate_pct', low=Decimal(0), high=Decimal(100))
        billed = [_q(s * sf / 100, places) for s in S]
        cash = _q(opening, places)
        rows = []
        min_row = None
        for m in range(months):
            coll = _q(billed[m - delay] * r / 100, places) if m - delay >= 0 else Decimal(0)
            pay = _q(P[m] * pf / 100, places)
            open_m = cash
            cash = open_m + coll - pay
            row = {'month': _month_label(start, m), 'opening': _s(open_m, places), 'billed': _s(billed[m], places),
                   'collections': _s(coll, places), 'payments': _s(pay, places), 'closing': _s(cash, places)}
            rows.append(row)
            if min_row is None or cash < min_row[0]:
                min_row = (cash, row['month'])
        tb = sum(billed, Decimal(0))
        collected_base = sum(billed[:max(0, months - delay)], Decimal(0))
        out[name] = {'months': rows, 'closing_cash': _s(cash, places),
                     'minimum_balance': _s(min_row[0], places), 'minimum_balance_month': min_row[1],
                     'goes_negative': min_row[0] < 0,
                     'billed_total': _s(tb, places),
                     'uncollected_written_off': _s(collected_base - collected_base * r / 100, places),
                     'receivable_after_horizon': _s(sum(billed[max(0, months - delay):], Decimal(0)), places)}
    order_ok = all(Decimal(out['low']['months'][m]['closing']) <= Decimal(out['base']['months'][m]['closing'])
                   <= Decimal(out['high']['months'][m]['closing']) for m in range(months))
    result = {'scenarios': out, 'scenario_order_ok': order_ok, 'collection_delay_months': delay}
    return _pack('cash_flow', result,
                 ['sales billed in a month are collected in one lump after the delay; the uncollected share is lost',
                  'no opening receivables or payables, no financing, tax or interest',
                  'scenario factors are uniform percentages over every month'],
                 ['<= 120 months, 3..6 scenarios', 'collections rounded per month to currency_places',
                  'a projection from owner assumptions, not a forecast or financing advice'])


# --------------------------------------------------------------------------- 24.08 cost_allocation

_EX_EXPENSES = [{'id': 'EXP-1', 'amount': '10000.00', 'description': 'Rent'},
                {'id': 'EXP-2', 'amount': '100.00', 'description': 'Cleaning'}]
_EX_CENTRES = [{'centre': 'Production', 'share': '3'}, {'centre': 'Sales', 'share': '3'},
               {'centre': 'Admin', 'share': '3'}]


@_decimal_ctx
def cost_allocation(*, expenses=None, centres=None, method='driver', currency_places=2, **extra):
    """Allocate each shared expense to cost centres by percent (shares must
    sum to exactly 100) or by driver quantity (positive shares). Each line is
    rounded ROUND_HALF_UP; the rounding remainder goes to the largest share
    (first in input order on ties), so every expense is allocated exactly.
    Each allocation line carries its source expense id."""
    _no_extra(extra)
    places = _places(currency_places)
    method = _choice(method, {'percent', 'driver'}, 'method')
    if _pair_given(expenses, centres, 'expenses', 'centres'):
        expenses, centres = _EX_EXPENSES, _EX_CENTRES
    C = []
    for i, r in enumerate(_rows(centres, 'centres', ('centre', 'share'), max_rows=500)):
        C.append((_text(r['centre'], f'centres[{i}].centre'),
                  _dec(r['share'], f'centres[{i}].share', low=Decimal(0))))
    _unique_ids([c for c, _ in C], 'centres')
    total_share = sum((s for _, s in C), Decimal(0))
    if method == 'percent' and total_share != 100:
        raise ValueError('percent shares must sum to exactly 100')
    if total_share <= 0:
        raise ValueError('driver shares must sum to more than zero')
    largest = max(range(len(C)), key=lambda k: (C[k][1], -k))
    E = []
    for i, r in enumerate(_rows(expenses, 'expenses', ('id', 'amount'))):
        E.append((_text(r['id'], f'expenses[{i}].id'),
                  _fits(_dec(r['amount'], f'expenses[{i}].amount'), places, f'expenses[{i}].amount')))
    _unique_ids([e for e, _ in E], 'expenses')
    if len(E) * len(C) > 2_000_000:
        raise ValueError('expenses * centres must be <= 2000000')
    lines = []
    by_centre = defaultdict(Decimal)
    checks = []
    for eid, amt in E:
        allocs = [_q(amt * s / total_share, places) for _, s in C]
        rem = amt - sum(allocs, Decimal(0))
        allocs[largest] += rem
        for k, (cname, share) in enumerate(C):
            lines.append({'allocation_id': f'{eid}/{cname}', 'source_expense_id': eid, 'centre': cname,
                          'share': str(share), 'amount': _s(allocs[k], places),
                          'received_remainder': k == largest and rem != 0})
            by_centre[cname] += allocs[k]
        checks.append({'expense_id': eid, 'amount': _s(amt, places),
                       'allocated': _s(sum(allocs, Decimal(0)), places),
                       'remainder': _s(rem, places), 'exact': sum(allocs, Decimal(0)) == amt})
    total = sum((a for _, a in E), Decimal(0))
    result = {'method': method, 'lines': lines, 'expense_checks': checks,
              'by_centre': [{'centre': c, 'amount': _s(by_centre[c], places)} for c, _ in C],
              'total_expenses': _s(total, places),
              'total_allocated': _s(sum(by_centre.values(), Decimal(0)), places),
              'all_exact': all(c['exact'] for c in checks),
              'remainder_centre': C[largest][0]}
    return _pack('cost_allocation', result,
                 ['one driver set applies to every expense in this call (run once per driver pool)',
                  'single-step direct allocation; no reciprocal or step-down between service centres'],
                 ['<= 500 centres, expenses * centres <= 2000000',
                  'expense amounts must fit currency_places exactly'])


# --------------------------------------------------------------------------- 24.09 standards_checklist

_EX_CHECKLIST = [
    {'id': 'C1', 'standard': 'IFRS 15', 'reference': 'IFRS 15.9',
     'effective_date': '2018-01-01', 'question': 'Contract with customer identified?', 'answer': 'yes'},
    {'id': 'C2', 'standard': 'IFRS 16', 'reference': '', 'effective_date': '2019-01-01',
     'question': 'Leases recognised on balance sheet?', 'answer': 'no'},
    {'id': 'C3', 'standard': 'SOCPA', 'reference': 'SOCPA-ZAKAT-1', 'question': 'Zakat provision recorded?'},
]
_ANSWERS = {'yes', 'no', 'partial', 'n/a'}


@_decimal_ctx
def standards_checklist(*, items=None, as_of=None, **extra):
    """Evaluate an owner-supplied checklist. Each item names a standard
    (e.g. IFRS 15, SOCPA), a reference id and an effective date; answers are
    yes / no / partial / n/a (or empty = unanswered) against an expected answer
    (default yes). Items missing a reference or effective date, or not yet
    effective at as_of, are flagged. Every result carries the non-definitive
    note: the tool does not know or interpret any standard's content."""
    _no_extra(extra)
    if items is None:
        items = _EX_CHECKLIST
    asof = _date(as_of, 'as_of') if as_of is not None else None
    out = []
    ids = []
    for i, r in enumerate(_rows(items, 'items', ('standard',), max_rows=5000)):
        iid = _text(r.get('id', i), f'items[{i}].id')
        ids.append(iid)
        std = _text(r['standard'], f'items[{i}].standard')
        ref = _text(r.get('reference') or '', f'items[{i}].reference', allow_empty=True)
        eff_raw = r.get('effective_date')
        flags = []
        eff = None
        if eff_raw in (None, ''):
            flags.append('missing_effective_date')
        else:
            eff = _date(eff_raw, f'items[{i}].effective_date')
            if asof is not None and eff > asof:
                flags.append('not_yet_effective')
        if not ref:
            flags.append('missing_reference')
        ans = r.get('answer')
        ans = None if ans in (None, '') else _choice(str(ans).strip().lower(), _ANSWERS, f'items[{i}].answer')
        exp = _choice(str(r.get('expected', 'yes')).strip().lower(), _ANSWERS - {'n/a'}, f'items[{i}].expected')
        if ans is None:
            status = 'unanswered'
        elif ans == 'n/a':
            status = 'not_applicable'
        elif ans == exp:
            status = 'consistent'
        else:
            status = 'gap'
        out.append({'id': iid, 'standard': std, 'reference': ref or None,
                    'effective_date': eff.isoformat() if eff else None,
                    'question': _text(r.get('question', ''), f'items[{i}].question', max_len=1000, allow_empty=True),
                    'answer': ans, 'expected': exp, 'status': status, 'flags': flags,
                    'definitive': False, 'note': NON_DEFINITIVE_NOTE})
    _unique_ids(ids, 'items')
    counts = defaultdict(int)
    for o in out:
        counts[o['status']] += 1
    result = {'items': out, 'status_counts': dict(sorted(counts.items())),
              'flagged_ids': [o['id'] for o in out if o['flags']],
              'as_of': asof.isoformat() if asof else None,
              'definitive': False, 'note': NON_DEFINITIVE_NOTE}
    return _pack('standards_checklist', result,
                 ['checklist items, references and expected answers come from the owner; none are built in',
                  'the tool does not read, interpret or verify the text of IFRS, SOCPA or any standard'],
                 ['<= 5000 items', 'every result is non-definitive and requires qualified review'])


# --------------------------------------------------------------------------- 24.10 journal_approval

_EX_ENTRIES = [
    {'id': 'JE-100', 'creator': 'amal', 'created_at': '2026-03-01T09:00', 'approver': 'omar',
     'approved_at': '2026-03-01T11:00'},
    {'id': 'JE-101', 'creator': 'omar', 'created_at': '2026-03-02T09:00', 'approver': 'omar',
     'approved_at': '2026-03-02T09:30'},
    {'id': 'JE-102', 'creator': 'amal', 'created_at': '2026-03-03T09:00', 'approver': 'omar',
     'approved_at': '2026-03-03T10:00',
     'history': [{'user': 'amal', 'at': '2026-03-03T12:00', 'action': 'edit'}]},
]
_REJECT = {'self_approval', 'approval_before_creation'}


@_decimal_ctx
def journal_approval(*, entries=None, **extra):
    """Segregation-of-duties check on journal entries (id, creator, created_at,
    approver, approved_at, history=[{user, at, action: edit|approve}]).
    Rejected: an approval by the creator (self_approval) or an approval
    timestamped before creation. Flagged: last edit later than the last
    approval (edited_after_approval), no approval at all, an approver who also
    edited the entry, events dated before creation. Names compare
    case-insensitively after trimming."""
    _no_extra(extra)
    if entries is None:
        entries = _EX_ENTRIES
    total_events = 0
    out = []
    ids = []
    for i, r in enumerate(_rows(entries, 'entries', ('id', 'creator', 'created_at'))):
        eid = _text(r['id'], f'entries[{i}].id')
        ids.append(eid)
        creator = _text(r['creator'], f'entries[{i}].creator').casefold()
        created = _datetime(r['created_at'], f'entries[{i}].created_at')
        approvals = []
        edits = []
        if (r.get('approver') is None) != (r.get('approved_at') is None):
            raise ValueError(f'entries[{i}] needs both approver and approved_at, or neither')
        if r.get('approver') is not None:
            approvals.append((_datetime(r['approved_at'], f'entries[{i}].approved_at'),
                              _text(r['approver'], f'entries[{i}].approver').casefold()))
        hist = r.get('history') or []
        if not isinstance(hist, (list, tuple)) or len(hist) > 1000:
            raise ValueError(f'entries[{i}].history must be a list of at most 1000 events')
        total_events += len(hist)
        if total_events > 200_000:
            raise ValueError('total history events must be <= 200000')
        for k, h in enumerate(hist):
            if not isinstance(h, dict):
                raise ValueError(f'entries[{i}].history[{k}] must be a dict')
            act = _choice(h.get('action'), {'edit', 'approve'}, f'entries[{i}].history[{k}].action')
            ev = (_datetime(h.get('at'), f'entries[{i}].history[{k}].at'),
                  _text(h.get('user'), f'entries[{i}].history[{k}].user').casefold())
            (approvals if act == 'approve' else edits).append(ev)
        issues = []
        if any(u == creator for _, u in approvals):
            issues.append('self_approval')
        if any(t < created for t, _ in approvals):
            issues.append('approval_before_creation')
        if any(t < created for t, _ in edits):
            issues.append('edit_before_creation')
        if not approvals:
            issues.append('not_approved')
        else:
            last_appr = max(t for t, _ in approvals)
            if edits and max(t for t, _ in edits) > last_appr:
                issues.append('edited_after_approval')
            editors = {u for _, u in edits}
            if any(u in editors for _, u in approvals):
                issues.append('approver_edited_entry')
        status = 'rejected' if _REJECT & set(issues) else 'flagged' if issues else 'ok'
        out.append({'id': eid, 'status': status, 'issues': issues,
                    'approvals': len(approvals), 'edits': len(edits)})
    _unique_ids(ids, 'entries')
    result = {'entries': out,
              'rejected_ids': [o['id'] for o in out if o['status'] == 'rejected'],
              'flagged_ids': [o['id'] for o in out if o['status'] == 'flagged'],
              'ok_ids': [o['id'] for o in out if o['status'] == 'ok']}
    return _pack('journal_approval', result,
                 ['timestamps are naive local times in one time zone',
                  'user names are compared after trimming and case-folding; no role or delegation table is used',
                  'an approval that is itself rejected (e.g. self-approval) still counts as the latest approval time'],
                 [f'<= {MAX_ROWS} entries, <= 1000 history events per entry, <= 200000 events in total',
                  'checks the supplied log only; it cannot detect edits missing from the history'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'bank_reconcile': bank_reconcile, 'duplicate_invoices': duplicate_invoices,
    'trial_balance': trial_balance, 'payroll_check': payroll_check,
    'inventory_codes': inventory_codes, 'meat_costing': meat_costing,
    'cash_flow': cash_flow, 'cost_allocation': cost_allocation,
    'standards_checklist': standards_checklist, 'journal_approval': journal_approval,
}


def run(op, params=None):
    """Validate and dispatch: run('trial_balance', {'lines': [...]}) -> {'op','result','assumptions','limits'}."""
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
