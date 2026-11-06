#!/usr/bin/env python3
"""Alternate immutable engine variants in fixed blocks; resume only verified blocks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.statistics import summary


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(parts, sample_ids, key):
    combined = dict(parts[0])
    combined['sample_ids'] = sample_ids
    combined['details'] = [row for part in parts for row in part['details']]
    combined['complete'] = len(combined['details']) == len(sample_ids)
    combined['elapsed_seconds'] = sum(part['elapsed_seconds'] for part in parts)
    if parts[-1].get('finished_at_utc'):
        combined['finished_at_utc'] = parts[-1]['finished_at_utc']
    combined['blocks'] = [f'{i:03d}-{key}.json' for i in range(len(parts))]
    # Each block launches its own VM. Preserve each start/end pair instead of
    # accidentally presenting the first block's end as the final observation.
    combined.pop('guest_memory_end', None)
    if 'guest_memory_end' in parts[-1]:
        combined['guest_memory_end'] = parts[-1]['guest_memory_end']
    if any('guest_memory' in part or 'guest_memory_end' in part for part in parts):
        combined['guest_memory_scope'] = 'independent VM per block; inspect the paired observations below'
        combined['guest_memory_blocks'] = [
            {'block': name, 'start': part.get('guest_memory'), 'end': part.get('guest_memory_end')}
            for name, part in zip(combined['blocks'], parts)
        ]
    combined.update(summary(combined['details'], len(sample_ids)))
    return combined


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', required=True, type=Path, help='immutable candidate manifest with command and engine_sha256')
    p.add_argument('--candidate', required=True, type=Path)
    p.add_argument('--dataset', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--block-size', type=int, default=256)
    p.add_argument('--milliseconds', type=int, default=2000)
    args = p.parse_args()
    if args.block_size <= 0 or args.milliseconds <= 0:
        p.error('block size and time must be positive')
    variants = {key: json.loads(path.read_text()) for key, path in (('baseline', args.baseline), ('candidate', args.candidate))}
    manifest_paths={'baseline':args.baseline.resolve(),'candidate':args.candidate.resolve()}
    records = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    if not records:
        raise ValueError('empty dataset')
    args.output.mkdir(parents=True, exist_ok=True)
    identity = {'dataset_sha256': digest(args.dataset), 'sample_ids': [r['id'] for r in records],
                'baseline_manifest_sha256': digest(args.baseline), 'candidate_manifest_sha256': digest(args.candidate),
                'block_size': args.block_size, 'milliseconds': args.milliseconds}
    identity_path = args.output / 'identity.json'
    if identity_path.exists():
        if json.loads(identity_path.read_text()) != identity:
            raise ValueError('resume identity differs')
    else:
        if any(args.output.iterdir()):
            raise ValueError('output is not an existing pair run or an empty directory')
        identity_path.write_text(json.dumps(identity, indent=2) + '\n')
    chunks = {'baseline': [], 'candidate': []}
    for block, start in enumerate(range(0, len(records), args.block_size)):
        count = min(args.block_size, len(records) - start)
        order = ('baseline', 'candidate') if block % 2 == 0 else ('candidate', 'baseline')
        for key in order:
            variant = variants[key]
            output = args.output / f'{block:03d}-{key}.json'
            if not output.exists():
                command = [sys.executable, str(ROOT / 'scripts/evaluate-accuracy.py'),
                           '--dataset', str(args.dataset.resolve()), '--output', str(output.resolve()),
                           '--engine-command', json.dumps(variant['command']),
                           '--engine-id', variant['id'], '--engine-sha256', variant['engine_sha256'],
                           '--engine-manifest',str(manifest_paths[key]),
                           '--engine-options', json.dumps(variant.get('engine_options', {})),
                           '--milliseconds', str(args.milliseconds), '--offset', str(start), '--limit', str(count)]
                if variant.get('guest_diagnostics'):
                    command.append('--guest-diagnostics')
                if variant.get('search_diagnostics'):
                    command.append('--search-diagnostics')
                with output.with_suffix('.console.log').open('w') as log:
                    subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
            result = json.loads(output.read_text())
            expected_ids = [r['id'] for r in records[start:start + count]]
            if not result['complete']:
                raise ValueError(f'incomplete block must be investigated, not overwritten: {output}')
            if (result['dataset_sha256'] != identity['dataset_sha256'] or result['sample_ids'] != expected_ids
                    or result['engine_sha256'] != variant['engine_sha256'] or result['engine_id'] != variant['id']
                    or result['engine_command'] != variant['command'] or result['model_options'] != variant.get('engine_options', {})
                    or result['milliseconds'] != args.milliseconds or result['nodes'] is not None):
                raise ValueError(f'block identity mismatch: {output}')
            for manifest_key, result_key in (('image_sha256','guest_image_sha256'),('model_sha256','guest_model_sha256')):
                if manifest_key in variant and result.get(result_key)!=variant[manifest_key]:
                    raise ValueError(f'block artifact differs: {output}: {manifest_key}')
            chunks[key].append(result)
        for key in ('baseline', 'candidate'):
            combined = aggregate(chunks[key], identity['sample_ids'], key)
            target = args.output / (key + '.json')
            temp = target.with_suffix('.partial'); temp.write_text(json.dumps(combined, indent=2) + '\n'); temp.replace(target)
            if combined['complete']:
                subprocess.run([sys.executable,str(ROOT/'scripts/update-measurements.py'),'--result',str(target.resolve())],cwd=ROOT,check=True)
        print(f'completed paired block {block + 1}: {start + count}/{len(records)}', flush=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/compare-accuracy.py'),
                    str((args.output / 'baseline.json').resolve()), str((args.output / 'candidate.json').resolve()),
                    '--output', str((args.output / 'comparison.json').resolve())], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
