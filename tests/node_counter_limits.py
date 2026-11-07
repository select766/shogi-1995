#!/usr/bin/env python3
"""Native operational checks for full-width node limits, stop, and counter reset."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--freeze', type=Path,
                        default=ROOT / 'manifests/halfkp-model-frozen-20261107-1000.json')
    args = parser.parse_args()
    logs = args.output.with_suffix('.logs')
    if args.output.exists() or logs.exists():
        raise ValueError('preserve previous operation evidence')
    frozen = json.loads(args.freeze.read_text())
    if not frozen['complete'] or digest(args.model) != frozen['selected']['model_sha256']:
        raise ValueError('exact frozen model required')
    report = {'passed': False, 'backend': 'native',
              'scope': 'operation only; not Pentium timing or strength',
              'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'engine_sha256': digest(args.binary), 'model_sha256': digest(args.model),
              'freeze_sha256': digest(args.freeze), 'test_sha256': digest(Path(__file__)),
              'small_limits': []}
    options = {'Threads': 1, 'USI_Hash': 2, 'USI_OwnBook': False, 'USI_Ponder': False,
               'NetworkDelay': 0, 'NetworkDelay2': 0, 'EvalFile': str(args.model.resolve())}
    try:
        with Engine([str(args.binary.resolve())], ROOT, logs, options) as engine:
            for limit in (1, 15, 16, 17, 1024):
                engine.reset()
                row = engine.search_position('position startpos', f'go nodes {limit}', 20,
                                             diagnostics=True)
                assert 0 < row['final_nodes'] < limit + 4096, row
                report['small_limits'].append({'requested': limit, **row})
            engine.reset()
            large = (1 << 32) + 1
            engine.send('position startpos')
            engine.send(f'go nodes {large}')
            _, initial = engine.until('info depth ', 10)
            assert not any(line.startswith('bestmove ') for line in initial), initial
            try:
                engine.until('bestmove ', .05)
            except TimeoutError:
                pass
            else:
                raise AssertionError('large limit finished before explicit stop; possible truncation')
            started = time.monotonic()
            engine.send('stop')
            _, stopped = engine.until('bestmove ', 5)
            stop_seconds = time.monotonic() - started
            engine.send('shogi1995searchstats')
            _, lines = engine.until('info string shogi1995 search ', 5)
            stats = {key: int(value) for key, value in
                     (part.split('=') for part in lines[-1].split()[4:])}
            assert 0 < stats['nodes'] < large, stats
            report['large_limit'] = {'requested': large, 'explicit_stop': True,
                                     'stop_host_seconds': stop_seconds,
                                     'bestmove': stopped[-1].split()[1], **stats}
            engine.reset()
            restart = engine.search_position('position startpos', 'go nodes 32', 20,
                                             diagnostics=True)
            assert 0 < restart['final_nodes'] < 4096, restart
            report['restart_after_stop'] = restart
            report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
