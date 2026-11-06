#!/usr/bin/env python3
"""Keep auxiliary graph rows tied to complete target measurements and conditions."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.match_history import row_from_match,markdown
from shogi1995.match_statistics import match_summary


def fixture():
    games=[]
    for i in range(10):
        for color in (0,1):
            games.append({'opening_id':str(i),'start_sfen':'opening-'+str(i),'candidate_color':color,
                          'candidate_result':'win' if color==0 else 'loss',
                          'outcome':{'winner':0,'reason':'resign'}})
    engine={'complete':True,'id':'engine','engine_sha256':'binary','image_sha256':'image',
            'source_commit':'source','feature_difference':'new model','engine_options':{}}
    report={'complete':True,'backend':'86box','mode':'guest_fischer_auxiliary','nodes':None,
            'games':games,'expected_games':20,'opening_ids':[str(i) for i in range(10)],
            'clock_calibration':{'passed':True,'samples':[{'repeat':r,'engine':e,'passed':True,
                'requested_ms':5000,'host_ms':5040,'guest_ms':5005} for r in range(3) for e in (0,1)]},
            'started_at_utc':'2026-11-07T00:00:00+00:00','finished_at_utc':'2026-11-07T01:00:00+00:00',
            'baseline':copy.deepcopy(engine),'candidate':copy.deepcopy(engine),'initial_ms':180000,
            'increment_ms':2000,'max_plies':512,'network_delay':120,'network_delay2':1120,
            'common_engine_options':{'NetworkDelay':120,'NetworkDelay2':1120,'USI_Hash':2},
            'environment':{'signature':'environment'},'dataset_sha256':'openings',
            'measurement_commit':'measurement','measurement_sources':{},'elapsed_seconds':3600}
    report['score']=match_summary(games,True)
    return report


def row(report):return row_from_match(report,'run','results/match.json','result-sha')


class MatchHistoryTests(unittest.TestCase):
    def test_complete_match_is_graph_ready(self):
        value=row(fixture())
        self.assertEqual((value['games'],value['score_percent'],value['elo_difference']),(20,50,0))
        self.assertEqual(value['finished_at_utc'],'2026-11-07T01:00:00+00:00')
        self.assertIn('+09:00',value['finished_at_jst'])
        buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=list(value));writer.writeheader();writer.writerow(value)
        self.assertIn('elo_difference',buffer.getvalue());json.dumps(value,allow_nan=False)
        self.assertIn('20局',markdown([value]))

    def test_candidate_revision_shares_series_but_opponent_revision_does_not(self):
        original=fixture();baseline=row(original)['comparison_group']
        changed=copy.deepcopy(original);changed['candidate']['engine_sha256']='new-candidate'
        self.assertEqual(row(changed)['comparison_group'],baseline)
        changed=copy.deepcopy(original);changed['baseline']['engine_sha256']='new-opponent'
        self.assertNotEqual(row(changed)['comparison_group'],baseline)

    def test_time_dataset_or_environment_changes_split_series(self):
        original=fixture();baseline=row(original)['comparison_group']
        for field in ('initial_ms','dataset_sha256','environment'):
            changed=copy.deepcopy(original)
            changed[field]={'initial_ms':600000,'dataset_sha256':'different','environment':{'signature':'different'}}[field]
            self.assertNotEqual(row(changed)['comparison_group'],baseline)

    def test_native_and_incomplete_runs_rejected(self):
        for changes in ({'backend':'native'},{'nodes':64},{'complete':False},{'mode':'fixed_nodes_operational'}):
            report=fixture();report.update(changes)
            with self.assertRaisesRegex(ValueError,'real-time'):row(report)

    def test_clock_flag_alone_cannot_certify_bad_samples(self):
        for host in (5200,float('nan')):
            report=fixture();report['clock_calibration']['samples'][0]['host_ms']=host
            with self.assertRaisesRegex(ValueError,'clock calibration'):row(report)
        report=fixture();report['clock_calibration']['samples']=[]
        with self.assertRaisesRegex(ValueError,'six independent'):row(report)

    def test_score_recount_detects_altered_results(self):
        report=fixture();report['score']['wins']=20
        with self.assertRaisesRegex(ValueError,'independent recount'):row(report)

    def test_planned_opening_order_cannot_be_silently_changed(self):
        report=fixture();report['opening_ids'].reverse()
        with self.assertRaisesRegex(ValueError,'opening order'):row(report)

    def test_operational_failure_is_recorded_without_rating(self):
        report=fixture();report['games'][0]['outcome']['reason']='time_forfeit'
        report['score']=match_summary(report['games'],True)
        value=row(report)
        self.assertFalse(value['rating_eligible']);self.assertEqual(value['elo_difference'],'')
        self.assertEqual(value['opponent_operational_failures'],1)
        self.assertIn('運用異常により除外',markdown([value]))

    def test_unreported_per_engine_option_override_rejected(self):
        report=fixture();report['candidate']['engine_options']={'USI_Hash':8}
        with self.assertRaisesRegex(ValueError,'per-engine options'):row(report)

    def test_empty_history_explicitly_contains_no_measurements(self):
        self.assertIn('測定値は登録されていない',markdown([]))


if __name__=='__main__':unittest.main()
