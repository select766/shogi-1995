from pathlib import Path
import sys
import tempfile
import unittest
import cshogi
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.halfkp_features import encode,INPUTS,material_initial_weights
from shogi1995.halfkp_linear import export,load,reference


class HalfKPLinearTests(unittest.TestCase):
    def test_file_round_trip_and_trailing_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.bin';weights=material_initial_weights()
            export(weights,path);self.assertEqual(path.stat().st_size,501568)
            np.testing.assert_array_equal(load(path),np.rint(weights*256))
            path.write_bytes(path.read_bytes()+b'x')
            with self.assertRaises(ValueError):load(path)

    def test_signed_rounding_and_clamp(self):
        board=cshogi.Board('4k4/9/9/9/9/9/4P4/9/4K4 b - 1')
        features=encode(board);weights=np.zeros(INPUTS,dtype=np.int64)
        unique=set(features[0])-set(features[1]);self.assertTrue(unique)
        index=unique.pop();weights[index]=128
        self.assertEqual(reference(board,weights),1)
        weights[index]=-128;self.assertEqual(reference(board,weights),-1)
        weights[index]=12001*256;self.assertEqual(reference(board,weights),12000)


if __name__=='__main__':unittest.main()
