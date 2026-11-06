#!/usr/bin/env python3
"""Fetch only fixed setup assets, verifying hashes before use. No training data."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / '.local/downloads'
destination.mkdir(parents=True, exist_ok=True)
for asset in json.loads((ROOT / 'manifests/assets.json').read_text())['assets']:
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
