#!/usr/bin/env python3
"""Play native GNU Shogi against uniformly random legal moves."""
import argparse
import hashlib
import json
import random
import sys
import time
import traceback
from pathlib import Path

import cshogi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.match_rules import Referee
from shogi1995.usi import Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new output directory')
    parser.add_argument('--games', type=int, default=200)
    parser.add_argument('--seed', type=int, default=20261117)
    parser.add_argument('--depth', type=int, default=2, choices=range(2, 30))
    parser.add_argument('--max-plies', type=int, default=512)
    args = parser.parse_args()
    if args.games < 1 or args.max_plies < 1:
        parser.error('--games and --max-plies must be positive')
    binary = ROOT / '.local/native-gnushogi/src/gnushogir'
    if not binary.is_file():
        parser.error('native GNU binary missing; see historical/README.md')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    games = []
    meta = {'engine_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'seed': args.seed, 'depth': args.depth, 'max_plies': args.max_plies,
            'random': 'uniform over cshogi legal moves', 'games': games}

    def save():
        tmp = out / 'results.tmp'
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        tmp.replace(out / 'results.json')

    rng = random.Random(args.seed)
    save()
    try:
        command = [sys.executable, str(ROOT / 'historical/usi.py'), '--backend', 'native',
                   '--run-root', str(out)]
        with Engine(command, ROOT, out / 'trace') as engine:
            for i in range(args.games):
                engine.reset()
                referee = Referee(cshogi.STARTING_SFEN, initial_ms=100000000,
                                  max_plies=args.max_plies)
                side = i % 2
                start = time.monotonic()
                result = None
                thinks = []
                while not result:
                    result = referee.terminal()
                    if result:
                        break
                    if referee.board.turn == side:
                        position = 'position startpos' + (
                            ' moves ' + ' '.join(referee.moves) if referee.moves else '')
                        think = engine.search_position(position, f'go depth {args.depth}', 60)
                        thinks.append(think)
                        move = think['actual']
                    else:
                        move = cshogi.move_to_usi(rng.choice(list(referee.board.legal_moves)))
                    # No clock adjudication: depth, not wall time, is the controlled resource.
                    result = referee.accept(move, 0)
                game = {'number': i + 1, 'gnu_side': side, 'result': result,
                        'plies': len(referee.moves), 'moves': referee.moves,
                        'elapsed_sec': round(time.monotonic() - start, 2), 'thinks': thinks}
                games.append(game)
                save()
                print(json.dumps({k: v for k, v in game.items() if k not in ('moves', 'thinks')}),
                      flush=True)
    except BaseException:
        meta['error'] = traceback.format_exc()
        save()
        raise


if __name__ == '__main__':
    main()
