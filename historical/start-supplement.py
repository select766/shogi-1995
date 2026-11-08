#!/usr/bin/env python3
"""Run three unique replacement openings after the video workers finish."""
import datetime,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];deadline=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
video=ROOT/'.local/match-video/recording-gnu-gote-02/result.json';out=ROOT/'.local/native-gnu-evaluation-supplement';status=ROOT/'.local/native-gnu-supplement-status.json'
while datetime.datetime.now(datetime.timezone.utc)<deadline:
 try:r=json.loads(video.read_text())
 except (OSError,ValueError):r={}
 if r.get('status')=='complete':break
 if r.get('status')=='error':
  status.write_text(json.dumps({'status':'blocked','reason':'second video error'},indent=2)+'\n');raise SystemExit(1)
 time.sleep(20)
else:
 status.write_text(json.dumps({'status':'not_started','reason':'deadline'},indent=2)+'\n');raise SystemExit(1)
status.write_text(json.dumps({'status':'running'},indent=2)+'\n')
args=['taskset','-c','4,5',sys.executable,str(ROOT/'historical/native-series.py'),'--output',str(out),'--backend','86box','--pairs','3','--opening-lines','749,1748,989']
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
