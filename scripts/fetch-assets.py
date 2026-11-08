#!/usr/bin/env python3
"""Fetch only fixed setup assets, verifying hashes before use. No training data."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-only', action='store_true', help='Skip compiler, libc sources and engine sources')
args = parser.parse_args()
runtime_names = {'86Box-v6.0.AppImage', '86box-roms.tar.gz', 'idenet.tgz',
                 'aaa_base.tgz', 'bash.tgz', 'ldso.tgz', 'shlibs.tgz', 'bin.tgz', 'sh_utils.tgz'}
destination = ROOT / '.local/downloads'
destination.mkdir(parents=True, exist_ok=True)
for asset in json.loads((ROOT / 'manifests/assets.json').read_text())['assets']:
    if args.runtime_only and asset['name'] not in runtime_names:
        continue
    path = destination / asset['name']
    def verified(p):
        return p.exists() and p.stat().st_size == asset['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == asset['sha256']
    if verified(path):
        print('verified', asset['name'])
        continue
    temp = path.with_suffix(path.suffix + '.part')
    print('fetching', asset['url'], flush=True)
    with urllib.request.urlopen(asset['url'], timeout=120) as response, temp.open('wb') as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    if not verified(temp):
        temp.unlink(missing_ok=True)
        raise RuntimeError('asset changed; investigate source before updating manifest: ' + asset['name'])
    temp.replace(path)
