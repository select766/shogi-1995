#!/usr/bin/env python3
"""Prepare GNU Shogi inputs from hash-pinned archives, without touching research assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Require verified local archives')
    args = parser.parse_args()
    downloads = HERE / 'downloads'
    downloads.mkdir(exist_ok=True)
    assets = json.loads((HERE / 'assets.json').read_text())['assets']
    for asset in assets:
        target = downloads / asset['name']
        def valid(path):
            return path.is_file() and path.stat().st_size == asset['bytes'] and sha(path) == asset['sha256']
        if not valid(target):
            cached = ROOT / '.local/downloads' / asset['name']
            if valid(cached):
                shutil.copyfile(cached, target)
            elif args.offline:
                raise RuntimeError('Missing verified archive: ' + str(target))
            else:
                part = target.with_suffix(target.suffix + '.part')
                with urllib.request.urlopen(asset['url'], timeout=60) as response, part.open('wb') as out:
                    shutil.copyfileobj(response, out)
                if not valid(part):
                    part.unlink()
                    raise RuntimeError('Archive hash/size mismatch: ' + asset['name'])
                part.replace(target)
        print('verified', asset['name'], flush=True)

    # Recreate only this comparator's generated directories. Never execute historical
    # package install scripts on the host: some contain absolute guest paths.
    for name in ('vendor', 'modern32', 'guest', 'kernel-source', 'boot-assets'):
        path = HERE / name
        if path.exists():
            shutil.rmtree(path)
        path.mkdir()
    for name in ('bin', 'results'):
        (HERE / name).mkdir(exist_ok=True)
    source = downloads / 'gnushogi-1.2p03.tar.gz'
    shutil.copyfile(source, HERE / 'vendor' / source.name)
    run('tar', '-xzf', source, '-C', HERE / 'vendor')
    source_dir = HERE / 'vendor/gnushogi-1.2p03'
    with (HERE / 'compatibility.patch').open() as patch:
        subprocess.run(['patch', '--batch', '--forward', '-p1'], cwd=source_dir, stdin=patch, check=True)
    shutil.copytree(source_dir, HERE / 'modern32/source')

    guest = HERE / 'guest'
    for name in ('aaa_base', 'bash', 'ldso', 'shlibs', 'bin', 'sh_utils', 'binutils', 'gmake', 'gcc270', 'libc'):
        run('tar', '-xzf', downloads / (name + '.tgz'), '-C', guest)
    run('tar', '-xzf', downloads / 'linux-1.2.13.tar.gz', '-C', HERE / 'kernel-source')
    include = HERE / 'kernel-source/linux/include'
    destination = guest / 'usr/src/linux/include'
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(include / 'linux', destination / 'linux')
    shutil.copytree(include / 'asm-i386', destination / 'asm')
    (destination / 'linux/version.h').write_text('#define UTS_RELEASE "1.2.13"\n#define LINUX_VERSION_CODE 66061\n')
    links = {
        'usr/include/linux': '../src/linux/include/linux',
        'usr/include/asm': '../src/linux/include/asm',
        'bin/sh': 'bash',
        'lib/ld-linux.so.1': 'ld-linux.so.1.7.3',
        'lib/libc.so.5': 'libc.so.5.0.9',
        'lib/libm.so.5': 'libm.so.5.0.0',
    }
    for name, target in links.items():
        path = guest / name
        if path.is_symlink() or path.exists():
            path.unlink()
        path.symlink_to(target)
    (guest / 'work/modern').mkdir(parents=True)
    (guest / 'proc').mkdir(exist_ok=True)
    shutil.copytree(source_dir, guest / 'work/old')
    run('tar', '-xzf', downloads / 'idenet.tgz', '-C', HERE / 'boot-assets')
    shutil.copyfile(HERE / 'boot-assets/vmlinuz', HERE / 'guest-vmlinuz')
    run('gcc', '-m32', '-march=pentium', '-Os', '-fno-pie', '-no-pie', '-fno-stack-protector',
        '-nostdlib', '-static', ROOT / 'src/compat/guest-init.c', '-o', guest / 'sbin/init')
    (HERE / 'results/preparation.json').write_text(json.dumps({
        'assets': assets,
        'compatibility_patch_sha256': sha(HERE / 'compatibility.patch'),
        'guest_init_source_sha256': sha(ROOT / 'src/compat/guest-init.c'),
        'host_gcc': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
        'kernel_header_version': '1.2.13',
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
