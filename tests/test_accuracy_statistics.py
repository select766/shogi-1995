import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.statistics import paired,summary,wilson

class AccuracyStatisticsTests(unittest.TestCase):
    def rows(self,values):
        return [dict(id=str(i),sfen=f'position {i}',expected='7g7f',match=bool(v)) for i,v in enumerate(values)]

    def test_partial_runs_keep_fixed_denominator(self):
        report=summary([{'match':True},{'match':False,'error':'VM exit'}],4)
        self.assertEqual(report['accuracy'],.25)
        self.assertEqual(report['errors'],1)
        self.assertEqual(report['measured'],2)

    def test_paired_counts_and_zero_difference(self):
        report=paired(self.rows([1,1,0,0]),self.rows([1,0,1,0]))
        self.assertEqual(report['both_correct'],1)
        self.assertEqual(report['baseline_only'],1)
        self.assertEqual(report['candidate_only'],1)
        self.assertEqual(report['both_wrong'],1)
        self.assertEqual(report['difference'],0)

    def test_identical_predictions_have_zero_paired_interval(self):
        a=self.rows([0,1,0,1]);r=paired(a,a)
        self.assertEqual(r['bootstrap_95'],{'lower':0.,'upper':0.})

    def test_misaligned_positions_rejected(self):
        a=self.rows([0,1]);b=self.rows([0,1]);b[0]['id']='another position'
        with self.assertRaises(ValueError):paired(a,b)

    def test_wilson_bounds_at_extremes(self):
        self.assertAlmostEqual(wilson(0,100)['lower'],0.)
        self.assertAlmostEqual(wilson(100,100)['upper'],1.)
        self.assertIsNone(wilson(0,0))

if __name__=='__main__':unittest.main()
