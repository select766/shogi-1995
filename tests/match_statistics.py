#!/usr/bin/env python3
"""Check paired-color scoring, failure attribution and finite JSON export."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.match_statistics import match_summary


def game(opening,color,result,reason='resign'):
    winner=None if result=='draw' else color if result=='win' else 1-color
    return {'opening_id':opening,'start_sfen':'position-'+str(opening),'candidate_color':color,
            'candidate_result':result,'outcome':{'winner':winner,'reason':reason}}


class MatchStatisticsTests(unittest.TestCase):
    def test_balanced_twenty_games_uses_ten_opening_clusters(self):
        games=[game(i,color,'win' if color==0 else 'loss') for i in range(10) for color in (0,1)]
        summary=match_summary(games,True)
        self.assertEqual((summary['wins'],summary['losses'],summary['completed_opening_pairs']),(10,10,10))
        self.assertEqual(summary['elo_difference_estimate'],0)
        self.assertAlmostEqual(summary['score_rate_95']['lower'],.0705305916532624)
        self.assertAlmostEqual(summary['score_rate_95']['upper'],.9294694083467376)

    def test_clean_sweep_does_not_imply_certain_infinite_rating(self):
        games=[game(i,color,'win') for i in range(10) for color in (0,1)]
        summary=match_summary(games,True)
        self.assertTrue(summary['rating_eligible'])
        self.assertIsNone(summary['elo_difference_estimate'])
        self.assertEqual(summary['elo_difference_boundary'],'+infinity')
        self.assertLess(summary['score_rate_95']['lower'],1)
        self.assertIsNotNone(summary['elo_difference_95']['lower'])
        self.assertEqual(summary['elo_difference_95']['upper_boundary'],'+infinity')
        json.dumps(summary,allow_nan=False)

    def test_draws_count_half_point(self):
        summary=match_summary([game(0,0,'draw'),game(0,1,'draw')],True)
        self.assertEqual((summary['draws'],summary['score_rate'],summary['elo_difference_estimate']),(2,.5,0))

    def test_incomplete_color_pair_not_a_rating_measurement(self):
        summary=match_summary([game(0,0,'win')],True)
        self.assertEqual(summary['score_rate'],1)
        self.assertFalse(summary['rating_eligible'])
        self.assertIsNone(summary['elo_difference_estimate'])

    def test_operational_smoke_mode_suppresses_rating(self):
        summary=match_summary([game(0,0,'win'),game(0,1,'loss')],False)
        self.assertFalse(summary['rating_eligible'])
        self.assertIsNone(summary['score_rate_95'])

    def test_failures_attributed_to_losing_engine_and_suppress_rating(self):
        for color in (0,1):
            for result,loser in [('win','baseline'),('loss','candidate')]:
                with self.subTest(color=color,result=result):
                    summary=match_summary([game(0,color,result,'time_forfeit'),game(0,1-color,'draw')],True)
                    self.assertEqual(summary['operational_failures'][loser]['time_forfeit'],1)
                    self.assertFalse(summary['operational_pass'])
                    self.assertFalse(summary['rating_eligible'])

    def test_conflicting_result_rejected(self):
        row=game(0,0,'win');row['candidate_result']='loss'
        with self.assertRaisesRegex(ValueError,'disagrees'):match_summary([row],True)

    def test_color_and_opening_identity_required(self):
        with self.assertRaisesRegex(ValueError,'each color'):
            match_summary([game(0,0,'win'),game(0,0,'loss')],True)
        rows=[game(0,0,'win'),game(0,1,'loss')];rows[1]['start_sfen']='different'
        with self.assertRaisesRegex(ValueError,'different starting'):
            match_summary(rows,True)

    def test_empty_result_is_finite_and_unrated(self):
        summary=match_summary([],True)
        self.assertIsNone(summary['score_rate'])
        self.assertFalse(summary['rating_eligible'])
        json.dumps(summary,allow_nan=False)


if __name__=='__main__':unittest.main()
