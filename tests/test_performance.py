from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.performance import compare_performance


class PerformanceTests(unittest.TestCase):
    def test_only_aligned_available_counters_are_compared(self):
        a = [{'id': 'a', 'nps': 100}, {'id': 'b', 'nps': 200, 'final_nps': 210}]
        b = [{'id': 'a', 'nps': 50, 'final_nps': 60, 'host_ms': 2050, 'final_time': 2005},
             {'id': 'b', 'nps': 300, 'final_nps': 420}]
        result = compare_performance(a, b)
        self.assertEqual(result['baseline']['final_nps']['count'], 1)
        self.assertEqual(result['paired_candidate_over_baseline']['nps']['median'], 1.)
        self.assertEqual(result['paired_candidate_over_baseline']['final_nps']['median'], 2.)
        self.assertEqual(result['paired_candidate_over_baseline']['final_nps']['count'], 1)
        self.assertEqual(result['candidate']['host_minus_final_guest_ms']['median'], 45.)
        self.assertEqual(result['baseline']['host_minus_final_guest_ms']['count'], 0)
        with self.assertRaises(ValueError):
            compare_performance(a, b[::-1])

    def test_zero_and_missing_values_never_become_infinite_ratios(self):
        a = [{'id': 'a', 'nps': 0}, {'id': 'b', 'nps': None}, {'id': 'c', 'nps': float('nan')}]
        b = [{'id': x, 'nps': 5} for x in ['a', 'b', 'c']]
        result = compare_performance(a, b)
        self.assertEqual(result['baseline']['nps'], {'count': 1, 'minimum': 0., 'p10': 0., 'median': 0., 'p90': 0., 'maximum': 0.})
        self.assertEqual(result['paired_candidate_over_baseline']['nps'], {'count': 0})


if __name__ == '__main__':
    unittest.main()
