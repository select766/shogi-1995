import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('bridge',Path(__file__).resolve().parents[1]/'src/bridge/main.py')
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class TimeAndPositionTests(unittest.TestCase):
    def test_startpos_turn(self):
        self.assertEqual(bridge.side_to_move('position startpos'),'b')
        self.assertEqual(bridge.side_to_move('position startpos moves 7g7f'),'w')
        self.assertEqual(bridge.side_to_move('position startpos moves 7g7f 3c3d'),'b')

    def test_sfen_turn_and_drop(self):
        self.assertEqual(bridge.side_to_move('position sfen 9/9/9/9/9/9/9/9/9 w P 23'),'w')
        self.assertEqual(bridge.side_to_move('position sfen 9/9/9/9/9/9/9/9/9 w P 23 moves P*5e'),'b')

    def test_asymmetric_tournament_clocks(self):
        command='go btime 180000 wtime 600000 binc 2000 winc 2000'
        self.assertAlmostEqual(bridge.hard_budget(command,'b'),179.8)
        self.assertAlmostEqual(bridge.hard_budget(command,'w'),599.8)

    def test_increment_is_not_current_time(self):
        self.assertEqual(bridge.hard_budget('go btime 100 binc 2000','b'),0)

    def test_byoyomi(self):
        self.assertAlmostEqual(bridge.hard_budget('go btime 0 byoyomi 5000','b'),4.8)

    def test_explicit_non_time_searches(self):
        for command in ('go infinite','go nodes 128','go depth 2'):
            self.assertIsNone(bridge.hard_budget(command,'b'))


if __name__=='__main__': unittest.main()
