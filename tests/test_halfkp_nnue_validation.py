"""Independent batch arithmetic must agree with board-based integer inference."""
import importlib.util
from pathlib import Path
import sys
import unittest

import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.halfkp_features import INPUTS, STRIDE, encode
from shogi1995.tiny_quant import reference

spec = importlib.util.spec_from_file_location('nnue_validation', ROOT / 'scripts/validate-halfkp-nnue.py')
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class NNUEValidationTests(unittest.TestCase):
    def test_batch_scores_equal_board_reference_with_captures_and_promotions(self):
        rng = np.random.default_rng(20261106)
        board = cshogi.Board()
        boards = []
        for _ in range(256):
            moves = list(board.legal_moves)
            if not moves:
                board.reset()
                moves = list(board.legal_moves)
            board.push(moves[int(rng.integers(len(moves)))])
            boards.append(board.copy())
        features = np.stack([encode(b) for b in boards])
        for hidden in [0, 3]:
            width = 2
            embedding = rng.integers(-80, 81, (INPUTS, width), dtype=np.int64)
            embedding[np.arange(81) * STRIDE] = 0
            weights = (
                embedding, np.array([30, -20], dtype=np.int64),
                rng.integers(-128, 129, (hidden, 2 * width), dtype=np.int64),
                rng.integers(-4096, 4097, hidden, dtype=np.int64),
                rng.integers(-2000, 2001, hidden or 2 * width, dtype=np.int64),
                np.array([-128], dtype=np.int64),
            )
            expected = np.array([reference(b, weights) for b in boards])
            actual = validation.integer_scores(features, weights)
            np.testing.assert_array_equal(actual, expected)
            self.assertGreater(len(np.unique(actual)), 20)


if __name__ == '__main__':
    unittest.main()
