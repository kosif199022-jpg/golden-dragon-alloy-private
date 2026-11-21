"""Agent-drafted question bank D0001-D1500: load, validate, summarise, render.

These 1,500 items were WRITTEN BY AN AI AGENT at the owner's request on
2026-11-21, each with a proposed answer. They are drafts awaiting the owner's
approval. They are NOT the historical 1-1400 questions, whose original texts
remain unrecovered (see QUESTION_COVERAGE.json), and a drafted answer is not an
implemented capability.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK_DIR = ROOT / 'questions'
SOURCE = 'agent-draft-not-user-approved'
STATES = ('implemented', 'partial', 'missing', 'policy')
EFFORTS = ('S', 'M', 'L')
TOTAL = 1500

# Group plan. 1-150 and 1401-1500 themes were chosen by the agent; 151-400 and
# 401-1400 follow the theme list the owner supplied on 2026-11-21.
GROUPS = (
    ('G01', 1, 'هوية المهارة وفكرة الانصهار الكامل', 'agent'),
    ('G02', 51, 'معمارية المهارة والسجل والتشغيل', 'agent'),
    ('G03', 101, 'الجودة والأمان والتسليم بين الوكلاء', 'agent'),
    ('G04', 151, 'التفكير والإبداع', 'owner'),
    ('G05', 201, 'الرياضيات والأبعاد', 'owner'),
    ('G06', 251, 'أساليب الرسم', 'owner'),
    ('G07', 301, 'المكتبات المجانية', 'owner'),
    ('G08', 351, 'الفيزياء المستخدمة في المونتاج', 'owner'),
    ('G09', 401, 'الذكاء والتفكير واتخاذ القرارات', 'owner'),
    ('G10', 451, 'البرمجة وإنشاء التطبيقات', 'owner'),
    ('G11', 501, 'تحليل الأكواد واكتشاف الأخطاء وإصلاحها', 'owner'),
    ('G12', 551, 'البحث والمعرفة والذاكرة', 'owner'),
    ('G13', 601, 'الرسم والتصميم والهوية البصرية', 'owner'),
    ('G14', 651, 'الشخصيات والتحريك', 'owner'),
    ('G15', 701, 'المونتاج والإخراج السينمائي', 'owner'),
    ('G16', 751, 'الصوت والموسيقى والمزامنة', 'owner'),
    ('G17', 801, 'المؤثرات البصرية والمحاكاة', 'owner'),
    ('G18', 851, 'النمذجة والتحريك ثلاثي الأبعاد', 'owner'),
    ('G19', 901, 'الرياضيات والهندسة والعلوم', 'owner'),
    ('G20', 951, 'تحليل الصور والفيديو', 'owner'),
    ('G21', 1001, 'الأتمتة والتحكم والتنفيذ', 'owner'),
    ('G22', 1051, 'الإنترنت والمواقع وجمع البيانات', 'owner'),
    ('G23', 1101, 'قواعد البيانات وتحليل المعلومات', 'owner'),
    ('G24', 1151, 'المحاسبة والمراجعة وإدارة الأعمال', 'owner'),
    ('G25', 1201, 'الأمن والخصوصية والاختبارات', 'owner'),
    ('G26', 1251, 'التعلم المستمر وتطوير القدرات', 'owner'),
    ('G27', 1301, 'الابتكار ودمج القدرات', 'owner'),
    ('G28', 1351, 'التكامل والاختبار النهائي', 'owner'),
    ('G29', 1401, 'اللغة العربية والكابشن وفهم طلب صاحب الشغل', 'agent'),
    ('G30', 1451, 'خارطة التنفيذ وأولويات الانصهار ومعايير القبول', 'agent'),
)


def _text(value, low, high, label):
    if not isinstance(value, str) or not low <= len(value.strip()) <= high or '\n' in value:
        raise ValueError(f'{label} must be single-line text of {low}..{high} characters')
    return value.strip()


def load_bank(*, registry, directory=BANK_DIR):
    """Return all drafted items after strict validation; never fills gaps."""
    directory = Path(directory)
    items = []
    seen_questions = {}
    for group, first, title, theme_source in GROUPS:
        path = directory / f'{group}.json'
        if not path.is_file():
            raise ValueError('missing question group file: ' + path.name)
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('group') != group or data.get('source') != SOURCE:
            raise ValueError(f'{group}: wrong group id or missing agent-draft source label')
        rows = data.get('items')
        if not isinstance(rows, list) or len(rows) != 50:
            raise ValueError(f'{group}: exactly 50 items are required')
        for offset, row in enumerate(rows):
            ident = first + offset
            if not isinstance(row, dict) or row.get('id') != ident:
                raise ValueError(f'{group}: expected id {ident}')
            question = _text(row.get('q'), 12, 400, f'question {ident}')
            answer = _text(row.get('a'), 25, 900, f'answer {ident}')
            if row.get('state') not in STATES or row.get('effort') not in EFFORTS:
                raise ValueError(f'item {ident}: invalid state or effort')
            cap = row.get('cap')
            if cap is not None and cap not in registry:
                raise ValueError(f'item {ident}: unknown capability link {cap!r}')
            key = ' '.join(question.split())
            if key in seen_questions:
                raise ValueError(f'item {ident} repeats question {seen_questions[key]}')
            seen_questions[key] = ident
            items.append({'id': ident, 'draft_id': f'D{ident:04d}', 'group': group,
                          'group_title': title, 'theme_chosen_by': theme_source,
                          'question': question, 'proposed_answer': answer,
                          'state': row['state'], 'capability': cap,
                          'effort': row['effort'], 'source': SOURCE,
                          'owner_approved': False})
    if [i['id'] for i in items] != list(range(1, TOTAL + 1)):
        raise ValueError('draft ids must be exactly 1..1500')
    return items


def summarize(items):
    """Counts only. A drafted answer never counts as a delivered capability."""
    per_group = {}
    for item in items:
        slot = per_group.setdefault(item['group'], {'title': item['group_title'],
                                                    **{s: 0 for s in STATES}})
        slot[item['state']] += 1
    return {'status': 'agent_drafted_questions_awaiting_owner_approval',
            'total': len(items), 'source': SOURCE, 'owner_approved': 0,
            'by_state': dict(Counter(i['state'] for i in items)),
            'by_effort': dict(Counter(i['effort'] for i in items)),
            'linked_to_native_adapter': sum(i['capability'] is not None for i in items),
            'themes_chosen_by_owner': sum(i['theme_chosen_by'] == 'owner' for i in items),
            'themes_chosen_by_agent': sum(i['theme_chosen_by'] == 'agent' for i in items),
            'groups': per_group,
            'are_these_the_original_1400_questions': False,
            'state_is_agent_assessment_not_test_evidence': True,
            'warning': 'Drafted by an AI agent. "implemented" is the drafting agent\'s reading '
                       'of the code, not a verified test result; nothing here is approved yet.'}


def find(items, *, query=None, group=None, state=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('limit must be 1..200')
    if state is not None and state not in STATES:
        raise ValueError('state must be one of ' + ', '.join(STATES))
    if group is not None and group not in {g[0] for g in GROUPS}:
        raise ValueError('group must be G01..G30')
    needle = query.casefold().strip() if isinstance(query, str) else ''
    out = []
    for item in items:
        if group and item['group'] != group:
            continue
        if state and item['state'] != state:
            continue
        if needle and needle not in (item['question'] + ' ' + item['proposed_answer']).casefold():
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


STATE_AR = {'implemented': 'موجودة', 'partial': 'جزئية', 'missing': 'ناقصة', 'policy': 'قاعدة'}


def render_markdown(items):
    """One readable document for the owner to review and approve."""
    stats = summarize(items)
    lines = ['# 🌹 بنك الأسئلة المقترحة D0001–D1500 (مسودة وكيل، بانتظار موافقة المالك)', '',
             '> **تنبيه:** هذه الأسئلة وإجاباتها **كتبها وكيل AI** بطلب المالك يوم 2026-11-21. '
             'ليست الأسئلة التاريخية 1–1400 (نصوصها الأصلية ما زالت غير مستردّة)، '
             'والإجابة المقترحة ليست قدرة منفّذة. الحالة المكتوبة تقدير الوكيل من قراءة الكود وليست نتيجة اختبار.',
             '', '## الإحصاء', '',
             f"- الإجمالي: {stats['total']} · موافَق عليه من المالك: 0",
             '- الحالة: ' + ' · '.join(f"{STATE_AR[s]} {stats['by_state'].get(s, 0)}" for s in STATES),
             '- حجم الشغل: ' + ' · '.join(f"{e} {stats['by_effort'].get(e, 0)}" for e in EFFORTS),
             '', '| المجموعة | الأرقام | المحور | موجودة | جزئية | ناقصة | قاعدة |',
             '|---|---|---|---:|---:|---:|---:|']
    for group, first, title, chosen in GROUPS:
        g = stats['groups'][group]
        mark = '' if chosen == 'owner' else ' *(محور من اختيار الوكيل)*'
        lines.append(f"| {group} | {first}–{first + 49} | {title}{mark} | {g['implemented']} | "
                     f"{g['partial']} | {g['missing']} | {g['policy']} |")
    current = None
    for item in items:
        if item['group'] != current:
            current = item['group']
            lines += ['', f"## {current} — {item['group_title']}", '']
        cap = f" · `{item['capability']}`" if item['capability'] else ''
        lines += [f"**{item['draft_id']}. {item['question']}**", '',
                  f"{item['proposed_answer']}", '',
                  f"_{STATE_AR[item['state']]} · حجم {item['effort']}{cap}_", '']
    return '\n'.join(lines).rstrip('\n') + '\n'


if __name__ == '__main__':
    from capability_runtime import REGISTRY
    bank = load_bank(registry=REGISTRY)
    (ROOT / 'QUESTIONS_1500_AGENT_DRAFT.md').write_bytes(render_markdown(bank).encode('utf-8'))
    print(json.dumps(summarize(bank), ensure_ascii=False))
