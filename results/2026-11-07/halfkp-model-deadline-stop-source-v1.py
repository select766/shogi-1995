import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import time

ROOT = Path('/home/select766/shogi/shogi-1995')
PLAN = ROOT / 'manifests/halfkp-fixed-model-optimization-schedule-v1.json'
OUTPUT = ROOT / '.local/jobs/halfkp-model-cutoff-v1.json'
plan = json.loads(PLAN.read_text())
target = plan['active_job']
cutoff = datetime.datetime.fromisoformat(plan['development_queue_stop_utc'])
record = {'status': 'waiting', 'pid': os.getpid(), 'target': target,
          'stop_at_utc': cutoff.isoformat(),
          'guard_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'schedule_sha256': hashlib.sha256(PLAN.read_bytes()).hexdigest(),
          'reason': 'user model-structure deadline; preserve evidence and prevent later geometry steps'}

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
        return fields[0], fields[19]
    except FileNotFoundError:
        return None, None

def save():
    record['updated_at_utc'] = now().isoformat()
    temporary = OUTPUT.with_suffix('.partial')
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(OUTPUT)

state = json.loads((ROOT / target['state']).read_text())
assert state['pid'] == target['pid'] and state['plan_sha256'] == target['plan_sha256']
assert identity(target['pid'])[1] == target['start_time']
assert now() < cutoff
with OUTPUT.open('x') as stream:
    stream.write(json.dumps(record, indent=2) + '\n')
try:
    while now() < cutoff:
        time.sleep(min(10, max(0.01, (cutoff - now()).total_seconds())))
    state = json.loads((ROOT / target['state']).read_text())
    assert state['pid'] == target['pid'] and state['plan_sha256'] == target['plan_sha256']
    status, start = identity(target['pid'])
    record['state_before_stop'] = state
    if status in (None, 'Z') or start != target['start_time']:
        record['status'] = 'target_already_exited'
    else:
        record['signal_sent_at_utc'] = now().isoformat()
        os.kill(target['pid'], signal.SIGTERM)
        record['status'] = 'term_sent'
        save()
        limit = time.monotonic() + 20
        while time.monotonic() < limit:
            status, start = identity(target['pid'])
            if status in (None, 'Z') or start != target['start_time']:
                record['status'] = 'deadline_stop_complete'
                break
            time.sleep(0.2)
        else:
            raise RuntimeError('owned queue did not exit after SIGTERM; inspect without blind restart')
    record['state_after_stop'] = json.loads((ROOT / target['state']).read_text())
except BaseException as error:
    record.update(status='error', error=repr(error))
    raise
finally:
    save()
print(json.dumps(record))
