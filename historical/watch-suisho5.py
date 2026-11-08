#!/usr/bin/env python3
"""Analyze completed games from the two independent pair slices until 09:00 JST."""
import datetime,json,os,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PY=sys.executable
SOURCES=[('primary',ROOT/'.local/native-gnu-evaluation-20261107/series.json',0),('worker2',ROOT/'.local/native-gnu-evaluation-20261107-worker2/series.json',50),('supplement',ROOT/'.local/native-gnu-evaluation-supplement/series.json',100)]
BASE=ROOT/'.local/suisho5-analysis/pass-002/analysis.json';OUT=ROOT/'.local/suisho5-analysis/live';OUT.mkdir(parents=True,exist_ok=True)
EXCLUDED={'primary':{25,26},'worker2':{11,12,13,14},'supplement':set()}
DEADLINE=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

def save(data):
 p=OUT/'combined.tmp';p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');p.replace(OUT/'combined.json')

def aggregate():
 data=json.loads(BASE.read_text());games={g['number']:g for g in data['games']};done={('primary',g['number']) for g in data['games']} | {(source,n) for source,nums in EXCLUDED.items() for n in nums}
 for p in sorted(list(OUT.glob('game-*/analysis.json'))+list(OUT.glob('worker2-game-*/analysis.json'))+list(OUT.glob('supplement-game-*/analysis.json'))):
  d=json.loads(p.read_text())
  if not d['complete']:continue
  source='worker2' if p.parent.name.startswith('worker2-') else 'supplement' if p.parent.name.startswith('supplement-') else 'primary'
  for orig in d['games']:
   g=dict(orig);done.add((source,g['number']))
   if g['number'] in EXCLUDED[source]:continue
   g['source_game']=g['number'];g['source']=source;g['number']+=50 if source=='worker2' else 100 if source=='supplement' else 0;games[g['number']]=g
 data['games']=[games[n] for n in sorted(games)];data['analysis_complete_through']=len(games);data['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(data)
 subprocess.run([PY,str(ROOT/'historical/summarize-suisho5.py'),str(OUT/'combined.json'),'--out',str(ROOT/'results/suisho5-native-gnu-live')],cwd=ROOT,env={**os.environ,'MPLCONFIGDIR':'/tmp/mpl-shogi'},check=True)
 return done

def main():
 while datetime.datetime.now(datetime.timezone.utc)<DEADLINE:
  analyzed=aggregate();pending=[];states=[]
  for name,source,offset in SOURCES:
   if not source.exists():continue
   series=json.loads(source.read_text());states.append(series)
   for i,g in enumerate(series['games']):
    if name=='primary' and i>=50:continue
    if g['status']=='complete' and (name,i+1) not in analyzed:pending.append((name,source,i+1))
  if pending:
   name,source,number=pending[0];label=(name+'-' if name!='primary' else '')+f'game-{number:03}';out=OUT/label
   if out.exists():
    (OUT/'watch-error.txt').write_text(f'Incomplete analysis directory: {out}; manual inspection needed\n');break
   cmd=['taskset','-c','3','nice','-n','10',PY,str(ROOT/'historical/analyze-suisho5.py'),'--series',str(source),'--output',str(out),'--nodes','500000','--game',str(number)]
   with (OUT/(label+'.log')).open('w') as log:
    if subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=log).returncode:
     (OUT/'watch-error.txt').write_text(f'Analysis failed: {label}; see {log.name}\n');break
   continue
  if len(analyzed)-sum(map(len,EXCLUDED.values()))>=100:break
  time.sleep(30)
 aggregate();(OUT/'watch-stopped.txt').write_text('Stopped at '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
if __name__=='__main__':
 try:main()
 except BaseException:
  (OUT/'watch-error.txt').write_text(traceback.format_exc());raise
