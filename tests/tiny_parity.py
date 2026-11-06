#!/usr/bin/env python3
"""Require exact agreement between scalar C++ and exported integer network."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine
from shogi1995.tiny_quant import load, reference



def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--count', type=int, default=256)
    p.add_argument('--binary', type=Path, default=ROOT / '.local/guest-root/shogi')
    p.add_argument('--log-prefix',type=Path,default=ROOT/'.local/tests/tiny-parity')
    args = p.parse_args()
    weights = load(args.model)
    rows = np.memmap(args.data, dtype=cshogi.PackedSfenValue, mode='r')
    board = cshogi.Board()
    options = {'Threads': 1, 'USI_Hash': 2, 'USI_OwnBook': False, 'EvalFile': str(args.model.resolve())}
    with Engine([str(args.binary.resolve())], ROOT, args.log_prefix, options) as engine:
        for index in np.linspace(0, len(rows) - 1, args.count, dtype=int):
            board.set_psfen(rows[index]['sfen'])
            engine.send('position sfen ' + board.sfen()); engine.send('shogi1995eval')
            _, lines = engine.until('info string shogi1995 eval ', 5)
            actual = int(lines[-1].split()[-1]); expected = reference(board, weights)
            assert actual == expected, (int(index), board.sfen(), expected, actual)
    print(json.dumps({'positions': args.count, 'exact_value_matches': args.count, 'passed': True,
                      'engine_sha256': hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                      'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
                      'validation_data_sha256':hashlib.sha256(args.data.read_bytes()).hexdigest(),
                      'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'verified_at_utc':datetime.now(timezone.utc).isoformat()}))


if __name__ == '__main__':
    main()
