import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.match_rules import Referee

KINGS = '4k4/9/9/9/9/9/9/9/4K4 b - 1'


class RefereeTests(unittest.TestCase):
    def test_increment_is_applied_once_and_host_time_is_rounded_up(self):
        r = Referee(KINGS, initial_ms=1000, increment_ms=2000)
        self.assertIsNone(r.accept('5i4i', 500.01))
        self.assertEqual(r.remaining, [2499, 1000])
        self.assertEqual(r.go_command(), 'go btime 2499 wtime 1000 binc 2000 winc 2000')

    def test_increment_cannot_rescue_a_move_after_the_existing_deadline(self):
        r = Referee(KINGS, initial_ms=1000, increment_ms=2000)
        self.assertEqual(r.accept('5i4i', 1000.01), {'winner':1, 'reason':'time_forfeit'})
        self.assertEqual(r.remaining, [-1, 1000])
        self.assertEqual(len(r.moves), 0)

    def test_resign_and_illegal_moves_do_not_earn_increment(self):
        for action in ['resign', '5i5a']:
            r = Referee(KINGS, initial_ms=1000, increment_ms=2000)
            self.assertIsNotNone(r.accept(action, 400))
            self.assertEqual(r.remaining, [600, 1000])

    def test_fourfold_repetition_includes_start_position(self):
        r = Referee(KINGS)
        sequence = ['5i4i','5a4a','4i5i','4a5a'] * 3
        for move in sequence[:-1]:
            self.assertIsNone(r.accept(move, 1))
        self.assertEqual(r.accept(sequence[-1], 1), {'winner':None, 'reason':'fourfold_repetition'})

    def test_continuous_check_loses_instead_of_drawing(self):
        r = Referee('4k4/5R3/9/9/9/9/9/9/4K4 b - 1')
        sequence = ['4b5b','5a4a','5b4b','4a5a'] * 3
        for move in sequence[:-1]:
            self.assertIsNone(r.accept(move, 1), move)
        self.assertEqual(r.accept(sequence[-1], 1), {'winner':1, 'reason':'perpetual_check'})

    def test_false_declaration_loses(self):
        r = Referee(KINGS)
        self.assertEqual(r.accept('win', 1), {'winner':1, 'reason':'illegal_declaration'})

    def test_black_27_point_rule_requires_28_points(self):
        camp = 'RBGG1GGBR/P7P/4K4/9/9/9/9/9/4k4 b '
        losing = Referee(camp + 'P 1')
        winning = Referee(camp + '2P 1')
        self.assertEqual(losing.accept('win',1), {'winner':1,'reason':'illegal_declaration'})
        self.assertEqual(winning.accept('win',1), {'winner':0,'reason':'declaration_win'})

    def test_move_limit(self):
        r = Referee(KINGS, max_plies=1)
        self.assertEqual(r.accept('5i4i', 1), {'winner':None, 'reason':'max_plies'})


if __name__ == '__main__':
    unittest.main()
