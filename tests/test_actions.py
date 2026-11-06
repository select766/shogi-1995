from pathlib import Path
import sys
import unittest
import cshogi

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.actions import classify
from shogi1995.statistics import summary


class ActionTests(unittest.TestCase):
    def test_resignation_is_a_valid_nonmatching_response(self):
        row=classify(cshogi.Board(),'resign');row['match']=False
        report=summary([row],1)
        self.assertEqual(report['illegal_moves'],0)
        self.assertEqual(report['resignations'],1)
        self.assertEqual(report['accuracy'],0)

    def test_declaration_follows_27_point_rule_including_black_28(self):
        camp='RBGG1GGBR/P7P/4K4/9/9/9/9/9/4k4 b '
        self.assertFalse(classify(cshogi.Board(camp+'P 1'),'win')['legal'])
        self.assertTrue(classify(cshogi.Board(camp+'2P 1'),'win')['legal'])
        self.assertFalse(classify(cshogi.Board(),'win')['legal'])

    def test_normal_move_validation_does_not_mutate_board(self):
        board=cshogi.Board();before=board.sfen()
        self.assertEqual(classify(board,'7g7f'),{'action':'move','legal':True})
        self.assertFalse(classify(board,'7g7e')['legal'])
        self.assertFalse(classify(board,'P*5e')['legal'])
        self.assertEqual(before,board.sfen())

    def test_malformed_move_is_illegal_without_native_decode(self):
        for actual in ['none','0000','7g7f extra','P*5z','9z0a','']:
            with self.subTest(actual=actual):self.assertEqual(classify(cshogi.Board(),actual),{'action':'invalid','legal':False})


if __name__=='__main__':unittest.main()
