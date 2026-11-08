#!/usr/bin/env python3
"""Assemble a fresh ShogiHome image from release binaries, with an optional local book."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('aaa_base', 'bash', 'ldso', 'shlibs', 'bin', 'sh_utils')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def guest_digest(image, name):
    with subprocess.Popen(['debugfs', '-R', 'cat ' + name, str(image)],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        value = hashlib.sha256()
        while chunk := proc.stdout.read(1024 * 1024):
            value.update(chunk)
        if proc.wait():
            raise ValueError('cannot read image file: ' + name)
    return value.hexdigest()


def assemble(assets, output, book, no_book=False):
    selection = json.loads((ROOT / 'config/release/denryu-halfkp-v1.json').read_text())
    release = json.loads((assets / 'release-manifest.json').read_text())
    if release['id'] != selection['id'] or release['private_book_included'] is not False:
        raise ValueError('unexpected release')
    for name, expected in selection['files'].items():
        entry = release['files'][name]
        path = assets / name
        if entry['sha256'] != expected or digest(path) != expected or path.stat().st_size != entry['bytes']:
            raise ValueError('release payload differs: ' + name)
    # Start from empty staging; never inherit a previous model or private book.
    output = output.resolve()
    if ROOT / '.local' not in output.parents:
        raise ValueError('images must be inside ignored .local/ (may contain a private book)')
    if output.exists():
        raise ValueError('output exists; choose a new directory to preserve existing images')
    asset_specs = {a['name']: a for a in json.loads((ROOT / 'manifests/assets.json').read_text())['assets']}
    for package in PACKAGES:
        name = package + '.tgz'
        if digest(ROOT / '.local/downloads' / name) != asset_specs[name]['sha256']:
            raise ValueError('runtime package hash differs: ' + name)
    for required in ('.local/images/boot.img', '.local/vmlinuz', '.local/86box/app/AppRun', '.local/86box/roms-master'):
        if not (ROOT / required).exists():
            raise ValueError('run bash scripts/setup-runtime.sh first: ' + required)
    include_book = not no_book and book.is_file()
    if include_book:
        with book.open('rb') as stream:
            if stream.read(16).rstrip(b'\0') != b'YANE-BINBOOK-V1':
                raise ValueError('expected a reduced YBB book')
        if book.stat().st_size > 300 * 1024 * 1024:
            raise ValueError('book too large for 504 MiB image; reduce with --max-ply 20')
    output.mkdir(parents=True)
    stage = output / 'root'
    stage.mkdir()
    for package in PACKAGES:
        subprocess.run(['tar', '-xzf', str(ROOT / '.local/downloads' / (package + '.tgz')),
                        '-C', str(stage)], check=True)
    for name in ('dev', 'proc', 'tmp', 'sbin', 'bin', 'lib', 'eval'):
        (stage / name).mkdir(exist_ok=True)
    for name, target in [('bin/sh', 'bash'), ('lib/ld-linux.so.1', 'ld-linux.so.1.7.3'), ('lib/libc.so.5', 'libc.so.5.0.9')]:
        path = stage / name
        path.unlink(missing_ok=True)
        path.symlink_to(target)
    guest_files = {'/shogi': 'shogi-pentium1995', '/eval/model.bin': 'halfkp-w8-d42.bin',
                   '/sbin/init': 'guest-init-pentium1995'}
    for target, name in guest_files.items():
        path = stage / target.lstrip('/')
        shutil.copyfile(assets / name, path)
        path.chmod(0o644 if target.endswith('.bin') else 0o755)
    options = {'EvalFile': '/eval/model.bin', 'Threads': '1', 'USI_Hash': '2',
               'MaxMovesToDraw': '512', 'EnteringKingRule': 'CSARule27', 'USI_Ponder': 'false',
               'NetworkDelay': '120', 'NetworkDelay2': '1120',
               'USI_OwnBook': 'true' if include_book else 'false',
               'BookFile': 'user_book1.db' if include_book else 'no_book',
               'BookDir': '/book', 'BookOnTheFly': 'true', 'IgnoreBookPly': 'true',
               'FlippedBook': 'true', 'BookMoves': '999', 'BookEvalDiff': '0',
               'BookDepthLimit': '0', 'BookPvMoves': '1'}
    book_hash = None
    if include_book:
        (stage / 'book').mkdir()
        shutil.copyfile(book, stage / 'book/user_book1.ybb')
        book_hash = digest(stage / 'book/user_book1.ybb')
    # engine_options.txt fixes settings against GUI changes. Pin only model identity.
    # Book and network delays are initial USI defaults, freely overridable by ShogiHome.
    config = 'EvalFile /eval/model.bin\n'
    (stage / 'engine_options.txt').write_text(config)
    (output / 'engine-defaults.json').write_text(json.dumps(options, indent=2) + '\n')
    image = output / 'root.ext2'
    with image.open('xb') as stream:
        stream.truncate(504 * 1024 * 1024)
    with (output / 'image-build.log').open('x') as log:
        subprocess.run(['mke2fs', '-q', '-F', '-t', 'ext2', '-r', '0', '-O', 'none',
                        '-I', '128', '-b', '1024', '-N', '4096', '-d', str(stage), str(image)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['debugfs', '-w', '-f', '/dev/stdin', str(image)], text=True,
                       input='cd /dev\nmknod ttyS0 c 4 64\nmknod console c 4 0\nmknod null c 1 3\nmknod zero c 1 5\nmknod tty c 5 0\n',
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    for target, name in guest_files.items():
        if guest_digest(image, target) != selection['files'][name]:
            raise ValueError('image payload verification failed: ' + target)
    if guest_digest(image, '/engine_options.txt') != hashlib.sha256(config.encode()).hexdigest():
        raise ValueError('image options verification failed')
    if include_book and guest_digest(image, '/book/user_book1.ybb') != book_hash:
        raise ValueError('image book verification failed')
    # Resolve repository relative to launcher location, independent of ShogiHome cwd.
    import os
    relative_root = os.path.relpath(ROOT, output)
    launcher = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                'profile_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
                'repo_dir="$(cd -- "$profile_dir"/' + shlex.quote(relative_root) + ' && pwd)"\n'
                'exec "$repo_dir/run-shogi-1995.sh" --image "$profile_dir/root.ext2" '
                '--engine-defaults "$profile_dir/engine-defaults.json" "$@"\n')
    (output / 'run.sh').write_text(launcher)
    (output / 'run.sh').chmod(0o755)
    report = {'id': selection['id'], 'complete': True, 'assembled_at_utc': datetime.now(timezone.utc).isoformat(),
              'release_manifest_sha256': digest(assets / 'release-manifest.json'),
              'image_sha256': digest(image), 'payload_sha256': selection['files'],
              'private_book_included': include_book, 'private_book_sha256': book_hash,
              'redistributable_image': False if include_book else None,
              'configured_guest_options': options, 'selection': selection['selection'],
              'command': [str(output / 'run.sh')],
              'notice': 'Local image only; upload only the book-free release-assets directory.'}
    (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'launcher': str(output / 'run.sh'), 'book_included': include_book}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path, help='Directory containing downloaded release attachments')
    parser.add_argument('--output', type=Path, default=ROOT / '.local/shogihome/denryu-halfkp-v1')
    parser.add_argument('--book', type=Path, default=ROOT / 'private/petashock/reduced/user_book1.ybb')
    parser.add_argument('--no-book', action='store_true', help='Build without a book even if a local book exists')
    args = parser.parse_args()
    assemble(args.assets.resolve(), args.output, args.book, args.no_book)
