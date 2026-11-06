#!/usr/bin/env python3
"""Encode freshly prepared original PSV records; never reads prior experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.tiny_features import encode, INPUTS, SYMMETRIC_INPUTS, STRIDE, ACTIVE


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--symmetric',action='store_true')
    args = p.parse_args()
    if args.output.exists():
        raise RuntimeError('output already exists')
    source = json.loads((args.data / 'manifest.json').read_text())
    assert source['complete']
    args.output.mkdir(parents=True)
    report = {'complete': False, 'inputs': SYMMETRIC_INPUTS if args.symmetric else INPUTS, 'stride': STRIDE, 'active': ACTIVE,
              'feature_layout':'canonical-halfking' if args.symmetric else 'full-king',
              'source_manifest_sha256': hashlib.sha256((args.data / 'manifest.json').read_bytes()).hexdigest(),
              'encoder_sha256': hashlib.sha256((ROOT / 'src/shogi1995/tiny_features.py').read_bytes()).hexdigest(),
              'splits': {}}
    start = time.monotonic()
    board = cshogi.Board()
    for split in ('train', 'validation'):
        if digest(args.data / (split + '.bin')) != source['outputs'][split]['sha256']:
            raise ValueError('prepared PSV hash differs: ' + split)
        records = np.memmap(args.data / (split + '.bin'), dtype=cshogi.PackedSfenValue, mode='r')
        x = np.lib.format.open_memmap(args.output / (split + '-features.npy'), mode='w+', dtype='<i4', shape=(len(records), 2, ACTIVE))
        y = np.lib.format.open_memmap(args.output / (split + '-targets.npy'), mode='w+', dtype='<f4', shape=(len(records), 2))
        for i, r in enumerate(records):
            board.set_psfen(r['sfen'])
            x[i], material = encode(board,args.symmetric)
            y[i] = (int(r['score']), material)
            if i % 100000 == 0:
                print(split, i, '/', len(records), flush=True)
        x.flush(); y.flush()
        report['splits'][split] = {'records': len(records),
                                 'features_sha256': digest(args.output / (split + '-features.npy')),
                                 'targets_sha256': digest(args.output / (split + '-targets.npy'))}
    report.update(complete=True, elapsed_seconds=time.monotonic() - start)
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
