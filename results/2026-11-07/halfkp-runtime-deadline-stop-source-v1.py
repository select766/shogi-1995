from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import signal
import time

ROOT=Path('/home/select766/shogi/shogi-1995')
JOB=ROOT/'.local/jobs/halfkp-fixed-model-radix-ordinary-v1.json'
OWN=ROOT/'.local/jobs/halfkp-runtime-cutoff-v1.json'
RECEIPT=ROOT/'results/2026-11-07/halfkp-runtime-deadline-stop-receipt-v1.json'
PID=823660
TICK='10407412'
PLAN='80091a6897ec6644edb58a6927253e0808ff2825806ccc60e858370c231cfe00'
DEADLINE=datetime(2026,11,7,5,59,tzinfo=timezone.utc)

def identity(pid):
    try:
        x=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
        return x[0],x[19]
    except FileNotFoundError:
        return None,None

def now():return datetime.now(timezone.utc).isoformat()

state={'status':'waiting','pid':os.getpid(),'started_at_utc':now(),'deadline_utc':DEADLINE.isoformat(),'owned_job_pid':PID,'owned_job_start_time':TICK,'owned_plan_sha256':PLAN,'guard_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with OWN.open('x') as f:json.dump(state,f,indent=2);f.write('\n')
while datetime.now(timezone.utc)<DEADLINE:
    time.sleep(min(30,max(.01,(DEADLINE-datetime.now(timezone.utc)).total_seconds())))
snapshot=json.loads(JOB.read_text())
if snapshot['pid']!=PID or snapshot['plan_sha256']!=PLAN:
    raise RuntimeError('owned job identity changed: refuse to signal')
status,tick=identity(PID)
receipt={'observed_at_utc':now(),'deadline_utc':DEADLINE.isoformat(),'job_snapshot':snapshot,'owned_process_status':status,'owned_process_start_time':tick,'signal_sent':False,'reason':'runtime exploration deadline; intentionally stop only the exact owned ordinary-time job if still live, preserve all partial evidence'}
if tick==TICK and status not in (None,'Z'):
    if snapshot['status'] not in ('executing','waiting_for_job'):
        raise RuntimeError('live owned process in unexpected state: refuse to signal')
    os.kill(PID,signal.SIGTERM)
    receipt.update(signal_sent=True,signal='SIGTERM',signal_at_utc=now())
    until=time.monotonic()+20
    while time.monotonic()<until:
        status,tick=identity(PID)
        if tick!=TICK or status in (None,'Z'):break
        time.sleep(.2)
    receipt['owned_process_after_signal']={'status':status,'start_time':tick}
else:
    receipt['reason']='owned ordinary trial had already exited; no signal needed'
receipt['final_job_snapshot']=json.loads(JOB.read_text())
with RECEIPT.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
state.update(status='complete',finished_at_utc=now(),receipt=str(RECEIPT))
OWN.write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
