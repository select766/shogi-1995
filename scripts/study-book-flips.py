#!/usr/bin/env python3
"""Study a local reduced book; write only aggregate results to ignored .local/."""
import collections
import ctypes
import hashlib
import json
import mmap
from pathlib import Path
import struct
import time

import cshogi
import numpy as np

ROOT = Path.cwd()
SOURCE = ROOT / 'private/petashock/reduced/user_book1.ybb'
WORK = ROOT / '.local/book-work'
MIRROR_DTYPE = np.dtype([('key', 'S32'), ('index', '<u4')])
HIGH_BIT = 1 << 63


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with SOURCE.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    book_hash = digest.hexdigest()
    mirror = WORK / ('flip-keys-' + book_hash + '.bin')
    with SOURCE.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        magic, count, flags = struct.unpack_from('<16sQQ', data)
        if magic != b'YANE-BINBOOK-V1\0' or flags & ~1 or count >= 2**32:
            raise ValueError('invalid or unsupported YBB')
        size = 6 if flags & 1 else 4
        base = 32 + 44 * count
        board = cshogi.Board()
        source_board = cshogi.Board()
        packed = np.empty(32, dtype=np.uint8)
        started = time.monotonic()
        if not mirror.exists():
            keys = np.empty(count, dtype=MIRROR_DTYPE)
            for i in range(count):
                board.set_psfen(np.frombuffer(data, dtype=np.uint8, count=32, offset=32 + 44 * i))
                board.set_sfen(cshogi.rotate_sfen(board.sfen()))
                board.to_psfen(packed)
                keys[i] = (packed.tobytes(), i)
                if i and i % 500000 == 0:
                    print('mirror keys', i, round(time.monotonic() - started), flush=True)
            keys.sort(order='key')
            temporary = mirror.with_suffix('.tmp')
            try:
                keys.tofile(temporary)
                temporary.replace(mirror)
            finally:
                temporary.unlink(missing_ok=True)
            del keys
        if mirror.stat().st_size != count * MIRROR_DTYPE.itemsize:
            raise ValueError('invalid cached mirror index')

        lib = ctypes.CDLL(str(WORK / 'flip_index.so'))
        lib.init.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.lookup.argtypes = [ctypes.c_char_p]
        lib.lookup.restype = ctypes.c_uint64
        if lib.init(str(SOURCE).encode(), str(mirror).encode()):
            raise ValueError('cannot initialize book lookup')
        # A direct hit for a mirrored key means both members of that pair are saved.
        mirrored = np.memmap(mirror, dtype=MIRROR_DTYPE, mode='r')
        paired = sum(1 for row in mirrored
                     if (result := lib.lookup(row.tobytes()[:32])) and not result >> 63)
        del mirrored
        if paired % 2:
            raise ValueError('unexpected reflected pair count')
        print('stored reflected pairs', paired // 2, flush=True)
        results = {}
        for side in (0, 1):
            board.reset()
            def key():
                board.to_psfen(packed)
                return packed.tobytes()
            starts = []
            if side == 0:
                starts.append(key())
            else:
                for move in list(board.legal_moves):
                    board.push(move)
                    starts.append(key())
                    board.pop()
            visited = np.zeros(count * 2, dtype=np.bool_)
            queue = collections.deque()
            stats = collections.Counter()
            started = time.monotonic()

            def add(position):
                result = lib.lookup(position)
                if not result:
                    stats['missing_attempts'] += 1
                    return
                flipped = result >> 63
                index = (result & (HIGH_BIT - 1)) - 1
                slot = index + flipped * count
                if not visited[slot]:
                    visited[slot] = True
                    queue.append((position, index, flipped))
            for position in starts:
                add(position)
            while queue:
                position, index, flipped = queue.popleft()
                board.set_psfen(np.frombuffer(position, dtype=np.uint8))
                offset, _, number = struct.unpack_from('<QHH', data, 32 + index * 44 + 32)
                if number != 1 or base + offset + size > len(data):
                    raise ValueError('expected one valid move per position')
                move = struct.unpack_from('<H', data, base + offset)[0]
                to = move & 127
                dest = str(to // 9 + 1) + chr(97 + to % 9)
                if flipped:
                    source_board.set_psfen(np.frombuffer(data, dtype=np.uint8, count=32,
                                                        offset=32 + index * 44))
                    move_board = source_board
                else:
                    move_board = board
                if move & 0x4000:
                    usi = ' PLNSBRG'[(move >> 7) & 127] + '*' + dest
                else:
                    origin = (move >> 7) & 127
                    usi = str(origin // 9 + 1) + chr(97 + origin % 9) + dest
                    if move & 0x8000:
                        usi += '+'
                actual = move_board.move_from_usi(usi)
                if flipped:
                    actual = cshogi.move_rotate(actual)
                if not board.is_legal(actual):
                    raise ValueError(f'illegal move at {index}, flipped={flipped}')
                stats['flipped' if flipped else 'direct'] += 1
                board.push(actual)
                for reply in list(board.legal_moves):
                    board.push(reply)
                    add(key())
                    board.pop()
                done = stats['direct'] + stats['flipped']
                if done % 100000 == 0:
                    print('side', side, 'direct', stats['direct'], 'flipped', stats['flipped'],
                          'pending', len(queue), 'sec', round(time.monotonic() - started), flush=True)
            results['black' if side == 0 else 'white'] = dict(stats)
            print('RESULT', side, dict(stats), flush=True)
        report = {'book_sha256': book_hash, 'stored_reflected_pairs': paired // 2,
                  'method': 'all legal opponent moves; stop on no book; ignore repetition; 2g2f initial',
                  'results': results}
        (WORK / 'flip-full-study.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
