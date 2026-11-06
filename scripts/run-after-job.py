#!/usr/bin/env python3
"""Run frozen steps once an identified owned prerequisite has completed and exited."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def process_identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
        return fields[0], fields[19]
    except FileNotFoundError:
        return None, None


def job_ready(expected, state, identity):
    if state['plan_sha256'] != expected['plan_sha256'] or state['pid'] != expected['pid']:
        raise ValueError('prerequisite identity changed')
    status, start = identity
    exited = status in (None, 'Z') or start != expected['process_start_time']
    if state['status'] == 'complete':
        return exited
    if state['status'] == 'stopped' or exited:
        raise RuntimeError('prerequisite stopped without completion; investigate, never restart automatically')
    return False


def completed_inputs(specs):
    snapshots = {}
    for name, spec in specs.items():
        path = Path(name)
        if spec.get('sha256') and digest(path) != spec['sha256']:
            raise ValueError('input hash differs: ' + name)
        value = json.loads(path.read_text())
        for key, expected in spec.get('fields', {}).items():
            if value.get(key) != expected:
                raise ValueError('input field differs: ' + name + ': ' + key)
        snapshots[name] = {'sha256': digest(path), 'records': value.get('records')}
    return snapshots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    state = {'status': 'waiting_for_job', 'pid': os.getpid(),
             'started_at_utc': datetime.now(timezone.utc).isoformat(), 'plan_sha256': digest(args.plan)}
    args.state.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally launching this owned job twice.
    with args.state.open('x') as stream:
        stream.write(json.dumps(state, indent=2) + '\n')
    child = None

    def save():
        temporary = args.state.with_suffix('.partial')
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(args.state)

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        prerequisite = plan['prerequisite_job']
        while True:
            parent = json.loads(Path(prerequisite['state']).read_text())
            if job_ready(prerequisite, parent, process_identity(prerequisite['pid'])):
                state['completed_prerequisite_sha256'] = digest(prerequisite['state'])
                break
            time.sleep(2)
        for name, expected in plan['code_sha256'].items():
            if digest(ROOT / name) != expected:
                raise ValueError('planned code changed: ' + name)
        for name, expected in plan.get('frozen_artifacts_sha256', {}).items():
            if digest(ROOT / name) != expected:
                raise ValueError('planned artifact changed: ' + name)
        state['completed_inputs'] = completed_inputs(plan.get('completed_inputs', {}))
        state.update(status='executing', execution_started_at_utc=datetime.now(timezone.utc).isoformat())
        save()
        for index, step in enumerate(plan['steps'], 1):
            state.update(step=index, description=step['description'], log=step['log'])
            save()
            # Preserve logs even after a failed attempt; never silently replace evidence.
            with Path(step['log']).open('x') as log:
                child = subprocess.Popen(step['argv'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
                state['child_pid'] = child.pid
                save()
                code = child.wait()
                child = None
                state['child_pid'] = None
            if code:
                raise RuntimeError(f'step {index} failed with exit {code}')
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='stopped', error=str(error))
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
