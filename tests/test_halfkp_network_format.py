from pathlib import Path
import struct
import sys
import tempfile
import unittest
import cshogi
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.halfkp_features import encode,INPUTS,STRIDE
from shogi1995.tiny_quant import load,reference


def write_model(path,hidden=0):
    width=8;board=cshogi.Board('4k4/9/9/9/9/9/4P4/9/4K4 b - 1')
    x=encode(board);feature=(set(x[0])-set(x[1])).pop()
    emb=np.zeros((INPUTS,width),dtype='<i2');emb[feature,0]=64
    bias=np.zeros(width,dtype='<i4');fc=np.zeros((hidden,width*2),dtype='<i2');fb=np.zeros(hidden,dtype='<i4')
    out=np.zeros(hidden or width*2,dtype='<i2');out[0]=4
    if hidden:fc[0,0]=64
    payload=b'S95NN03\0'+struct.pack('<4I',INPUTS,width,hidden,STRIDE)
    path.write_bytes(payload+emb.tobytes()+bias.tobytes()+fc.tobytes()+fb.tobytes()+out.tobytes()+struct.pack('<i',0))
    return board


class HalfKPNetworkFormatTests(unittest.TestCase):
    def test_two_and_three_layer_integer_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            for hidden in [0,8]:
                path=Path(folder)/f'model-{hidden}.bin';board=write_model(path,hidden)
                self.assertEqual(reference(board,load(path)),91)
                expected=24+INPUTS*8*2+8*4+hidden*16*2+hidden*4+(hidden or 16)*2+4
                self.assertEqual(path.stat().st_size,expected)

    def test_standard_layout_rejects_legacy_stride_and_trailing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.bin';write_model(path);data=path.read_bytes()
            path.write_bytes(data[:20]+struct.pack('<I',2120)+data[24:])
            with self.assertRaises(AssertionError):load(path)
            path.write_bytes(data+b'x')
            with self.assertRaises(AssertionError):load(path)

    def test_legacy_full_and_symmetric_formats_still_read(self):
        with tempfile.TemporaryDirectory() as folder:
            for magic,inputs,hidden in [(b'S95NN01\0',171720,1),(b'S95NN02\0',95400,0)]:
                path=Path(folder)/'legacy.bin'
                data=magic+struct.pack('<4I',inputs,1,hidden,2120)
                data+=np.zeros(inputs,dtype='<i2').tobytes()+np.zeros(1,dtype='<i4').tobytes()
                data+=np.zeros(hidden*2,dtype='<i2').tobytes()+np.zeros(hidden,dtype='<i4').tobytes()
                data+=np.zeros(hidden or 2,dtype='<i2').tobytes()+np.zeros(1,dtype='<i4').tobytes()
                path.write_bytes(data)
                board=cshogi.Board('4k4/9/9/9/9/9/4P4/9/4K4 b - 1')
                self.assertEqual(reference(board,load(path)),90)


if __name__=='__main__':unittest.main()
