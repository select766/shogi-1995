"""Integer serialization and independent reference for a pure HalfKP sum."""
import struct
import numpy as np
from .halfkp_features import encode, INPUTS

SCALE=256


def export(weights_cp,path):
    values=np.rint(np.asarray(weights_cp,dtype=np.float64)*SCALE)
    if values.shape!=(INPUTS,) or not np.isfinite(values).all() or np.max(np.abs(values))>2**31-1:
        raise ValueError('invalid HalfKP weights')
    path.write_bytes(b'S95HKL1\0'+struct.pack('<II',INPUTS,SCALE)+values.astype('<i4').tobytes())


def load(path):
    data=path.read_bytes()
    if len(data)!=16+INPUTS*4 or data[:8]!=b'S95HKL1\0' or struct.unpack_from('<II',data,8)!=(INPUTS,SCALE):
        raise ValueError('invalid HalfKP linear file')
    return np.frombuffer(data,dtype='<i4',offset=16).astype(np.int64)


def reference(board,weights):
    features=encode(board)
    raw=int(weights[features[0]].sum()-weights[features[1]].sum())
    value=(raw+128)//SCALE if raw>=0 else -((-raw+128)//SCALE)
    return max(-12000,min(12000,value))
