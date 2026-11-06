"""Paired Pentium speed evidence only when model and searched trees agree."""
import math
import numpy as np
from .comparison import validate_conditions
from .performance import compare_performance


def compare_speed(baseline, candidate, seed=20261106, replicates=10000):
    validate_conditions(baseline, candidate)
    if baseline['backend'] != '86box' or baseline['mode'] != 'fixed_nodes':
        raise ValueError('Pentium fixed-node measurements required')
    model = baseline.get('model_sha256')
    if not model or model != candidate.get('model_sha256'):
        raise ValueError('identical frozen model required')
    for report in (baseline, candidate):
        if any(report[key] != 0 for key in ('errors', 'illegal_moves', 'time_overruns')):
            raise ValueError('operational failure invalidates speed comparison')
    savings = []
    for a, b in zip(baseline['details'], candidate['details']):
        for key in ('id', 'sfen', 'expected', 'actual', 'final_nodes', 'completed_depth'):
            if a.get(key) is None or a.get(key) != b.get(key):
                raise ValueError('different or missing search evidence: ' + key)
        x, y = a.get('host_ms'), b.get('host_ms')
        if not all(isinstance(t, (int, float)) and math.isfinite(t) and t > 0 for t in (x, y)):
            raise ValueError('positive finite host timings required')
        savings.append((1 - y / x) * 100)
    if not savings:
        raise ValueError('empty speed comparison')
    if replicates <= 0:
        raise ValueError('positive bootstrap count required')
    values = np.asarray(savings)
    rng = np.random.default_rng(seed)
    draws = []
    for start in range(0, replicates, 1000):
        indices = rng.integers(0, len(values), size=(min(1000, replicates - start), len(values)))
        draws.extend(np.median(values[indices], axis=1).tolist())
    low, high = map(float, np.quantile(draws, [.025, .975]))
    return {
        'positions': len(values), 'identical_model_and_search_results': True,
        'median_host_time_saved_percent': float(np.median(values)),
        'paired_bootstrap_95_percent': {'lower': low, 'upper': high},
        'speedup_supported': low > 0, 'replicates': replicates, 'seed': seed,
        'performance': compare_performance(baseline['details'], candidate['details']),
        'scope': 'Pentium fixed-node speed diagnostic; not real-time agreement or strength',
        'limitation': 'Position bootstrap does not account for unknown game or temporal block correlation; use alternating blocks and inspect their observations.',
    }
