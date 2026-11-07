#!/usr/bin/env python3
"""Finish the existing heldout child, archive its verdict, cancel later games."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PARENT, PARENT_TICK = 865808, '10980854'
CHILD, CHILD_TICK = 872608, '11078593'
PLAN_SHA = '558ca5ab3a5ecd1307041f0a9be7bca949fd0dd457d1a975f1b68bc94f73e1b2'
STATE = ROOT / '.local/jobs/halfkp-stop-after-heldout-v1.json'
RECEIPT = ROOT / 'results/2026-11-07/final-heldout-user-requested-stop-v1.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def process(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
    except FileNotFoundError:
        return None


def owned(pid, tick):
    value = process(pid)
    return value if value and value[19] == tick else None


def main():
    plan_path = ROOT / 'manifests/halfkp-final-verification-execution-plan-v1.json'
    assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == PLAN_SHA
    plan = json.loads(plan_path.read_text())
    parent = owned(PARENT, PARENT_TICK)
    child = owned(CHILD, CHILD_TICK)
    assert parent and parent[0] == 'T', 'only the held parent may be supervised'
    assert child and child[1] == str(PARENT)
    state = {'status': 'waiting_for_heldout', 'pid': os.getpid(), 'started_at_utc': now(),
             'parent_pid': PARENT, 'parent_start_time': PARENT_TICK,
             'child_pid': CHILD, 'child_start_time': CHILD_TICK,
             'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'user_request': 'Stop after agreement verification; do not start auxiliary or tournament games.'}
    with STATE.open('x') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')

    def save():
        temp = STATE.with_suffix('.partial')
        temp.write_text(json.dumps(state, indent=2) + '\n')
        temp.replace(STATE)

    try:
        while True:
            child = owned(CHILD, CHILD_TICK)
            if child is None or child[0] == 'Z':
                break
            parent = owned(PARENT, PARENT_TICK)
            assert parent and parent[0] == 'T', 'parent hold changed; investigate without restarting'
            time.sleep(20)
        exit_status = int(child[49]) if child and len(child) > 49 else None
        state.update(status='stopping_controller', measurement_exit_status=exit_status)
        save()
        # Child search/VMs have ended. Queue TERM before CONT so the original
        # Python controller handles cancellation before advancing to games.
        parent = owned(PARENT, PARENT_TICK)
        if parent and parent[0] != 'Z':
            assert parent[0] == 'T'
            os.kill(PARENT, signal.SIGTERM)
            os.kill(PARENT, signal.SIGCONT)
            until = time.monotonic() + 10
            while time.monotonic() < until:
                parent = owned(PARENT, PARENT_TICK)
                if parent is None or parent[0] == 'Z':
                    break
                time.sleep(.1)
            else:
                # Only the verified controller, after its measurement child
                # has exited, may be killed; never signal a measurement group.
                if owned(PARENT, PARENT_TICK):
                    os.kill(PARENT, signal.SIGKILL)
        original = json.loads((ROOT / '.local/jobs/halfkp-final-verification-v1.json').read_text())
        assert original['step'] == 2, 'unexpected later stage was reached'
        for name in ('final-auxiliary-20-v1.json', 'final-tournament-operational-2-v1.json'):
            assert not (ROOT / '.local/evaluation' / name).exists(), 'unexpected game output'
        if exit_status not in (0, None):
            raise RuntimeError('measurement child failed; preserve evidence, do not resume')
        directory = ROOT / '.local/evaluation/final-heldout-4096-v1'
        for side in ('baseline', 'candidate'):
            result = json.loads((directory / (side + '.json')).read_text())
            assert result['complete'] and result['measured'] == result['total'] == 4096
        assert (directory / 'comparison.json').exists()
        state['status'] = 'archiving_agreement_verdict'
        save()
        log = ROOT / '.local/jobs/halfkp-stop-after-heldout-summary-v1.log'
        # Reuse the already frozen, reviewable summary/adoption calculation.
        # A negative strength verdict is recorded, never used for retuning.
        with log.open('x') as stream:
            finished = subprocess.run(plan['steps'][2]['argv'], cwd=ROOT,
                                      stdout=stream, stderr=subprocess.STDOUT)
        verdict_path = ROOT / 'results/2026-11-07/final-heldout-4096-v1-adoption-gate.json'
        if not verdict_path.exists():
            raise RuntimeError('summary failed; preserve raw comparison and log')
        verdict = json.loads(verdict_path.read_text())
        receipt = {'complete': True, 'stopped_at_utc': now(),
                   'reason': 'User requested a stop after agreement verification.',
                   'measurement_finished': True, 'measurement_exit_status': exit_status,
                   'agreement_verdict': verdict, 'summary_exit_code': finished.returncode,
                   'cancelled_original_stages': [4, 5], 'games_started': False,
                   'default_image_changed': False, 'original_controller_final_state': original,
                   'future_plan': 'docs/denryu-next-steps.md'}
        with RECEIPT.open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        state.update(status='stopped_as_requested', completed_at_utc=now(),
                     receipt=str(RECEIPT), adoption_pass=verdict['adoption_pass'])
    except BaseException as error:
        state.update(status='stopped_with_error', error=repr(error), updated_at_utc=now())
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
