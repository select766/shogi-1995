#!/usr/bin/env python3
"""After supplementation, play the recapture fix against the same 86Box engine."""
import datetime,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];deadline=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
ready=ROOT/'.local/native-gnu-supplement-status.json';status=ROOT/'.local/native-gnu-audit/recapture-vs-yane-status.json';out=ROOT/'.local/native-gnu-audit/recapture-vs-yane'
while datetime.datetime.now(datetime.timezone.utc)<deadline:
 try:r=json.loads(ready.read_text())
 except (OSError,ValueError):r={}
 if r.get('status')=='complete':break
 if r.get('status') in ('error','blocked'):
  status.write_text(json.dumps({'status':'blocked','reason':'supplement did not finish'},indent=2)+'\n');raise SystemExit(1)
 time.sleep(20)
else:
 status.write_text(json.dumps({'status':'not_started','reason':'deadline'},indent=2)+'\n');raise SystemExit(1)
status.write_text(json.dumps({'status':'running'},indent=2)+'\n')
args=['taskset','-c','4,5',sys.executable,str(ROOT/'historical/native-series.py'),'--output',str(out),'--backend','86box','--pairs','3','--opening-lines','1157,1354,779','--gnu-binary',str(ROOT/'.local/native-gnu-audit/recapture-fix/gnushogir')]
x=subprocess.Popen(args,cwd=ROOT,env={**os.environ,'TMPDIR':'/tmp'})
while x.poll() is None:
 if datetime.datetime.now(datetime.timezone.utc)>=deadline:
  x.send_signal(signal.SIGINT)
  try:x.wait(timeout=20)
  except subprocess.TimeoutExpired:x.terminate();x.wait(timeout=10)
  break
 time.sleep(10)
status.write_text(json.dumps({'status':'complete' if x.returncode==0 else 'error','returncode':x.returncode},indent=2)+'\n')
raise SystemExit(x.returncode)
