#!/usr/bin/env python3
"""Keep deferred preprocessing behind every planned timing run and producer exit."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('deferred',ROOT/'scripts/run-nnue-after-measurement.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class DeferredTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.original_root=module.ROOT;module.ROOT=Path(self.temp.name)
        self.addCleanup(setattr,module,'ROOT',self.original_root)
        self.plan={'dataset_sha256':'dataset','sample_ids':[str(i) for i in range(1024)],'measurements':[]}
        self.report={'complete':True,'total':1024,'measured':1024,
                     'dataset_sha256':self.plan['dataset_sha256'],'sample_ids':self.plan['sample_ids'],
                     'backend':'86box','mode':'fixed_byoyomi','milliseconds':2000,'nodes':None}
        for name in ('first','second'):
            pair=module.ROOT/name;pair.mkdir();(pair/'identity.json').write_text(json.dumps({'id':name}))
            self.plan['measurements'].append({'output':name,'identity_sha256':module.digest(pair/'identity.json')})

    def complete(self,name,report=None,operational=True):
        pair=module.ROOT/name
        for key in ('baseline','candidate'):
            (pair/(key+'.json')).write_text(json.dumps(self.report if report is None else report))
        (pair/'comparison.json').write_text(json.dumps({'comparison_operational_pass':operational}))

    def test_first_completed_run_does_not_release_second(self):
        self.complete('first')
        self.assertIsNone(module.completed_comparisons(self.plan))
        self.assertFalse(module.producer_gate(None,('S','123'),'123',True))

    def test_all_completed_runs_still_wait_for_live_producer(self):
        for name in ('first','second'):self.complete(name)
        completed=module.completed_comparisons(self.plan)
        self.assertEqual(set(completed),{'first','second'})
        self.assertFalse(module.producer_gate(completed,('R','123'),'123',True))
        self.assertTrue(module.producer_gate(completed,('Z','123'),'123',True))

    def test_dead_producer_with_missing_run_stops(self):
        self.complete('first')
        with self.assertRaisesRegex(RuntimeError,'without all complete'):
            module.producer_gate(module.completed_comparisons(self.plan),(None,None),'123',True)

    def test_reused_pid_does_not_make_incomplete_run_live(self):
        with self.assertRaises(RuntimeError):module.producer_gate(None,('S','456'),'123',True)

    def test_completed_report_with_operational_failure_rejected(self):
        self.complete('first');self.complete('second',operational=False)
        with self.assertRaisesRegex(ValueError,'operational investigation'):module.completed_comparisons(self.plan)

    def test_changed_identity_rejected(self):
        for name in ('first','second'):self.complete(name)
        (module.ROOT/'second/identity.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'identity changed'):module.completed_comparisons(self.plan)

    def test_wrong_time_control_rejected(self):
        self.complete('first');report=copy.deepcopy(self.report);report['milliseconds']=1000
        self.complete('second',report)
        with self.assertRaisesRegex(ValueError,'conditions differ'):module.completed_comparisons(self.plan)

    def test_incomplete_report_cannot_be_certified_by_comparison_flag(self):
        self.complete('first');report=copy.deepcopy(self.report);report['measured']=256
        self.complete('second',report)
        with self.assertRaisesRegex(ValueError,'not complete'):module.completed_comparisons(self.plan)

    def test_legacy_single_measurement_plan_remains_supported(self):
        self.complete('first');plan=dict(self.plan)
        first=plan.pop('measurements')[0]
        plan.update(measurement_output=first['output'],measurement_identity_sha256=first['identity_sha256'])
        completed=module.completed_comparisons(plan)
        self.assertEqual(list(completed),['first'])
        self.assertTrue(module.producer_gate(completed,('S','123'),'123',False))

    def test_duplicate_targets_rejected(self):
        self.plan['measurements']=[self.plan['measurements'][0]]*2
        with self.assertRaisesRegex(ValueError,'duplicate'):module.completed_comparisons(self.plan)


if __name__=='__main__':unittest.main()
