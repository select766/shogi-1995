"""Validate comparable measurements and describe predeclared position strata."""
from .statistics import paired, summary


def validate_conditions(baseline, candidate):
    if not (baseline['complete'] and candidate['complete']):
        raise ValueError('incomplete measurement')
    for report in (baseline, candidate):
        ids = report['sample_ids']
        if (report['total'] != len(ids) or report['measured'] != len(ids)
                or [r['id'] for r in report['details']] != ids):
            raise ValueError('complete measurement does not contain all declared positions')
    for key in ('dataset_sha256', 'sample_ids', 'mode', 'milliseconds', 'nodes', 'options', 'backend'):
        if key not in baseline or key not in candidate or baseline[key] != candidate[key]:
            raise ValueError('different measurement condition: ' + key)
    a = baseline.get('environment', {}).get('signature')
    b = candidate.get('environment', {}).get('signature')
    if not a or not b or a != b:
        raise ValueError('different measurement condition: environment')


def stratified(baseline, candidate, records):
    """Descriptive strata only; do not select a model or change the fixed denominator."""
    if len(baseline) != len(candidate):
        raise ValueError('different sample count')
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('duplicate dataset IDs')
    indexed = {r['id']: r for r in records}
    groups = {}
    for a, b in zip(baseline, candidate):
        record = indexed[a['id']]
        if record['sfen'] != a['sfen'] or record['bestmove'] != a['expected']:
            raise ValueError('stratification dataset differs from measured position')
        score = abs(record['eval'])
        band = '0..299' if score < 300 else '300..999' if score < 1000 else '1000+'
        keys = [('turn', 'black' if record['turn'] == 0 else 'white'),
                ('abs_teacher_eval', band), ('in_check', str(bool(record['in_check'])).lower())]
        for key in keys:
            left, right = groups.setdefault(key, ([], []))
            left.append(a); right.append(b)
    results = []
    for (dimension, value), (left, right) in sorted(groups.items()):
        results.append({'dimension': dimension, 'value': value, 'positions': len(left),
                        'baseline': summary(left, len(left)), 'candidate': summary(right, len(right)),
                        'paired': paired(left, right)})
    return {'purpose': 'descriptive diagnostics; not separate acceptance tests',
            'multiple_comparisons_adjusted': False, 'strata': results}
