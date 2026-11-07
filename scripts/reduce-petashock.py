#!/usr/bin/env python3
"""Filter the private YBB by recorded ply; preserve sorted keys and move records."""
import argparse
import mmap
import os
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'private/petashock/user_book1-19003763.7z'
OUTPUT = ROOT / 'private/petashock/reduced/user_book1.ybb'
MAGIC = b'YANE-BINBOOK-V1\0'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-ply', type=int, required=True, help='maximum recorded ply to retain')
    p.add_argument('--input', type=Path, help='already extracted YBB (default: extract private archive)')
    p.add_argument('--output', type=Path, default=OUTPUT)
    a = p.parse_args()
    if not 0 <= a.max_ply <= 65535:
        p.error('max-ply must be between 0 and 65535')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / '.local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.local', prefix='book-') as td:
        source = a.input
        if source is None:
            subprocess.run(['7z', 'x', '-y', '-o' + td, str(ARCHIVE)], check=True, stdout=subprocess.DEVNULL)
            source = Path(td) / 'user_book1.ybb'
        if source.resolve() == a.output.resolve():
            raise ValueError('input and output must differ')
        with source.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
            magic, count, flags = struct.unpack_from('<16sQQ', data)
            if magic != MAGIC or flags & ~1 or 32 + count * 44 > len(data):
                raise ValueError('invalid YBB header')
            size = 6 if flags & 1 else 4
            moves_base = 32 + count * 44
            idxpath, movepath = Path(td) / 'index', Path(td) / 'moves'
            kept = offset = 0
            with idxpath.open('wb') as idx, movepath.open('wb') as moves:
                for n in range(count):
                    pos = 32 + n * 44
                    move_offset, ply, number = struct.unpack_from('<QHH', data, pos + 32)
                    end = moves_base + move_offset + number * size
                    if end > len(data):
                        raise ValueError('invalid move offset at index %d' % n)
                    if ply <= a.max_ply:
                        idx.write(data[pos:pos + 32] + struct.pack('<QHH', offset, ply, number))
                        moves.write(data[moves_base + move_offset:end])
                        offset += number * size
                        kept += 1
            tmp = a.output.with_name(a.output.name + '.tmp')
            try:
                with tmp.open('wb') as out:
                    out.write(struct.pack('<16sQQ', magic, kept, flags))
                    for part in (idxpath, movepath):
                        with part.open('rb') as inp:
                            while chunk := inp.read(1024 * 1024):
                                out.write(chunk)
                os.replace(tmp, a.output)
            finally:
                tmp.unlink(missing_ok=True)
            print(f'positions {kept}/{count}; bytes {a.output.stat().st_size}; max ply {a.max_ply}')

if __name__ == '__main__':
    main()
