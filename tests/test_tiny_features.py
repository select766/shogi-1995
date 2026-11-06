import sys
from pathlib import Path
import unittest
import random
import cshogi
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.tiny_features import encode, canonicalize, INPUTS, SYMMETRIC_INPUTS, ACTIVE


class TinyFeatureTests(unittest.TestCase):
    def test_capture_promotion_and_hand_conserve_feature_count(self):
        board = cshogi.Board()
        for move, expected_material in [('7g7f', 0), ('3c3d', 0), ('8h2b+', -1800), ('3a2b', 0)]:
            board.push_usi(move)
            features, material = encode(board)
            self.assertEqual(material, expected_material)
            self.assertEqual(features.shape, (2, ACTIVE))
            self.assertTrue(np.all((features >= 0) & (features < INPUTS)))

    def test_changing_side_swaps_perspectives_and_negates_material(self):
        board = cshogi.Board()
        for move in ('7g7f', '3c3d', '8h2b+'):
            board.push_usi(move)
        a, material = encode(board)
        fields = board.sfen().split()
        fields[1] = 'b' if fields[1] == 'w' else 'w'
        board.set_sfen(' '.join(fields))
        b, opposite = encode(board)
        np.testing.assert_array_equal(a[::-1], b)
        self.assertEqual(material, -opposite)

    def test_hand_count_uses_repeated_features(self):
        board = cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b 18P4L4N4S4G2B2R 1')
        x, material = encode(board)
        self.assertEqual(material, 18*90+4*315+4*405+4*495+4*540+2*855+2*990)
        self.assertEqual(len(set(x[0].tolist())), 7)
        self.assertEqual(sum(x[0] == x[0, 0]), 18)

    def test_cached_remapping_equals_direct_symmetric_encoding(self):
        board=cshogi.Board();rng=random.Random(1995)
        for _ in range(100):
            old,material=encode(board);new,symmetric_material=encode(board,True)
            np.testing.assert_array_equal(canonicalize(old),new)
            self.assertEqual(material,symmetric_material)
            self.assertTrue(np.all((new>=0)&(new<SYMMETRIC_INPUTS)))
            moves=list(board.legal_moves)
            if not moves:board=cshogi.Board()
            else:board.push(rng.choice(moves))

    def test_missing_piece_padding_uses_new_sentinel(self):
        board=cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b - 1')
        old,_=encode(board);new,_=encode(board,True)
        self.assertTrue(np.all(old==INPUTS));self.assertTrue(np.all(new==SYMMETRIC_INPUTS))
        np.testing.assert_array_equal(canonicalize(old),new)


if __name__ == '__main__':
    unittest.main()
