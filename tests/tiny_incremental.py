#!/usr/bin/env python3
"""Verify every evaluated accumulator during fixed-node searches and match reference moves."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--reference', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--binary', type=Path, default=ROOT / '.local/guest-root/shogi')
    p.add_argument('--expected-kernel-width', type=int, choices=(0,8,16))
    p.add_argument('--expected-fc-packed', type=int, choices=(0,1))
    p.add_argument('--expected-fc-bits', type=int, choices=(0,32,64))
    p.add_argument('--expected-accumulator-packed', type=int, choices=(0,1))
    p.add_argument('--expected-accumulator-bits', type=int, choices=(16,32))
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('output exists')
    reference = json.loads(args.reference.read_text())
    assert reference['complete'] and reference['mode'] == 'fixed_nodes'
    options = {**reference['options'], 'EvalFile': str(args.model.resolve()), 'EvalVerify': True}
    binary = args.binary.resolve()
    results = []
    with Engine([str(binary)], ROOT, str(args.output) + '.logs', options) as engine:
        for row in reference['details']:
            engine.reset()
            actual = engine.search(row['sfen'], nodes=reference['nodes'],diagnostics=reference.get('capture_search_diagnostics',False))
            assert actual['actual'] == row['actual'], (row['id'], row['actual'], actual)
            expected_nodes=row.get('final_nodes',row['nodes'])
            actual_nodes=actual.get('final_nodes',actual['nodes'])
            assert actual_nodes == expected_nodes, (row['id'], expected_nodes, actual)
            if reference.get('capture_search_diagnostics',False):
                assert actual['completed_depth'] == row['completed_depth'], (row['id'], row, actual)
            results.append({'id': row['id'], 'actual': actual['actual'], 'nodes': actual_nodes,
                            'completed_depth':actual.get('completed_depth')})
        engine.send('shogi1995evalstats')
        _, lines = engine.until('info string shogi1995 accumulators ', 5)
        stats = {k: int(v) for k, v in (item.split('=') for item in lines[-1].split()[4:])}
        assert stats['incremental'] > 1000 and stats['refresh'] > 100 and stats['verified'] > 1000, stats
        if args.expected_kernel_width is not None:
            assert stats.get('kernel_width') == args.expected_kernel_width, stats
        if args.expected_fc_packed is not None:
            assert stats.get('fc_packed') == args.expected_fc_packed, stats
        if args.expected_fc_bits is not None:
            assert stats.get('fc_bits') == args.expected_fc_bits, stats
        if args.expected_accumulator_packed is not None:
            assert stats.get('accumulator_packed') == args.expected_accumulator_packed, stats
        if args.expected_accumulator_bits is not None:
            assert stats.get('accumulator_bits') == args.expected_accumulator_bits, stats
        # Reloading a model must invalidate cached accumulators, including at the current position.
        engine.send('shogi1995eval'); _, before = engine.until('info string shogi1995 eval ', 5)
        engine.send('setoption name EvalFile value ' + str(args.model.resolve()))
        engine.reset(); engine.send('position sfen ' + reference['details'][-1]['sfen'])
        engine.send('shogi1995eval'); _, after = engine.until('info string shogi1995 eval ', 5)
        # Search restores the root position, so these must remain exactly equal after reload.
        assert before[-1] == after[-1], (before[-1], after[-1])
    result = {'passed': True, 'positions': len(results), 'counters': stats,
              'same_bestmoves_and_nodes': True, 'model_reload_passed': True,
              'same_completed_depth': True if reference.get('capture_search_diagnostics',False) else None,
              'engine_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
              'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
