#!/usr/bin/env python3
"""Freeze a runtime from complete paired development trials, never heldout data."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.statistics import paired

validate_report = runpy.run_path(str(ROOT / 'scripts/freeze-halfkp-model.py'))['validate_report']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def utc():
    return datetime.now(timezone.utc)


def process_live(pid, tick):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
    except FileNotFoundError:
        return False
    return fields[0] != 'Z' and fields[19] == tick


def remember_latest(latest, value):
    key = value['engine_sha256']
    previous = latest.get(key)
    if previous is None or datetime.fromisoformat(value['finished_at_utc']) > datetime.fromisoformat(previous['finished_at_utc']):
        latest[key] = value


def choose(plan):
    for path, expected in plan['frozen_inputs_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('frozen input differs: ' + path)
    model = read(ROOT / plan['model_manifest'])
    if not model['complete'] or model['selected']['model_sha256'] != plan['model_sha256']:
        raise ValueError('fixed model differs')
    conditions = read(ROOT / plan['conditions_manifest'])
    dataset = Path(conditions['dataset'])
    if sha(dataset) != conditions['dataset_sha256']:
        raise ValueError('development dataset differs')
    records = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    ids = [row['id'] for row in records]
    if len(ids) != 1024 or len(set(ids)) != 1024:
        raise ValueError('exactly1024 unique development positions required')
    profiles = {}
    for key, spec in plan['profiles'].items():
        profile = read(ROOT / spec['path'])
        if profile['model_sha256'] != plan['model_sha256']:
            raise ValueError('runtime has different model')
        for guard in spec.get('qualification', []):
            report = read(ROOT / guard['path'])
            for field, expected in guard['fields'].items():
                if report.get(field) != expected:
                    raise ValueError('runtime qualification differs: ' + field)
        profiles[key] = profile

    def observation(path, key, trial):
        report = read(path)
        validate_report(report, profiles[key], ids, conditions)
        finished = datetime.fromisoformat(report['finished_at_utc'])
        if finished > utc() or finished >= datetime.fromisoformat(plan['deadline_utc']):
            raise ValueError('measurement finished outside selection window')
        for row, expected in zip(report['details'], records):
            if row['sfen'] != expected['sfen'] or row['expected'] != expected['bestmove']:
                raise ValueError('detail position differs from actual dataset')
            match = bool(row.get('legal') and not row.get('time_overrun')
                         and row.get('actual') == row['expected'])
            if row['match'] != match:
                raise ValueError('detail match flag differs from actual move')
        stamp = finished.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        safe_engine = ''.join(c if c.isalnum() or c in '-_' else '_' for c in report['engine_id'])
        # Prefer the byte-identical public archive over a local working path.
        archive = ROOT / 'results' / finished.astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d') / (safe_engine + '-' + stamp + '-' + path.name)
        evidence = path
        if archive.exists():
            if sha(archive) != sha(path):
                raise ValueError('archived report differs from local result')
            evidence = archive
        return {'runtime': key, 'profile': plan['profiles'][key]['path'],
                'profile_sha256': sha(ROOT / plan['profiles'][key]['path']),
                'engine_sha256': profiles[key]['engine_sha256'],
                'image_sha256': profiles[key]['image_sha256'],
                'model_sha256': profiles[key]['model_sha256'],
                'source_commit': profiles[key]['source_commit'],
                'source_tree_sha256': profiles[key]['source_tree_sha256'],
                'matches': report['matches'], 'positions': 1024,
                'accuracy': report['accuracy'], 'wilson_95': report['wilson_95'],
                'finished_at_utc': report['finished_at_utc'],
                'evidence': {'path': str(evidence), 'sha256': sha(evidence)}, 'trial': trial,
                'priority': plan['profiles'][key]['priority']}, report

    fallback = plan['fallback']
    first, _ = observation(ROOT / fallback['path'], fallback['runtime'], 'historical fallback')
    latest = {first['engine_sha256']: first}
    excluded, comparisons = [], []
    for trial in plan['trials']:
        state = read(ROOT / trial['state'])
        if state['pid'] != trial['pid'] or state['plan_sha256'] != trial['plan_sha256']:
            raise ValueError('trial producer identity differs')
        if state['status'] != 'complete' or process_live(trial['pid'], trial['process_start_time']):
            excluded.append({'trial': trial['id'], 'reason': 'paired trial producer has not completed and exited'})
            continue
        if datetime.fromisoformat(state['updated_at_utc']) >= datetime.fromisoformat(plan['deadline_utc']):
            excluded.append({'trial': trial['id'], 'reason': 'trial producer completed after cutoff'})
            continue
        directory = ROOT / trial['directory']
        identity = read(directory / 'identity.json')
        expected = {'dataset_sha256': conditions['dataset_sha256'], 'sample_ids': ids,
                    'block_size': 256, 'milliseconds': 2000}
        for field, value in expected.items():
            if identity.get(field) != value:
                raise ValueError('pair identity differs: ' + field)
        if identity.get('nodes') is not None:
            raise ValueError('fixed-node diagnostic cannot select strength runtime')
        observations, reports = [], []
        for side in ('baseline', 'candidate'):
            key = trial[side]
            if identity[side + '_manifest_sha256'] != sha(ROOT / plan['profiles'][key]['path']):
                raise ValueError('paired profile identity differs')
            value, report = observation(directory / (side + '.json'), key, trial['id'])
            observations.append(value)
            reports.append(report)
        comparison_path = directory / 'comparison.json'
        comparison = read(comparison_path)
        computed = paired(reports[0]['details'], reports[1]['details'])
        for field, value in computed.items():
            if comparison.get(field) != value:
                raise ValueError('paired result differs from actual full measurements: ' + field)
        if not comparison.get('comparison_operational_pass'):
            raise ValueError('paired trial operational failure')
        if comparison.get('baseline_accuracy') != reports[0]['accuracy'] or comparison.get('candidate_accuracy') != reports[1]['accuracy']:
            raise ValueError('comparison accuracy differs from reports')
        comparisons.append({'trial': trial['id'], 'path': str(comparison_path),
                            'sha256': sha(comparison_path), 'paired': computed})
        for value in observations:
            remember_latest(latest, value)
    ranked = sorted(latest.values(), key=lambda row: (-row['matches'], row['priority']))
    return {'selected': ranked[0], 'ranked_eligible': ranked, 'excluded_trials': excluded,
            'completed_comparisons': comparisons,
            'limitation': 'Development point-estimate selection; overlapping paired intervals do not establish a gain. Unknown within-game correlation is not accounted for. Repeated controls are not pooled or maximized.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    plan = read(args.plan)
    if sha(Path(__file__)) != plan['selector_sha256']:
        raise ValueError('selector source differs')
    if args.dry_run:
        print(json.dumps(choose(plan), indent=2))
        return
    state_path = ROOT / plan['receipt']
    state = {'status': 'waiting', 'pid': os.getpid(), 'started_at_utc': utc().isoformat(),
             'plan_sha256': sha(args.plan), 'selector_sha256': sha(Path(__file__)),
             'execute_at_utc': plan['execute_at_utc']}
    with state_path.open('x') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
    try:
        target = datetime.fromisoformat(plan['execute_at_utc'])
        while utc() < target:
            time.sleep(min(20, max(.01, (target - utc()).total_seconds())))
        if utc() >= datetime.fromisoformat(plan['deadline_utc']):
            raise RuntimeError('runtime freeze deadline missed; never backdate')
        result = choose(plan)
        profile = read(ROOT / result['selected']['profile'])
        image = Path(profile['command'][profile['command'].index('--image') + 1])
        for path, expected in [(image, profile['image_sha256']),
                               (image.parent / 'shogi', profile['engine_sha256']),
                               (image.parent / 'model.bin', plan['model_sha256'])]:
            if sha(path) != expected:
                raise ValueError('actual selected artifact differs: ' + str(path))
        result.update(complete=True, frozen_at_utc=utc().isoformat(), deadline_utc=plan['deadline_utc'],
                      plan_sha256=sha(args.plan), selector_sha256=sha(Path(__file__)),
                      model_manifest=plan['model_manifest'], model_sha256=plan['model_sha256'])
        if utc() >= datetime.fromisoformat(plan['deadline_utc']):
            raise RuntimeError('artifact verification exceeded runtime freeze deadline')
        output = ROOT / plan['output']
        with output.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        state.update(status='complete', output=str(output), output_sha256=sha(output),
                     selected_runtime=result['selected']['runtime'])
    except BaseException as error:
        state.update(status='stopped', error=repr(error))
        raise
    finally:
        state['updated_at_utc'] = utc().isoformat()
        state_path.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
