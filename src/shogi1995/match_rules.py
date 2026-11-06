"""Host referee rules for warm-history auxiliary games, separate from the USI bridge."""
from collections import Counter
import math
import cshogi


def position_key(board):
    return ' '.join(board.sfen().split()[:3])


class Referee:
    def __init__(self, sfen, initial_ms=180000, increment_ms=2000, max_plies=512, *, initial_by_color_ms=None):
        self.board = cshogi.Board(sfen)
        self.start_sfen = sfen
        self.moves = []
        self.remaining = list(initial_by_color_ms) if initial_by_color_ms is not None else [initial_ms, initial_ms]
        if len(self.remaining)!=2 or any(type(value) is not int or value<=0 for value in self.remaining):
            raise ValueError('two positive integer clocks required')
        self.increment = increment_ms
        self.max_plies = max_plies
        self.occurrences = Counter({position_key(self.board): 1})

    def position_command(self):
        return 'position sfen ' + self.start_sfen + (' moves ' + ' '.join(self.moves) if self.moves else '')

    def go_command(self):
        return f'go btime {self.remaining[0]} wtime {self.remaining[1]} binc {self.increment} winc {self.increment}'

    def terminal(self):
        if not any(self.board.legal_moves):
            return {'winner': 1 - self.board.turn, 'reason': 'no_legal_move'}
        if len(self.moves) >= self.max_plies:
            return {'winner': None, 'reason': 'max_plies'}
        return None

    def accept(self, move, host_ms):
        side = self.board.turn
        elapsed = math.ceil(host_ms)
        self.remaining[side] -= elapsed
        if self.remaining[side] < 0:
            return {'winner': 1 - side, 'reason': 'time_forfeit'}
        if move == 'resign':
            return {'winner': 1 - side, 'reason': 'resign'}
        if move == 'win':
            valid = self.board.is_nyugyoku(cshogi.LAW_27)
            return {'winner': side if valid else 1 - side, 'reason': 'declaration_win' if valid else 'illegal_declaration'}
        try:
            parsed = self.board.move_from_usi(move)
            valid = self.board.is_legal(parsed)
        except (ValueError, RuntimeError, OverflowError):
            valid = False
        if not valid:
            return {'winner': 1 - side, 'reason': 'illegal_move'}
        self.board.push(parsed); self.moves.append(move)
        # Fischer increment is earned after completing a move within the
        # existing remaining time. It cannot rescue an already expired clock.
        self.remaining[side] += self.increment
        key = position_key(self.board); self.occurrences[key] += 1
        if self.occurrences[key] >= 4:
            status = self.board.is_draw()
            if status == cshogi.REPETITION_WIN:
                return {'winner': self.board.turn, 'reason': 'perpetual_check'}
            if status == cshogi.REPETITION_LOSE:
                return {'winner': 1 - self.board.turn, 'reason': 'perpetual_check'}
            return {'winner': None, 'reason': 'fourfold_repetition'}
        return self.terminal()
