#!/usr/bin/env python3
"""Replay and audit a random-match results file with the host referee."""
import argparse
from collections import Counter
import json
import random
import statistics
import sys
from pathlib import Path

import cshogi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.match_rules import Referee


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    if data.get('error'):
        raise ValueError('run reported an error')
    outcomes = Counter()
    checks = promotions = drops = searches = 0
    rng = random.Random(data['seed'])
    for i, game in enumerate(data['games']):
        if game['number'] != i + 1 or game['gnu_side'] != i % 2:
            raise ValueError(f'game {i + 1}: number or side mismatch')
        ref = Referee(cshogi.STARTING_SFEN, initial_ms=100000000,
                      max_plies=data['max_plies'])
        terminal = None
        think_index = 0
        for move in game['moves']:
            if terminal is not None:
                raise ValueError(f'game {i + 1}: moves after end')
            if ref.board.turn == game['gnu_side']:
                if game['thinks'][think_index]['actual'] != move:
                    raise ValueError(f'game {i + 1}: search move mismatch')
                think_index += 1
            else:
                expected = cshogi.move_to_usi(rng.choice(list(ref.board.legal_moves)))
                if move != expected:
                    raise ValueError(f'game {i + 1}: random move mismatch')
            terminal = ref.accept(move, 0)
            promotions += move.endswith('+')
            drops += '*' in move
        if terminal is None and game['result']['reason'] in ('resign', 'illegal_move', 'illegal_declaration', 'declaration_win'):
            # The final non-board action is present in the engine search record.
            terminal = ref.accept(game['thinks'][think_index]['actual'], 0)
            think_index += 1
        if think_index != len(game['thinks']):
            raise ValueError(f'game {i + 1}: search count mismatch')
        if terminal != game['result'] or len(game['moves']) != game['plies']:
            raise ValueError(f'game {i + 1}: outcome or move count mismatch')
        if any(t.get('depth') != data['depth'] for t in game['thinks']):
            raise ValueError(f'game {i + 1}: reported depth mismatch')
        checks += bool(ref.board.is_check())
        searches += len(game['thinks'])
        winner = terminal['winner']
        outcomes['draw' if winner is None else 'gnu_win' if winner == game['gnu_side'] else 'gnu_loss'] += 1
        outcomes[terminal['reason']] += 1
    print(json.dumps({'games': len(data['games']), 'outcomes': outcomes,
                      'final_positions_in_check': checks, 'promotions': promotions,
                      'drops': drops, 'gnu_searches': searches,
                      'mean_plies': statistics.mean(g['plies'] for g in data['games']) if data['games'] else None},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
