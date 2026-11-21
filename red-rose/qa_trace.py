"""V18: provenance-aware Q&A and capability trace (offline, read-only).

A01-A35 are PARAPHRASED decisions, NOT the literal original 1-1400 questions.
A linked native adapter is relevant to part of the goal, not proof that the
whole historical user request has been implemented. No remote or legacy calls.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
ID_RE = re.compile(r"^A\d{2}$")
HEADING_RE = re.compile(r"^### (A\d{2}) — (.+)$", flags=re.MULTILINE)
ASSESSMENTS = frozenset((
    'design_only', 'policy_verified', 'original_not_recovered',
    'related_partial', 'historical_status', 'agent_guidance'
))


def _parse_decisions(source):
    """Read actual markdown text. Never synthesize missing user Q&A."""
    blocks = re.split(r"(?=^### A\d{2} — )", source, flags=re.MULTILINE)
    result = {}
    for block in blocks:
        heading = HEADING_RE.match(block)
        if heading is None:
            continue
        ident, question = heading.groups()
        ans = re.search(r"^\*\*الإجابة:\*\*\s*(.+)$", block, flags=re.MULTILINE)
        attr = re.search(r"^\*\*التصنيف:\*\*\s*([UROG])\s*·\s*\*\*السند:\*\*\s*(.+)$",
                         block, flags=re.MULTILINE)
        if not ans or not attr or ident in result:
            raise ValueError("Malformed or duplicate attributed Q&A: " + ident)
        result[ident] = {
            "question_paraphrase": question,
            "answer_paraphrase": ans.group(1),
            "provenance_class": attr.group(1),
            "attribution_note": attr.group(2)
        }
    return result


def load_trace(*, directory=ROOT, registry):
    """Validate all 35 decisions against the *current* native adapter IDs."""
    if not isinstance(registry, dict) or not registry:
        raise ValueError("Current native registry required")
    base = Path(directory)
    data = json.loads((base / 'QA_TRACEABILITY.json').read_text(encoding='utf-8'))
    coverage = json.loads((base / 'QUESTION_COVERAGE.json').read_text(encoding='utf-8'))
    decisions = _parse_decisions((base / 'QUESTIONS_AND_ANSWERS.md').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or coverage.get('historical_design_target') != 1400:
        raise ValueError('Unsupported traceability schema')
    if data.get('truth_conditions', {}).get('original_1400_questions_recovered') is not False:
        raise ValueError('Trace must never falsely assert historical recovery')
    if coverage.get('original_1400_question_archive_complete') is not False:
        raise ValueError('Question archive completeness must have original-source evidence')
    if not decisions or len(decisions) != coverage.get('confirmed_answer_paraphrases'):
        raise ValueError('Q&A source missing or count drift')
    rows = data.get('rows')
    if not isinstance(rows, list):
        raise ValueError('Q&A trace must contain a rows array')
    if [r.get('id') for r in rows] != list(decisions):
        raise ValueError('Trace IDs and source Q&A headings must match in order')
    evidence = {}
    for item in rows:
        ident = item['id']
        if not ID_RE.fullmatch(ident) or item.get('assessment') not in ASSESSMENTS:
            raise ValueError('Invalid tracked decision: ' + str(ident))
        if item.get('original_question_verbatim') is not False or item.get('original_answer_verbatim') is not False:
            raise ValueError('The recorded items are paraphrases, not historical verbatim Q&A')
        links = item.get('linked_native_capabilities')
        if not isinstance(links, list) or len(links) != len(set(links)):
            raise ValueError('Duplicate or malformed capability links: ' + ident)
        unknown = set(links) - set(registry)
        if unknown:
            raise ValueError('Nonexecutable, unknown capability link: ' + ','.join(sorted(unknown)))
        if item['assessment'] == 'original_not_recovered' and links:
            raise ValueError('Unrecovered original Q&A must not imply implemented links')
        evidence[ident] = dict(item, **decisions[ident])
    return evidence, coverage


def trace(question_id=None, *, registry, directory=ROOT):
    """Read one documented decision or an honest whole-catalog coverage report."""
    record, coverage = load_trace(directory=directory, registry=registry)
    if question_id is None:
        statuses = Counter(v['assessment'] for v in record.values())
        linked = {name for v in record.values() for name in v['linked_native_capabilities']}
        return {
            'status': 'paraphrased_decision_trace_not_original_1400_archive',
            'tracked_decisions': len(record),
            'decisions_linked_to_native_adapters': sum(bool(v['linked_native_capabilities']) for v in record.values()),
            'registered_native_adapters_current': len(registry),
            'distinct_referenced_native_adapters': len(linked),
            'assessment_breakdown': dict(sorted(statuses.items())),
            'original_question_archive_complete': False,
            'historical_design_target': coverage['historical_design_target'],
            'historical_ranges': [
                {'range': r['range'], 'original_questions': r['verbatim_questions_in_this_repo'],
                 'original_answers': r['verbatim_answers_in_this_repo']}
                for r in coverage['historical_question_status']],
            'warning': '35 paraphrased decisions are not 1,400 verbatim answers; links do not prove feature completion.'
        }
    if type(question_id) is not str or not ID_RE.fullmatch(question_id):
        raise ValueError('Use a documented paraphrase ID A01..A35. Original 1..1400 are not recovered.')
    if question_id not in record:
        raise ValueError('Decision ID has no attributed source: ' + question_id)
    d = record[question_id]
    return {
        'status': 'documented_paraphrase_not_original_question',
        'id': question_id,
        'question_paraphrase': d['question_paraphrase'],
        'answer_paraphrase': d['answer_paraphrase'],
        'provenance_class': d['provenance_class'],
        'attribution_note': d['attribution_note'],
        'assessment': d['assessment'],
        'linked_native_capabilities': [
            {'id': ident, 'description': registry[ident][0],
             'effect': registry[ident][1], 'dependency': registry[ident][2]}
            for ident in d['linked_native_capabilities']
        ],
        'limitation': d['limit_or_next_evidence'],
        'verbatim_original_question': False,
        'verbatim_original_answer': False,
        'link_is_proof_of_full_completion': False
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Trace attributed Red Rose Q&A, no legacy execution')
    parser.add_argument('question_id', nargs='?')
    args = parser.parse_args()
    from capability_runtime import REGISTRY
    print(json.dumps(trace(args.question_id, registry=REGISTRY), ensure_ascii=False, indent=2))
