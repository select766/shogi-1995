from pathlib import Path
import random
import sys
import unittest
import cshogi
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.halfkp_features import encode, material_initial_weights, INPUTS, STRIDE
from shogi1995.tiny_features import encode as old_encode


class HalfKPFeatureTests(unittest.TestCase):
    def test_all_hand_ordinals_are_distinct(self):
        b=cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b 18P4L4N4S4G2B2R 1')
        x=encode(b)
        self.assertEqual(len(set(x[0])),38)
        self.assertEqual(set(x[0]%STRIDE),set(range(1,19))|set(range(39,43))|set(range(49,53))|
                         set(range(59,63))|set(range(69,73))|set(range(79,81))|set(range(85,87)))

    def test_gold_and_promoted_minor_share_category(self):
        gold=cshogi.Board('4k4/9/9/9/4G4/9/9/9/4K4 b - 1')
        pawn=cshogi.Board('4k4/9/9/9/4+P4/9/9/9/4K4 b - 1')
        np.testing.assert_array_equal(encode(gold),encode(pawn))

    def test_missing_pieces_use_bona_zero_for_current_king(self):
        b=cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b - 1');x=encode(b)
        self.assertTrue(np.all(x%STRIDE==0))

    def test_material_initialization_and_side_symmetry_over_legal_moves(self):
        b=cshogi.Board();rng=random.Random(20261106);weights=material_initial_weights()
        for i in range(400):
            x=encode(b);_,material=old_encode(b)
            self.assertEqual(float(weights[x[0]].sum()-weights[x[1]].sum()),material)
            self.assertTrue(np.all((x>=0)&(x<INPUTS)))
            fields=b.sfen().split();fields[1]='w' if fields[1]=='b' else 'b'
            opposite=cshogi.Board(' '.join(fields))
            np.testing.assert_array_equal(encode(opposite),x[::-1])
            moves=list(b.legal_moves)
            if not moves:b=cshogi.Board()
            else:b.push(rng.choice(moves))


if __name__=='__main__':unittest.main()
