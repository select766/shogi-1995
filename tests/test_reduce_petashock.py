"""Exercise both YBB reductions with a small, synthetic legal position graph."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import cshogi
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/reduce-petashock.py'
spec = importlib.util.spec_from_file_location('reduce_petashock', SCRIPT)
reducer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reducer)
HEADER = struct.Struct('<16sQQ')
TAIL = struct.Struct('<QHH')


def packed(board):
    result = np.empty(32, dtype=np.uint8)
    board.to_psfen(result)
    return result.tobytes()


def move16(usi):
    def square(s):
        return (int(s[0]) - 1) * 9 + ord(s[1]) - ord('a')
    if '*' in usi:
        return 0x4000 | (' PLNSBRG'.index(usi[0]) << 7) | square(usi[2:4])
    return ((square(usi[:2]) << 7) | square(usi[2:4]) |
            (0x8000 if usi.endswith('+') else 0))


def position(moves):
    board = cshogi.Board()
    for move in moves.split():
        board.push_usi(move)
    return packed(board)


class ReduceBookTest(unittest.TestCase):
    def test_move_encoding_for_drops_and_promotions(self):
        board = cshogi.Board('4k4/9/9/9/9/9/9/9/4K4 b P 1')
        drop = reducer.convert_move(board, move16('P*5e'))
        self.assertTrue(board.is_legal(drop))
        self.assertEqual(cshogi.move_to_usi(drop), 'P*5e')
        board.set_sfen('4k4/9/4P4/9/9/9/9/9/4K4 b - 1')
        promote = reducer.convert_move(board, move16('5c5b+'))
        self.assertTrue(board.is_legal(promote))
        self.assertEqual(cshogi.move_to_usi(promote), '5c5b+')

    def test_repertoire_and_legacy_filter(self):
        # The last node lies only behind the rejected white response to 7g7f.
        entries = [
            ('', [('7g7f', 100, 10), ('2g2f', 0, 10)], 1),
            ('7g7f', [('8c8d', 0, 10), ('3c3d', 50, 10)], 2),
            ('2g2f 3c3d', [('2f2e', 10, 10), ('7g7f', 0, 10)], 3),
            ('2g2f 8c8d', [('7g7f', 10, 10)], 3),
            ('7g7f 3c3d 2g2f', [('8c8d', 5, 10)], 4),
            ('7g7f 8c8d 2g2f', [('3c3d', 5, 10)], 4),
        ]
        records = sorted((position(path), moves, ply) for path, moves, ply in entries)
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source, out, old = (temp / name for name in ('source.ybb', 'out.ybb', 'old.ybb'))
            index, payload = bytearray(), bytearray()
            for key, moves, ply in records:
                index += key + TAIL.pack(len(payload), ply, len(moves))
                for move, score, depth in moves:
                    payload += struct.pack('<HhH', move16(move), score, depth)
            source.write_bytes(HEADER.pack(b'YANE-BINBOOK-V1\0', len(records), 1) + index + payload)
            subprocess.run([sys.executable, str(SCRIPT), '--input', str(source), '--output', str(out)], check=True)
            data = out.read_bytes()
            _, count, flags = HEADER.unpack_from(data)
            self.assertEqual((count, flags, len(data)), (5, 1, 32 + 5 * 50))
            result = {}
            for n in range(count):
                offset, _, number = TAIL.unpack_from(data, 32 + 44*n + 32)
                self.assertEqual(number, 1)
                result[data[32+44*n:64+44*n]] = struct.unpack_from('<H', data, 32 + 44*count + offset)[0]
            self.assertEqual(result[position('')], move16('2g2f'))
            self.assertEqual(result[position('7g7f')], move16('3c3d'))
            self.assertIn(position('2g2f 8c8d'), result)
            self.assertNotIn(position('7g7f 8c8d 2g2f'), result)
            subprocess.run([sys.executable, str(SCRIPT), '--input', str(source), '--output', str(old), '--max-ply', '2'], check=True)
            data = old.read_bytes()
            _, count, _ = HEADER.unpack_from(data)
            self.assertEqual(count, 2)
            self.assertEqual(len(data), 32 + 2*44 + 4*6)
            self.assertEqual([TAIL.unpack_from(data, 32 + 44*n + 32)[2] for n in range(count)], [2, 2])


if __name__ == '__main__':
    unittest.main()
