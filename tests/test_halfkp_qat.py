"""Regression cases for exact exported-integer rounding during QAT."""
from pathlib import Path
import sys
import unittest

import cshogi
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shogi1995.halfkp_features import encode
from shogi1995.halfkp_network import HalfKPNetwork


class HalfKPQATTests(unittest.TestCase):
    def test_output_half_cp_rounds_away_from_zero(self):
        x = torch.from_numpy(np.stack([encode(cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b - 1'))]))
        for hidden in [0, 3]:
            model = HalfKPNetwork(2, hidden, qat=True)
            for sign in [-1, 1]:
                with torch.no_grad():
                    model.out.weight.zero_()
                    # Exported bias is +/-6272: exactly +/-24.5 CP, which
                    # formerly became +/-24.499998 in the float32 QAT path.
                    model.out.bias.fill_(sign * 6272 / 153600)
                    score = model(x).item() * 600
                self.assertAlmostEqual(score, sign * 25, places=4)

    def test_integer_forward_keeps_training_gradients(self):
        x = torch.from_numpy(np.stack([encode(cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b - 1'))]))
        model = HalfKPNetwork(2, 3, qat=True)
        with torch.no_grad():
            model.embedding.weight.zero_(); model.bias.fill_(.1)
            model.fc.weight.fill_(.1); model.fc.bias.fill_(.3)
            model.out.weight.fill_(.2)
        model(x).sum().backward()
        for name, parameter in model.named_parameters():
            self.assertIsNotNone(parameter.grad, name)
            self.assertTrue(torch.isfinite(parameter.grad).all(), name)
            self.assertTrue(torch.any(parameter.grad != 0), name)


if __name__ == '__main__':
    unittest.main()
