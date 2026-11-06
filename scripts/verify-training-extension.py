#!/usr/bin/env python3
"""Verify a deterministic original-PSV extension before qsearch preprocessing."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path, limit=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        remaining = limit
        while remaining is None or remaining > 0:
            data = stream.read(1048576 if remaining is None else min(1048576, remaining))
            if not data:
                if remaining:
                    raise ValueError('truncated prefix: ' + str(path))
                break
            h.update(data)
            if remaining is not None:
                remaining -= len(data)
    return h.hexdigest()


def verify(reference_path, candidate_path, expected_records):
    a = json.loads(reference_path.read_text())
    b = json.loads(candidate_path.read_text())
    if not a['complete'] or not b['complete']:
        raise ValueError('both extractions must be complete')
    for key in ('series', 'seed', 'move_codec', 'source', 'source_readme_sha256',
                'exclusions_sha256', 'block_size', 'validation_files',
                'training_file_count', 'extractor_sha256'):
        if a[key] != b[key]:
            raise ValueError('extraction identity changed: ' + key)
    if a['series'] != 'tanuki-original-blocks-v2':
        raise ValueError('expected approved original-PSV sampling series')
    for split in ('validation', 'train'):
        old_blocks = [x for x in a['blocks'] if x['split'] == split]
        new_blocks = [x for x in b['blocks'] if x['split'] == split]
        if new_blocks[:len(old_blocks)] != old_blocks:
            raise ValueError('source block prefix changed: ' + split)
        if split == 'validation' and new_blocks != old_blocks:
            raise ValueError('validation source blocks changed')
        for manifest in (a, b):
            entry = manifest['outputs'][split]
            path = Path(entry['file'])
            if path.stat().st_size != entry['records'] * 40 or digest(path) != entry['sha256']:
                raise ValueError('raw bytes differ from manifest: ' + str(path))
    av, bv = a['outputs']['validation'], b['outputs']['validation']
    if (av['records'], av['sha256']) != (bv['records'], bv['sha256']):
        raise ValueError('held-out validation changed')
    at, bt = a['outputs']['train'], b['outputs']['train']
    if not 0 < at['records'] < bt['records'] == expected_records:
        raise ValueError('unexpected training extension size')
    prefix_hash = digest(bt['file'], at['records'] * 40)
    if prefix_hash != at['sha256']:
        raise ValueError('extended training bytes do not preserve the original prefix')
    return {'passed': True, 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
            'reference_manifest_sha256': digest(reference_path),
            'candidate_manifest_sha256': digest(candidate_path),
            'reference_records': at['records'], 'extended_records': bt['records'],
            'original_training_prefix_sha256': prefix_hash,
            'extended_training_sha256': bt['sha256'],
            'unchanged_validation_records': av['records'],
            'unchanged_validation_sha256': av['sha256'],
            'source_block_prefix_preserved': True,
            'scope': 'raw original-only extraction identity and byte integrity; qsearch/shuffle and leaf exclusions are separate required stages'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-manifest', required=True, type=Path)
    parser.add_argument('--candidate-manifest', required=True, type=Path)
    parser.add_argument('--expected-train-records', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('output exists; preserve previous verification')
    result = verify(args.reference_manifest, args.candidate_manifest, args.expected_train_records)
    result['verifier_sha256'] = digest(Path(__file__))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
