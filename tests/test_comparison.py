import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.comparison import stratified, validate_conditions


class ComparisonTests(unittest.TestCase):
    def report(self):
        return dict(complete=True, dataset_sha256='abc', sample_ids=['a'], mode='fixed_byoyomi',
                    milliseconds=2000, nodes=None, options={}, backend='86box', environment={'signature':'cpu1'},
                    total=1, measured=1, details=[{'id':'a'}])

    def test_same_conditions(self):
        validate_conditions(self.report(), self.report())

    def test_incomplete_details_rejected_even_when_complete_flag_is_true(self):
        for key, value in [('details',[]), ('total',2), ('measured',0), ('details',[{'id':'wrong'}])]:
            a=self.report();a[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):validate_conditions(a,self.report())

    def test_backend_environment_and_incomplete_rejected(self):
        for key, value in [('backend','native'), ('environment',{'signature':'cpu2'}), ('complete',False)]:
            a=self.report();b=copy.deepcopy(a);b[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):validate_conditions(a,b)

    def positions(self):
        records=[];left=[];right=[]
        for i, score in enumerate([0,299,300,-999,1000,-2000]):
            records.append(dict(id=str(i), sfen=f'sfen {i}', bestmove='7g7f', eval=score,
                                turn=i%2, in_check=i%2==0))
            common=dict(id=str(i), sfen=f'sfen {i}', expected='7g7f')
            left.append(dict(common,match=i%2==0));right.append(dict(common,match=i!=0))
        return records,left,right

    def test_bands_boundaries_and_fixed_totals(self):
        records,left,right=self.positions();result=stratified(left,right,records)
        for dimension in ['turn','abs_teacher_eval','in_check']:
            rows=[r for r in result['strata'] if r['dimension']==dimension]
            self.assertEqual(sum(r['positions'] for r in rows),6)
            self.assertEqual(sum(r['baseline']['matches'] for r in rows),3)
            self.assertEqual(sum(r['candidate']['matches'] for r in rows),5)
        bands=[r for r in result['strata'] if r['dimension']=='abs_teacher_eval']
        self.assertTrue(all(r['positions']==2 for r in bands))

    def test_changed_source_and_duplicate_ids_rejected(self):
        records,left,right=self.positions()
        with self.assertRaises(ValueError):stratified(left,right[:-1],records)
        with self.assertRaises(ValueError):stratified(left,right,records+[records[0]])
        records[0]['bestmove']='2g2f'
        with self.assertRaises(ValueError):stratified(left,right,records)


if __name__=='__main__':unittest.main()
