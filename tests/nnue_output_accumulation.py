#!/usr/bin/env python3
"""Exercise narrow output sums and wide fallback at real int32 boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.halfkp_features import INPUTS, STRIDE
from shogi1995.sessions import COMMON
from shogi1995.tiny_quant import load, reference
from shogi1995.usi import Engine


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--width', type=int, default=2)
    p.add_argument('--expected-kernel-width', type=int, choices=(0,8,16))
    args = p.parse_args()
    if not 1 <= args.width <= 32:
        p.error('width must be 1..32')
    if args.work.exists() or args.output.exists():
        raise ValueError('preserve previous attempt')
    args.work.mkdir(parents=True)
    maximum, minimum = np.iinfo(np.int32).max, np.iinfo(np.int32).min
    cases = [
        ('rounding', 6272, 0, 0, 32),
        ('positive-safe', maximum - 128, 0, 0, 32),
        ('positive-rounding-fallback', maximum - 127, 0, 0, 64),
        ('negative-safe', minimum + 129, 0, 0, 32),
        ('negative-rounding-fallback', minimum + 128, 0, 0, 64),
        ('minimum-bias', minimum, 0, 0, 64),
        ('maximum-bias', maximum, 0, 0, 64),
        ('positive-product-overflow', maximum - 1, 32767, 0, 64),
        ('negative-product-overflow', minimum + 1, -32768, 0, 64),
        ('hidden-safe', 6272, 2, 3, 32),
        ('hidden-product-overflow', maximum - 1, 32767, 3, 64),
    ]
    models = []
    width = args.width
    for name, bias, weight, hidden, bits in cases:
        data = b'S95NN03\0' + struct.pack('<4I', INPUTS, width, hidden, STRIDE)
        data += np.zeros((INPUTS, width), dtype='<i2').tobytes()
        data += np.full(width, 128, dtype='<i4').tobytes()
        data += np.zeros((hidden, width * 2), dtype='<i2').tobytes()
        data += np.full(hidden, 8192, dtype='<i4').tobytes()
        data += np.full(hidden or width * 2, weight, dtype='<i2').tobytes()
        data += struct.pack('<i', int(bias))
        path = args.work / (name + '.bin')
        path.write_bytes(data)
        models.append((name, path, bits))
    records = np.memmap(args.data, dtype=cshogi.PackedSfenValue, mode='r')
    indices = np.linspace(0, len(records) - 1, 16, dtype=int)
    board = cshogi.Board()
    binary = ROOT / '.local/guest-root/shogi'
    results = []
    with Engine([str(binary)], ROOT, args.work / 'engine.logs', COMMON) as engine:
        def output_bits():
            engine.send('shogi1995evalstats')
            _, lines = engine.until('info string shogi1995 accumulators ', 5)
            stats = dict(item.split('=') for item in lines[-1].split()[4:])
            if 'output_bits' not in stats:
                raise ValueError('build the output-accumulation implementation first')
            if args.expected_kernel_width is not None:
                expected = args.expected_kernel_width if int(stats['output_bits']) else 0
                assert int(stats.get('kernel_width', -1)) == expected, stats
            return int(stats['output_bits'])
        for name, path, bits in models:
            engine.send('setoption name EvalFile value ' + str(path.resolve()))
            engine.reset()
            assert output_bits() == bits, name
            weights = load(path)
            for index in indices:
                board.set_psfen(records[index]['sfen'])
                engine.send('position sfen ' + board.sfen())
                engine.send('shogi1995eval')
                _, lines = engine.until('info string shogi1995 eval ', 5)
                actual = int(lines[-1].split()[-1])
                assert actual == reference(board, weights), (name, int(index), actual)
            results.append({'case': name, 'output_bits': bits, 'positions': len(indices),
                            'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        engine.send('setoption name EvalFile value <none>')
        engine.reset()
        assert output_bits() == 0
    result = {'passed': True, 'cases': results, 'model_disable_resets_output_mode': True,
              'width': width, 'expected_kernel_width': args.expected_kernel_width,
              'engine_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'scope': 'integer boundary and model-switch validation; not speed or strength'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
