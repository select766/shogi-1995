from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.speed_comparison import compare_speed


def report(host_ms):
    return dict(complete=True, total=4, measured=4, sample_ids=list(range(4)),
                dataset_sha256='data', mode='fixed_nodes', milliseconds=2000, nodes=10000,
                options={}, backend='86box', environment={'signature': 'Pentium'}, model_sha256='same',
                errors=0, illegal_moves=0, time_overruns=0,
                details=[dict(id=i, sfen='position', expected='5i4i', actual='5i4i',
                              final_nodes=10000, completed_depth=8, host_ms=host_ms) for i in range(4)])


class SpeedComparisonTests(unittest.TestCase):
    def test_exact_speedup_and_slowdown(self):
        result = compare_speed(report(100), report(80), replicates=100)
        self.assertAlmostEqual(result['median_host_time_saved_percent'], 20)
        self.assertTrue(result['speedup_supported'])
        self.assertAlmostEqual(result['paired_bootstrap_95_percent']['lower'], 20)
        self.assertFalse(compare_speed(report(100), report(120), replicates=100)['speedup_supported'])

    def test_different_model_tree_or_environment_cannot_claim_speedup(self):
        a, b = report(100), report(80)
        for key, value in [('model_sha256', 'different'), ('backend', 'native'), ('errors', 1)]:
            wrong = deepcopy(b); wrong[key] = value
            with self.assertRaises(ValueError): compare_speed(a, wrong, replicates=1)
        for key in ['actual', 'final_nodes', 'completed_depth']:
            wrong = deepcopy(b); wrong['details'][0][key] = None
            with self.assertRaises(ValueError): compare_speed(a, wrong, replicates=1)

    def test_zero_missing_or_nonfinite_clock_is_rejected(self):
        for invalid in [0, -1, None, float('nan'), float('inf')]:
            with self.assertRaises(ValueError): compare_speed(report(100), report(invalid), replicates=1)


if __name__ == '__main__':
    unittest.main()
