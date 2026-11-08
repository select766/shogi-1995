#!/usr/bin/env python3
"""Collect the measured engine and model into ignored, book-free release assets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/release-assets/denryu-halfkp-v1')
    args = parser.parse_args()
    out = args.output.resolve()
    if ROOT / '.local' not in out.parents:
        raise ValueError('release assets must be inside ignored .local/')
    selection = json.loads((ROOT / 'config/release/denryu-halfkp-v1.json').read_text())
    candidate = json.loads((ROOT / selection['candidate_manifest']).read_text())
    image = Path(candidate['command'][2])
    if digest(image) != candidate['image_sha256']:
        raise ValueError('frozen candidate image changed')
    # Read only these public files, never copy a root image or a staging tree.
    payloads = {'shogi-pentium1995': '/shogi', 'halfkp-w8-d42.bin': '/eval/model.bin',
                'guest-init-pentium1995': '/sbin/init'}
    blobs = {}
    for name, guest in payloads.items():
        data = subprocess.check_output(['debugfs', '-R', 'cat ' + guest, str(image)], stderr=subprocess.DEVNULL)
        if hashlib.sha256(data).hexdigest() != selection['files'][name]:
            raise ValueError('frozen payload differs: ' + name)
        blobs[name] = data
    out.mkdir(parents=True, exist_ok=False)
    for name, data in blobs.items():
        (out / name).write_bytes(data)
        (out / name).chmod(0o644 if name.endswith('.bin') else 0o755)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    # Exact engine source revision, including its build scripts and dependency hashes.
    with (out / 'shogi-1995-engine-source.tar.gz').open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', '--prefix=shogi-1995-engine-source/',
                        selection['engine_source_commit'], 'vendor', 'src', 'scripts', 'config', 'manifests'],
                       cwd=ROOT, stdout=stream, check=True)
    (out / 'COPYING.YaneuraOu').write_bytes((ROOT / 'vendor/YaneuraOu/LICENSE').read_bytes())
    (out / 'README.txt').write_text(
        'shogi-1995 denryu-halfkp-v1\n'
        'Measured HalfKP(Friend) width 8, two weight layers, material residual, D42; scalar Pentium runtime.\n'
        'No opening book or guest disk image is included. Do not upload private books or book-containing images.\n'
        'The model format is project-specific, not an arbitrary upstream NNUE file.\n'
        'Engine license: COPYING.YaneuraOu; corresponding build sources: shogi-1995-engine-source.tar.gz.\n'
        'Model training provenance: manifests/halfkp-model-frozen-20261107-1000.json in the repository.\n'
        'Assembly and ShogiHome setup: docs/shogihome-release.md in the release checkout.\n'
        'Run: python3 scripts/assemble-shogihome.py --assets <download-directory>\n')
    manifest = {'id': selection['id'], 'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
                'packaging_commit': revision, 'packaging_worktree_dirty': bool(subprocess.check_output(
                    ['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
                'engine_source_commit': selection['engine_source_commit'],
                'selection': selection['selection'], 'private_book_included': False,
                'runtime_changes_since_measurement': selection.get('runtime_changes_since_measurement'),
                'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                          for p in sorted(out.iterdir())}}
    (out / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(''.join(digest(p) + '  ' + p.name + '\n'
                                          for p in sorted(out.iterdir()) if p.name != 'SHA256SUMS'))
    print(out)


if __name__ == '__main__':
    main()
