#!/usr/bin/env python3
"""Compare original and original-with-recapture-fix at actual game positions."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
out=ROOT/'.local/native-gnu-audit/critical-positions';out.mkdir(exist_ok=False)
series=ROOT/'.local/native-gnu-evaluation-20261107'
cases=[(1,38),(2,39),(3,44)]
versions={'original':ROOT/'.local/native-gnushogi/src/gnushogir','recapture-fix':ROOT/'.local/native-gnu-audit/recapture-fix/gnushogir'}
report={'cases':cases,'results':[],'sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in versions.items()},'complete':False}
def save():
 p=out/'results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(out/'results.json')
save()
for name,binary in versions.items():
 cmd=[sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--native-binary',str(binary),'--run-root',str(out)]
 with Engine(cmd,ROOT,out/name,{'Threads':1,'USI_OwnBook':False,'USI_Ponder':False}) as e:
  for game,ply in cases:
   moves=(series/f'game-{game:03}.usi').read_text().split()[2:ply+2]
   e.reset();v=e.search_position('position startpos moves '+' '.join(moves),'go btime 0 wtime 0 byoyomi 10000',90)
   report['results'].append({'version':name,'game':game,'ply':ply,**v});save();print(json.dumps(report['results'][-1]),flush=True)
report['complete']=True;save()
