#!/usr/bin/env python3
"""Compare complete fixed-node runs of the same model on the target Pentium."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.speed_comparison import compare_speed


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('baseline', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('preserve previous comparison')
    reports = [json.loads(path.read_text()) for path in (args.baseline, args.candidate)]
    result = compare_speed(*reports)
    result['compared_at_utc'] = datetime.now(timezone.utc).isoformat()
    result['measurements'] = {
        key: {'path': str(path.resolve()), 'sha256': digest(path), 'engine_sha256': report['engine_sha256'],
              'model_sha256': report['model_sha256']}
        for key, path, report in zip(('baseline', 'candidate'), (args.baseline, args.candidate), reports)
    }
    result['comparison_sources'] = {
        name: digest(ROOT / name) for name in ('scripts/compare-fixed-node-speed.py',
                                             'src/shogi1995/speed_comparison.py',
                                             'src/shogi1995/comparison.py', 'src/shogi1995/performance.py')
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
