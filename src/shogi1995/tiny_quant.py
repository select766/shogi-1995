"""Reference arithmetic for the exported scalar integer evaluator."""
import struct
import numpy as np
from .tiny_features import encode, INPUTS, STRIDE


def load(path):
    data = path.read_bytes()
    assert data[:8] == b'S95NN01\0'
    inputs, width, hidden, stride = struct.unpack_from('<4I', data, 8)
    assert inputs == INPUTS and stride == STRIDE
    offset = 24
    def read(dtype, shape):
        nonlocal offset
        n = int(np.prod(shape))
        a = np.frombuffer(data, dtype=dtype, count=n, offset=offset).reshape(shape).astype(np.int64)
        offset += n * np.dtype(dtype).itemsize
        return a
    weights = (read('<i2', (inputs, width)), read('<i4', (width,)),
               read('<i2', (hidden, 2 * width)), read('<i4', (hidden,)),
               read('<i2', (hidden,)), read('<i4', (1,)))
    assert offset == len(data)
    return weights


def reference(board, weights):
    embedding, bias, fc, fc_bias, out, out_bias = weights
    features, material = encode(board)
    acc = []
    for perspective in features:
        valid = perspective[perspective != INPUTS]
        acc.append(np.clip(embedding[valid].sum(axis=0) + bias, 0, 128))
    h = np.clip((fc @ np.concatenate(acc) + fc_bias + 32) // 64, 0, 128)
    raw = int(h @ out + out_bias[0])
    correction = (raw + 128) // 256 if raw >= 0 else -((-raw + 128) // 256)
    return max(-12000, min(12000, material + correction))

