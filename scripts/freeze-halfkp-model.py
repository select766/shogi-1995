#!/usr/bin/env python3
"""Freeze one qualified model from complete ordinary-time development evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.statistics import summary


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def utc():
    return datetime.now(timezone.utc)


def validate_report(report, profile, expected_ids, plan):
    if not report['complete'] or report['measured'] != len(expected_ids) or report['total'] != len(expected_ids):
        raise ValueError('incomplete measurement')
    expected = {
        'engine_id': profile['id'], 'engine_sha256': profile['engine_sha256'],
        'guest_model_sha256': profile['model_sha256'], 'guest_image_sha256': profile['image_sha256'],
        'source_commit': profile['source_commit'], 'source_tree_sha256': profile['source_tree_sha256'],
        'dataset_sha256': plan['dataset_sha256'], 'backend': '86box', 'mode': 'fixed_byoyomi',
        'milliseconds': 2000, 'nodes': None, 'sample_ids': expected_ids,
        'engine_command': profile['command'], 'model_options': profile.get('engine_options', {}),
        'errors': 0, 'illegal_moves': 0, 'time_overruns': 0,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError('report identity differs: ' + key)
    if report.get('options') != plan['options']:
        raise ValueError('ordinary-time options differ')
    if report.get('environment', {}).get('signature') != plan['environment_signature']:
        raise ValueError('environment differs')
    if [row['id'] for row in report['details']] != expected_ids:
        raise ValueError('detail IDs/order differ')
    computed = summary(report['details'], len(expected_ids))
    if any(report.get(key) != value for key, value in computed.items()):
        raise ValueError('summary differs from details')


def collect(entry, plan, sample_ids):
    profile_path = ROOT / entry['profile']
    training_path = ROOT / entry['training']
    if sha(profile_path) != entry['profile_sha256'] or sha(training_path) != entry['training_sha256']:
        raise ValueError('frozen candidate/training manifest differs')
    profile, training = read(profile_path), read(training_path)
    if not training['complete'] or not training['converged'] or training['model_sha256'] != profile['model_sha256']:
        raise ValueError('qualified converged model required')
    if 'result' in entry:
        result_path = ROOT / entry['result']
        if sha(result_path) != entry['result_sha256']:
            raise ValueError('archived result differs')
        report = read(result_path)
        evidence = {'path': str(result_path.relative_to(ROOT)), 'sha256': sha(result_path)}
        comparison_scope = 'completed historical full-development run'
    else:
        directory = ROOT / entry['blocks']
        identity = read(directory / 'identity.json')
        if (identity['dataset_sha256'] != plan['dataset_sha256'] or identity['sample_ids'] != sample_ids
                or identity['candidate_manifest_sha256'] != entry['profile_sha256']
                or identity['block_size'] != 256 or identity['milliseconds'] != 2000):
            raise ValueError('candidate block-run identity differs')
        parts, evidence = [], []
        for index, start in enumerate(range(0, len(sample_ids), 256)):
            path = directory / f'{index:03d}-candidate.json'
            if not path.exists() or not read(path).get('complete'):
                return None, 'candidate has not completed all 1024 positions'
            part = read(path)
            validate_report(part, profile, sample_ids[start:start + 256], plan)
            parts.append(part)
            evidence.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        aggregate = runpy.run_path(str(ROOT / 'scripts/evaluate-pair.py'))['aggregate']
        report = aggregate(parts, sample_ids, 'candidate')
        comparison_scope = 'candidate-only full1024 from four complete blocks; paired control may remain incomplete; no full paired CI claimed'
    validate_report(report, profile, sample_ids, plan)
    if datetime.fromisoformat(report['finished_at_utc']) > utc():
        raise ValueError('measurement timestamp is in the future')
    return {
        'id': entry['id'], 'profile': entry['profile'], 'profile_sha256': entry['profile_sha256'],
        'training': entry['training'], 'training_sha256': entry['training_sha256'],
        'model_sha256': profile['model_sha256'], 'width': training['width'], 'hidden': training['hidden'],
        'weight_layers': training['weight_layers'], 'model_bytes': training['model_bytes'],
        'matches': report['matches'], 'positions': 1024, 'accuracy': report['accuracy'],
        'wilson_95': report['wilson_95'], 'finished_at_utc': report['finished_at_utc'],
        'evidence': evidence, 'comparison_scope': comparison_scope, 'priority': entry['priority'],
    }, None


def choose(plan):
    dataset = Path(plan['dataset'])
    if sha(dataset) != plan['dataset_sha256']:
        raise ValueError('development dataset differs')
    sample_ids = [json.loads(line)['id'] for line in dataset.read_text().splitlines() if line.strip()]
    if len(sample_ids) != 1024 or len(set(sample_ids)) != 1024:
        raise ValueError('exactly1024 unique development positions required')
    eligible, excluded = [], []
    for entry in plan['candidates']:
        candidate, reason = collect(entry, plan, sample_ids)
        if candidate is None:
            excluded.append({'id': entry['id'], 'reason': reason})
        else:
            eligible.append(candidate)
    if not eligible:
        raise ValueError('no complete qualified model')
    eligible.sort(key=lambda row: (-row['matches'], row['model_bytes'], row['weight_layers'], row['priority']))
    return eligible, excluded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    plan = read(args.plan)
    if sha(Path(__file__)) != plan['selector_sha256']:
        raise ValueError('selector source differs')
    if args.dry_run:
        eligible, excluded = choose(plan)
        print(json.dumps({'dry_run': True, 'eligible': eligible, 'excluded': excluded}, indent=2))
        return
    receipt_path = ROOT / plan['receipt']
    receipt = {'status': 'waiting', 'execute_at_utc': plan['execute_at_utc'],
               'plan_sha256': sha(args.plan), 'selector_sha256': sha(Path(__file__))}
    with receipt_path.open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    try:
        execute_at = datetime.fromisoformat(plan['execute_at_utc'])
        while utc() < execute_at:
            time.sleep(min(10, max(.01, (execute_at - utc()).total_seconds())))
        if utc() >= datetime.fromisoformat(plan['deadline_utc']):
            raise RuntimeError('model-freeze deadline missed; do not backdate a freeze')
        eligible, excluded = choose(plan)
        selected = eligible[0]
        profile = read(ROOT / selected['profile'])
        image = Path(profile['command'][profile['command'].index('--image') + 1])
        model_path = image.parent / 'model.bin'
        if sha(model_path) != selected['model_sha256']:
            raise ValueError('actual model bytes differ')
        output = ROOT / plan['output']
        if output.exists():
            raise ValueError('preserve previous model-freeze record')
        frozen_path = ROOT / plan['frozen_model']
        frozen_path.parent.mkdir(parents=True, exist_ok=False)
        with frozen_path.open('xb') as stream:
            stream.write(model_path.read_bytes())
        if sha(frozen_path) != selected['model_sha256']:
            raise ValueError('frozen model copy differs')
        finished = utc()
        if finished >= datetime.fromisoformat(plan['deadline_utc']):
            raise RuntimeError('freeze finished after deadline; preserve evidence without claiming success')
        record = {'complete': True, 'frozen_at_utc': finished.isoformat(), 'deadline_utc': plan['deadline_utc'],
                  'plan_sha256': sha(args.plan), 'selector_sha256': sha(Path(__file__)),
                  'selected': selected, 'frozen_model': plan['frozen_model'],
                  'ranked_eligible': eligible, 'excluded': excluded, 'heldout_test_used': False,
                  'selection_rule': plan['selection_rule'],
                  'uncertainty': 'Development point ranking for a deadline freeze; overlapping intervals are uncertain, repeated controls are not pooled, no incremental improvement is inferred from ranking.',
                  'next_phase': 'Keep exact geometry/model bytes fixed; runtime/arithmetic/search exploration until06:00UTC. Reference runtime is a starting point, not yet final.'}
        with output.open('x') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        receipt.update(status='model_frozen', frozen_at_utc=finished.isoformat(), output=plan['output'],
                       output_sha256=sha(output), model_sha256=selected['model_sha256'])
        print(json.dumps(record, ensure_ascii=False, indent=2))
    except BaseException as error:
        receipt.update(status='error', error=repr(error))
        raise
    finally:
        receipt['updated_at_utc'] = utc().isoformat()
        temporary = receipt_path.with_suffix('.partial')
        temporary.write_text(json.dumps(receipt, indent=2) + '\n')
        temporary.replace(receipt_path)


if __name__ == '__main__':
    main()
