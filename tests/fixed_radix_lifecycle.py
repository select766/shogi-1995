#!/usr/bin/env python3
"""Verify exact-head dispatch, fallback values, and model-switch invalidation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.sessions import COMMON
from shogi1995.tiny_quant import load, reference
from shogi1995.usi import Engine


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--binary', type=Path, default=ROOT / '.local/guest-root/shogi')
    p.add_argument('--guest-manifest', type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.work.exists() or args.output.exists():
        raise ValueError('preserve previous attempt')
    raw = args.model.read_bytes()
    assert sha(args.model) == 'd42b68f3da24fe3d77d9549aeca1c0b6a4ced375d7ff7fa6b14c737d876bdeff'
    assert raw[:8] == b'S95NN03\0'
    assert struct.unpack_from('<4I', raw, 8) == (125388, 8, 0, 1548)
    args.work.mkdir(parents=True)
    records = np.memmap(args.data, dtype=cshogi.PackedSfenValue, mode='r')
    board = cshogi.Board()
    sfens = [cshogi.STARTING_SFEN]
    for index in np.linspace(0, len(records) - 1, 15, dtype=int):
        board.set_psfen(records[index]['sfen'])
        sfens.append(board.sfen())
    weights = load(args.model)
    cases = [('frozen', args.model, weights, 1)]
    if args.guest_manifest:
        manifest = json.loads(args.guest_manifest.read_text())
        image = Path(manifest['command'][manifest['command'].index('--image') + 1])
        assert sha(image) == manifest['image_sha256']
        assert manifest['model_sha256'] == sha(args.model)
        command = manifest['command']
        engine_sha = manifest['engine_sha256']
        selected_path = manifest['configured_guest_options']['EvalFile']
    else:
        command = [str(args.binary.resolve())]
        engine_sha = sha(args.binary)
        selected_path = str(args.model.resolve())
        # A coefficient difference at any lane must select the generic head,
        # even when integer rounding happens to hide the numerical difference.
        for lane in range(16):
            mutated = bytearray(raw)
            offset = len(raw) - 36 + lane * 2
            struct.pack_into('<h', mutated, offset, struct.unpack_from('<h', raw, offset)[0] + 1)
            path = args.work / f'coefficient-{lane}.bin'
            path.write_bytes(mutated)
            cases.append((f'coefficient-{lane}', path, load(path), 0))
        mutated = bytearray(raw)
        struct.pack_into('<i', mutated, len(raw) - 4, struct.unpack_from('<i', raw, len(raw) - 4)[0] + 1)
        path = args.work / 'bias.bin'
        path.write_bytes(mutated)
        cases.append(('bias', path, load(path), 0))
    rows = []
    with Engine(command, ROOT, args.work / 'engine.logs', COMMON) as engine:
        def stats():
            engine.send('shogi1995evalstats')
            _, lines = engine.until('info string shogi1995 accumulators ', 10)
            return {k: int(v) for k, v in (x.split('=') for x in lines[-1].split()[4:])}

        def check_values(expected_weights):
            # isready resets to StartSFEN; explicitly initialize every position.
            for sfen in sfens:
                board.set_sfen(sfen)
                engine.send('position sfen ' + sfen)
                engine.send('shogi1995eval')
                _, lines = engine.until('info string shogi1995 eval ', 10)
                actual = int(lines[-1].split()[-1])
                expected = reference(board, expected_weights)
                assert actual == expected, (sfen, actual, expected)

        if args.guest_manifest:
            # Assert automatic startup selection before explicitly reloading.
            assert stats()['head_radix'] == 1
            check_values(weights)
        for name, path, expected_weights, mode in cases:
            engine_path = selected_path if args.guest_manifest else str(path.resolve())
            engine.send('setoption name EvalFile value ' + engine_path)
            engine.reset()
            observed = stats()
            assert observed['head_radix'] == mode, (name, observed)
            assert observed['output_bits'] == 32, observed
            check_values(expected_weights)
            rows.append({'case': name, 'head_radix': mode, 'positions': len(sfens), 'model_sha256': sha(path)})
        engine.send('setoption name EvalFile value <none>')
        engine.reset()
        if args.guest_manifest:
            # Prepared launchers pin EvalFile; an external client cannot
            # disable the selected model. Native tests exercise invalidation.
            engine.send('getoption EvalFile')
            _, lines = engine.until('Options[EvalFile]', 10)
            assert lines[-1].split('=', 1)[1].strip() == selected_path
            assert stats()['head_radix'] == 1
            check_values(weights)
        else:
            assert stats()['head_radix'] == 0
            engine.send('shogi1995eval')
            _, lines = engine.until('info string shogi1995 eval ', 10)
            assert int(lines[-1].split()[-1]) == 0
        engine.send('setoption name EvalFile value ' + selected_path)
        engine.reset()
        assert stats()['head_radix'] == 1
        check_values(weights)
    result = {'passed': True, 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'engine_sha256': engine_sha, 'model_sha256': sha(args.model),
              'test_sha256': sha(Path(__file__)), 'cases': rows,
              'guest_automatic_selection': bool(args.guest_manifest),
              'native_disable_and_reenable_passed': not bool(args.guest_manifest),
              'guest_model_cannot_be_silently_disabled': bool(args.guest_manifest),
              'reload_passed': True, 'independent_integer_values': True,
              'scope': 'loaded-head dispatch, fallback and USI model-switch correctness; not speed or strength'}
    if args.guest_manifest:
        result['image_sha256'] = manifest['image_sha256']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
