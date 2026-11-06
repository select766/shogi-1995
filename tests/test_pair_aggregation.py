import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pair_evaluation', ROOT / 'scripts/evaluate-pair.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)


class PairAggregationTests(unittest.TestCase):
    def test_memory_observations_stay_paired_with_their_own_vm(self):
        parts = [
            {'details': [{'id': 'a', 'match': True}], 'elapsed_seconds': 2,
             'guest_memory': {'free': 20}, 'guest_memory_end': {'free': 19},
             'finished_at_utc': 'first'},
            {'details': [{'id': 'b', 'match': False}], 'elapsed_seconds': 3,
             'guest_memory': {'free': 18}, 'guest_memory_end': {'free': 17},
             'finished_at_utc': 'last'},
        ]
        result = pair.aggregate(parts, ['a', 'b'], 'candidate')
        self.assertTrue(result['complete'])
        self.assertEqual((result['matches'], result['total'], result['elapsed_seconds']), (1, 2, 5))
        self.assertEqual(result['guest_memory_end'], {'free': 17})
        self.assertEqual(result['finished_at_utc'], 'last')
        self.assertEqual(result['guest_memory_blocks'], [
            {'block': '000-candidate.json', 'start': {'free': 20}, 'end': {'free': 19}},
            {'block': '001-candidate.json', 'start': {'free': 18}, 'end': {'free': 17}},
        ])
        self.assertEqual(parts[0]['guest_memory_end'], {'free': 19})
        # Missing diagnostics in the last VM must not reuse an earlier VM.
        del parts[-1]['guest_memory_end']
        result = pair.aggregate(parts, ['a', 'b'], 'candidate')
        self.assertNotIn('guest_memory_end', result)
        self.assertIsNone(result['guest_memory_blocks'][-1]['end'])

    def test_partial_runs_keep_the_frozen_denominator(self):
        result = pair.aggregate([{'details': [{'id': 'a', 'match': True}], 'elapsed_seconds': 2}], ['a', 'b'], 'baseline')
        self.assertFalse(result['complete'])
        self.assertEqual(result['accuracy'], .5)
        self.assertEqual(result['measured'], 1)
        self.assertNotIn('guest_memory_blocks', result)


if __name__ == '__main__':
    unittest.main()
