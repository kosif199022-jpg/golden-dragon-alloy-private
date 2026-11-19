"""Ultra Mind integration for Black Dragon 10.3 (stdlib, offline, read-only).

The source-provided skill is a procedural checklist. This module deliberately does
not claim to upgrade the LLM's weights, reason autonomously, call independent AI
agents, fact-check URLs, or execute a verifier. Only hashes and arithmetic here
are independently computed, and a matching hash proves integrity, not correctness.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA = 'black-dragon.ultra-mind.packet.v1'
DOMAINS = ('general', 'math', 'code', 'analysis', 'decision', 'forecast', 'creative', 'writing')
LEVELS = ('L0', 'L1', 'L2', 'L3')
CORE = {
    1: ('Understand / Polya', 'حدد المجهول والمعطيات والشروط ونطاق الطلب حرفيًا.'),
    2: ('Step back / Outside view', 'حدد فئة المشكلة والمعدل الأساسي قبل الانطباع الأول.'),
    3: ('Diverge / ACH', 'ولّد بدائل متمايزة ودليلًا يفرق بينها.'),
    4: ('Execute precisely', 'حوّل الحسابات والاستنتاجات إلى قياس أو اختبار يمكن إعادته.'),
    5: ('Falsify / Pre-mortem', 'ابحث عن مثال مضاد وافترض الفشل وحدد سببه.'),
    6: ('Independent verification', 'اختبر بمصدر أو أداة مستقلة؛ لا تكرّر نفس الإجابة.'),
    7: ('Calibrate and deliver', 'افصل المحقق عن المستنتج عن المفترض وحدد درجة الثقة عند الحاجة.'),
}
STAGES = {'L0': (1,), 'L1': (1, 3, 6), 'L2': (1, 2, 3, 4, 5, 6, 7), 'L3': (1, 2, 3, 4, 5, 6, 7)}
TYPE_FOCUS = {
    'general': ('فسّر الألفاظ النافية والقيود', 'ابحث عن تفسير منافس', 'تحقق بشكل مستقل'),
    'math': ('الوحدات والحالات الحدية', 'احسب برمجيًا بدل التخمين', 'أعد التعويض في نص المسألة'),
    'code': ('أعد إنتاج العطل قبل إصلاحه', 'اختبر فرضيات سبب جذري متنافسة', 'شغّل اختبارات الانحدار'),
    'analysis': ('ACH: الأدلة المميّزة لا المؤكّدة فقط', 'المصادر الأولية وتاريخها', 'لا تخلط الارتباط بالسببية'),
    'decision': ('خيارات متنوعة بينها عدم التغيير', 'تكلفة قابلية الرجوع ومرحلة pre-mortem', 'قيّم المعايير بأوزان موثقة'),
    'forecast': ('المعدل الأساسي والنظرة الخارجية أولًا', 'نطاق الاحتمالات ومصادره', 'الإشارات التي قد تغيّر التوقع'),
    'creative': ('ولّد بدائل متباعدة أولًا', 'تشبيه بعيد أو TRIZ أو عكس الافتراض', 'المفاضلة بين الأصالة والملاءمة والتنفيذ'),
    'writing': ('الجمهور والفكرة الأساسية', 'أمثلة ملموسة بدل العموميات', 'افحص الاكتمال والدقة وحذف الحشو'),
}
RISK_CUES = ('مصيري', 'طوارئ', 'علاج', 'استثمار كبير', 'حذف نهائي', 'high stakes', 'irreversible', 'critical')
COMPLEX_CUES = ('حلل', 'حلّل', 'صمم', 'صمّم', 'ابحث', 'مقارنة', 'debug', 'design', 'strategy', 'forecast', 'proof')


def _nonempty(obj: object) -> bool:
    return isinstance(obj, str) and bool(obj.strip())


def plan(task: str, domain: str = 'general', level: str = 'L2') -> dict:
    if not _nonempty(task):
        raise ValueError('task must not be empty')
    if domain not in DOMAINS:
        raise ValueError('unknown domain: ' + domain)
    if level not in LEVELS:
        raise ValueError('level must be L0, L1, L2 or L3')
    return {
        'kind': 'black-dragon.v10.3/ultra-plan',
        'source': 'uploaded ultra-mind.rar (source instructions), extended for Black Dragon',
        'task': task.strip(), 'domain': domain, 'level': level,
        'execution_performed': False, 'agents_called': False,
        'stages': [{'number': i, 'name': CORE[i][0], 'check': CORE[i][1]} for i in STAGES[level]],
        'task_focus': TYPE_FOCUS[domain],
        'branches_required': 0 if level == 'L0' else 2 if level in ('L1', 'L2') else 3,
        'required_receipts': ['record why the chosen option beats alternatives', 'record a falsifier or counterexample',
                              'attach independent evidence where available'] if level in ('L2', 'L3') else [],
        'safety_gates': ['no credit spending, installation, publication, or private uploads without consent'],
        'limits': 'This is a proposed review plan. No task executed, claims verified, or AI agents called.',
    }


def _safe_local_path(root: Path, raw: str) -> Path:
    if not _nonempty(raw):
        raise ValueError('empty evidence file path')
    p = Path(raw)
    if p.is_absolute():
        raise ValueError('evidence paths must be relative to the packet directory')
    root = root.resolve()
    dst = (root / p).resolve()
    if not dst.is_relative_to(root):
        raise ValueError('evidence path escapes packet directory')
    if not dst.is_file():
        raise FileNotFoundError('evidence file not found')
    return dst


def _sha256_file(p: Path) -> str:
    digest = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def audit(packet: dict, packet_dir: Path) -> dict:
    """Structural validation + proof-of-file-integrity; NEVER grade answer truth."""
    if not isinstance(packet, dict):
        raise ValueError('audit packet must be a JSON object')
    failures, warnings, evidence = [], [], []
    level = packet.get('level', 'L2')
    domain = packet.get('domain', 'general')
    if level not in LEVELS: failures.append('invalid level')
    if domain not in DOMAINS: failures.append('invalid domain')
    if not _nonempty(packet.get('task')): failures.append('task is required')
    branches = 0 if level == 'L0' else 2 if level in ('L1', 'L2') else 3
    opts = packet.get('hypotheses', [])
    if not isinstance(opts, list):
        failures.append('hypotheses must be an array'); opts = []
    if len(opts) < branches:
        failures.append(f'{level}: need at least {branches} competing hypotheses')
    ids, approaches = [], []
    for i, opt in enumerate(opts):
        if not isinstance(opt, dict):
            failures.append(f'hypothesis {i} must be an object'); continue
        for key in ('id', 'approach', 'discriminator'):
            if not _nonempty(opt.get(key)):
                failures.append(f'hypothesis {i} missing {key}')
        if _nonempty(opt.get('id')): ids.append(opt['id'].strip())
        if _nonempty(opt.get('approach')):
            approaches.append(re.sub(r'\s+', ' ', opt['approach'].strip()).casefold())
    if len(ids) != len(set(ids)): failures.append('duplicate hypothesis IDs')
    if len(approaches) != len(set(approaches)): failures.append('duplicate approaches; alternatives must be distinct')
    if level != 'L0' and packet.get('selected') not in ids:
        failures.append('selected hypothesis ID must appear in hypotheses')
    if level in ('L2', 'L3'):
        if not _nonempty(packet.get('falsifier')): failures.append('missing falsifier/counterexample')
        if domain in ('decision', 'forecast', 'analysis') and not _nonempty(packet.get('outside_view')):
            failures.append('missing outside-view baseline / source')
    checks = packet.get('checks', [])
    if not isinstance(checks, list):
        failures.append('checks must be an array'); checks = []
    if level != 'L0' and not checks:
        failures.append('at least one independent verification proposal required')
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            failures.append(f'check {i} must be an object'); continue
        typ = c.get('kind')
        if typ == 'file-sha256':
            expected = c.get('sha256')
            if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
                failures.append(f'check {i}: invalid sha256'); continue
            try:
                target = _safe_local_path(packet_dir, c.get('file', ''))
                actual = _sha256_file(target)
            except (OSError, ValueError) as exc:
                failures.append(f'check {i}: {exc}'); continue
            match = actual.lower() == expected.lower()
            evidence.append({'check': i, 'kind': 'file-sha256', 'path': target.relative_to(packet_dir.resolve()).as_posix(),
                             'integrity_match': match, 'proves_answer_correct': False})
            if not match: failures.append(f'check {i}: file SHA-256 does not match')
        elif typ == 'external-reference':
            if not _nonempty(c.get('reference')):
                failures.append(f'check {i}: missing external reference')
            else:
                evidence.append({'check': i, 'kind': typ, 'status': 'declared-not-verified'})
                warnings.append(f'check {i}: external reference not fetched or fact-checked')
        else:
            failures.append(f'check {i}: unsupported check kind; no arbitrary command execution')
    return {
        'kind': 'black-dragon.v10.3/ultra-audit', 'structure_pass': not failures,
        'violations': failures, 'warnings': warnings,
        'files_with_matching_sha256': sum(e.get('integrity_match') is True for e in evidence),
        'evidence': evidence, 'reasoning_correctness_verified': False,
        'source_claims_verified': False, 'agents_called': False,
        'meaning': 'PASS checks packet structure and file-byte integrity only, not logical/factual correctness.',
    }


def calibrate(rows: object) -> dict:
    """Calculate Brier score and empirical bin calibration for *observed* binary forecasts."""
    if not isinstance(rows, list) or not rows:
        raise ValueError('forecast input must be a nonempty JSON array')
    if len(rows) > 100000:
        raise ValueError('forecast input exceeds 100000 observations')
    points = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict): raise ValueError(f'row {i} must be an object')
        p, y = r.get('probability'), r.get('outcome')
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError(f'row {i}: probability must be finite 0..1')
        if type(y) is not int or y not in (0, 1):
            raise ValueError(f'row {i}: observed outcome must be integer 0 or 1')
        points.append((float(p), y))
    n = len(points)
    base = sum(y for _, y in points) / n
    buckets = []
    for ix in range(5):
        lo, hi = ix / 5, (ix + 1) / 5
        subset = [(p, y) for p, y in points if (lo <= p < hi) or (ix == 4 and p == 1)]
        if subset:
            buckets.append({'probability_range': [lo, hi], 'n': len(subset),
                            'average_prediction': sum(p for p, _ in subset) / len(subset),
                            'observed_frequency': sum(y for _, y in subset) / len(subset)})
    score = sum((p-y)**2 for p,y in points)/n
    return {'kind':'black-dragon.v10.3/forecast-calibration', 'n':n, 'brier_score': score,
            'base_rate':base, 'constant_base_rate_brier':base*(1-base),
            'lower_is_better':True, 'bins':buckets,
            'interpretation':'Observed-data score, not a guarantee of future forecasting ability.'}
