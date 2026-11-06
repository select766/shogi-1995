#!/usr/bin/env python3
"""Require exact agreement between scalar C++ and exported integer network."""
import argparse
import json
from pathlib import Path
import struct
import sys
import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine
from shogi1995.tiny_features import encode, INPUTS, STRIDE


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--count', type=int, default=256)
    args = p.parse_args()
    weights = load(args.model)
    rows = np.memmap(args.data, dtype=cshogi.PackedSfenValue, mode='r')
    board = cshogi.Board()
    options = {'Threads': 1, 'USI_Hash': 2, 'USI_OwnBook': False, 'EvalFile': str(args.model.resolve())}
    with Engine([str(ROOT / '.local/guest-root/shogi')], ROOT, ROOT / '.local/tests/tiny-parity', options) as engine:
        for index in np.linspace(0, len(rows) - 1, args.count, dtype=int):
            board.set_psfen(rows[index]['sfen'])
            engine.send('position sfen ' + board.sfen()); engine.send('shogi1995eval')
            _, lines = engine.until('info string shogi1995 eval ', 5)
            actual = int(lines[-1].split()[-1]); expected = reference(board, weights)
            assert actual == expected, (int(index), board.sfen(), expected, actual)
    print(json.dumps({'positions': args.count, 'exact_value_matches': args.count, 'passed': True}))


if __name__ == '__main__':
    main()
