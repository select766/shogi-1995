#!/usr/bin/env python3
"""Stop first slice after 50 games; stop both at requested deadline."""
import datetime,json,os,signal,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAMES=['.local/native-gnu-evaluation-20261107','.local/native-gnu-evaluation-20261107-worker2']
DEADLINE=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
LOG=ROOT/'.local/native-gnu-evaluation-guard.log'

def stop(name,reason):
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:args=(proc/'cmdline').read_bytes().split(b'\0')
  except (OSError,PermissionError):continue
  if b'historical/native-series.py' not in args or name.encode() not in args:continue
  try:os.kill(int(proc.name),signal.SIGINT)
  except ProcessLookupError:continue
  with LOG.open('a') as f:f.write(f'{datetime.datetime.now(datetime.timezone.utc).isoformat()} stopped pid={proc.name} series={name} reason={reason}\n')

def main():
 first_stopped=False
 while True:
  now=datetime.datetime.now(datetime.timezone.utc)
  if now>=DEADLINE:
   for name in NAMES:stop(name,'09:00 JST deadline')
   break
  try:
   r=json.loads((ROOT/NAMES[0]/'series.json').read_text());complete=sum(g['status']=='complete' for g in r['games'])
  except (OSError,ValueError,KeyError):complete=0
  if complete>=50 and not first_stopped:stop(NAMES[0],'first 25 opening pairs complete');first_stopped=True
  if first_stopped:
   try:
    other=json.loads((ROOT/NAMES[1]/'series.json').read_text())
    if other.get('complete'):break
   except (OSError,ValueError):pass
  time.sleep(10)
if __name__=='__main__':main()
