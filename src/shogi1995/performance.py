"""Diagnostic speed distributions; never mix final counters with USI info lines."""
import math
import numpy as np


FIELDS = ('host_ms', 'nps', 'nodes', 'depth', 'final_nps', 'final_nodes', 'completed_depth')


def distribution(values):
    values = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not values:
        return {'count': 0}
    return dict(count=len(values), minimum=min(values), p10=float(np.quantile(values, .1)),
                median=float(np.median(values)), p90=float(np.quantile(values, .9)), maximum=max(values))


def compare_performance(baseline, candidate):
    if len(baseline) != len(candidate) or any(a['id'] != b['id'] for a, b in zip(baseline, candidate)):
        raise ValueError('performance rows must be position aligned')
    result = {
        name: {field: distribution(row.get(field) for row in rows) for field in FIELDS}
        for name, rows in [('baseline', baseline), ('candidate', candidate)]
    }
    result['paired_candidate_over_baseline'] = {}
    for field in ('nps', 'final_nps', 'final_nodes'):
        ratios = []
        for a, b in zip(baseline, candidate):
            x, y = a.get(field), b.get(field)
            if (isinstance(x, (int, float)) and isinstance(y, (int, float))
                    and math.isfinite(x) and math.isfinite(y) and x > 0 and y >= 0):
                ratios.append(y / x)
        result['paired_candidate_over_baseline'][field] = distribution(ratios)
    for name, rows in [('baseline', baseline), ('candidate', candidate)]:
        result[name]['host_minus_final_guest_ms'] = distribution(
            row['host_ms'] - row['final_time'] for row in rows
            if isinstance(row.get('host_ms'), (int, float)) and isinstance(row.get('final_time'), (int, float))
        )
    result['scope'] = ('Diagnostic only. nps/nodes/depth come from the last regular USI info line; '
                       'final_* counters require an explicit engine diagnostic. Missing counters are not substituted. '
                       'Different models can visit different trees, so NPS ratios alone do not establish arithmetic speedups.')
    return result
