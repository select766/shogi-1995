#!/usr/bin/env python3
"""Reduce a private YBB to a one-move repertoire, or filter by recorded ply."""
import argparse
from collections import deque
import mmap
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'private/petashock/user_book1-19003763.7z'
OUTPUT = ROOT / 'private/petashock/reduced/user_book1.ybb'
MAGIC = b'YANE-BINBOOK-V1\0'
HEADER = struct.Struct('<16sQQ')
INDEX_TAIL = struct.Struct('<QHH')


def read_header(data):
    if len(data) < HEADER.size:
        raise ValueError('truncated YBB header')
    magic, count, flags = HEADER.unpack_from(data)
    if magic != MAGIC or flags & ~1 or 32 + count * 44 > len(data):
        raise ValueError('invalid YBB header')
    return count, flags


def index_entry(data, index, count, move_size):
    pos = 32 + index * 44
    offset, ply, number = INDEX_TAIL.unpack_from(data, pos + 32)
    if 32 + count * 44 + offset + number * move_size > len(data):
        raise ValueError(f'invalid move offset at index {index}')
    return offset, ply, number


def find_index(data, count, key):
    left, right = 0, count
    while left < right:
        mid = (left + right) // 2
        candidate = data[32 + mid * 44:64 + mid * 44]
        if candidate < key:
            left = mid + 1
        else:
            right = mid
    return left if left < count and data[32 + left * 44:64 + left * 44] == key else None


def convert_move(board, move):
    to = move & 127
    dest = str(to // 9 + 1) + chr(97 + to % 9)
    if move & 0x4000:
        piece = (move >> 7) & 127
        if not 1 <= piece <= 7:
            raise ValueError(f'invalid drop move: {move}')
        return board.move_from_usi(' PLNSBRG'[piece] + '*' + dest)
    origin = (move >> 7) & 127
    return board.move_from_usi(str(origin // 9 + 1) + chr(97 + origin % 9)
                               + dest + ('+' if move & 0x8000 else ''))


def repertoire(data, count, flags):
    # Imported only for the repertoire method; the ply filter uses the stdlib.
    try:
        import cshogi
        import numpy as np
    except ImportError as exc:
        raise RuntimeError('repertoire requires cshogi and numpy; install requirements-evaluation.txt') from exc

    size = 6 if flags & 1 else 4
    base = 32 + count * 44
    board = cshogi.Board()
    packed = np.empty(32, dtype=np.uint8)
    # Zero means unselected; otherwise it is the move's one-based index.
    selected = np.zeros(count, dtype=np.uint16)
    seen = np.zeros(count, dtype=np.bool_)

    def key():
        board.to_psfen(packed)
        return packed.tobytes()

    root = key()
    if find_index(data, count, root) is None:
        raise ValueError('initial position is missing from the book')
    for side in (0, 1):
        board.reset()
        starts = []
        if side == 0:
            starts.append(root)
        else:
            for move in list(board.legal_moves):
                board.push(move)
                starts.append(key())
                board.pop()
        queue = deque()
        missing = 0
        def add(position):
            nonlocal missing
            idx = find_index(data, count, position)
            if idx is None:
                missing += 1
            elif not seen[idx]:
                seen[idx] = True
                queue.append((position, idx))
        for position in starts:
            add(position)
        kept = 0
        started = time.monotonic()
        while queue:
            position, idx = queue.popleft()
            offset, _, number = index_entry(data, idx, count, size)
            if not number:
                continue
            board.set_psfen(np.frombuffer(position, dtype=np.uint8))
            choices = []
            for i in range(number):
                pos = base + offset + i * size
                move, value = struct.unpack_from('<Hh', data, pos)
                depth = struct.unpack_from('<H', data, pos + 4)[0] if flags & 1 else 0
                choices.append((move, value, depth, i))
            choices.sort(key=lambda item: (-item[1], -item[2], item[0]))
            if side == 0 and position == root:
                chosen = next((item for item in choices if cshogi.move_to_usi(convert_move(board, item[0])) == '2g2f'), None)
                if chosen is None:
                    raise ValueError('initial position has no 2g2f move')
            else:
                chosen = choices[0]
            move = convert_move(board, chosen[0])
            if not board.is_legal(move):
                raise ValueError(f'illegal book move at index {idx}: {chosen[0]}')
            selected[idx] = chosen[3] + 1
            kept += 1
            board.push(move)
            for reply in list(board.legal_moves):
                board.push(reply)
                add(key())
                board.pop()
            if kept % 100000 == 0:
                print(f'{"black" if side == 0 else "white"}: {kept} positions, {len(queue)} pending, '
                      f'{time.monotonic() - started:.0f}s', flush=True)
        print(f'{"black" if side == 0 else "white"}: {kept} positions; '
              f'{missing} missing lookups (including repetitions)', flush=True)
    return selected


def write_book(data, output, tempdir, max_ply=None):
    count, flags = read_header(data)
    size = 6 if flags & 1 else 4
    base = 32 + count * 44
    selected = repertoire(data, count, flags) if max_ply is None else None
    idxpath, movepath = tempdir / 'index', tempdir / 'moves'
    kept = offset = 0
    with idxpath.open('wb') as idx, movepath.open('wb') as moves:
        for n in range(count):
            pos = 32 + n * 44
            if selected is not None and not selected[n]:
                continue
            move_offset, ply, number = index_entry(data, n, count, size)
            if max_ply is not None and ply > max_ply:
                continue
            if selected is not None:
                move_offset += (int(selected[n]) - 1) * size
                number = 1
            idx.write(data[pos:pos + 32] + INDEX_TAIL.pack(offset, ply, number))
            moves.write(data[base + move_offset:base + move_offset + number * size])
            offset += number * size
            kept += 1
    # Write next to the destination so the final replacement is atomic.
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + '.', delete=False) as out:
        tmp = Path(out.name)
        try:
            out.write(HEADER.pack(MAGIC, kept, flags))
            for part in (idxpath, movepath):
                with part.open('rb') as inp:
                    while chunk := inp.read(1024 * 1024):
                        out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f'positions {kept}/{count}; bytes {output.stat().st_size}; '
          f'method {"repertoire" if max_ply is None else "max-ply " + str(max_ply)}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-ply', type=int, help='use the legacy filter: retain recorded ply <= this value')
    parser.add_argument('--input', type=Path, help='already extracted YBB (default: extract private archive)')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.max_ply is not None and not 0 <= args.max_ply <= 65535:
        parser.error('max-ply must be between 0 and 65535')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / '.local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.local', prefix='book-') as td:
        tempdir = Path(td)
        source = args.input
        if source is None:
            subprocess.run(['7z', 'x', '-y', '-o' + td, str(ARCHIVE)], check=True, stdout=subprocess.DEVNULL)
            source = tempdir / 'user_book1.ybb'
        if source.resolve() == args.output.resolve():
            raise ValueError('input and output must differ')
        with source.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            write_book(data, args.output, tempdir, args.max_ply)


if __name__ == '__main__':
    main()
