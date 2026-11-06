import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import cshogi
from shogi1995.packed import psv_move_usi

class PackedMoveTests(unittest.TestCase):
    def test_ordinary_move(self):
        self.assertEqual(psv_move_usi((60<<7)+59),'7g7f')
    def test_drop_bit_is_not_promotion(self):
        raw=(1<<14)+(1<<7)+40
        self.assertEqual(psv_move_usi(raw),'P*5e')
        b=cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b P 1')
        self.assertTrue(b.is_legal(b.move_from_usi(psv_move_usi(raw))))
    def test_promotion_bit(self):
        raw=(1<<15)+(37<<7)+36
        self.assertEqual(psv_move_usi(raw),'5b5a+')
        b=cshogi.Board('k8/4P4/9/9/9/9/9/9/4K4 b - 1')
        self.assertTrue(b.is_legal(b.move_from_usi(psv_move_usi(raw))))
    def test_bad_drop(self):
        with self.assertRaises(ValueError):psv_move_usi((1<<14)+(8<<7))

if __name__=='__main__':unittest.main()
