#!/usr/bin/env python3
"""Check whether six times more time changes moves in three critical positions."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
out=ROOT/'.local/native-gnu-audit/long-think';out.mkdir(exist_ok=False)
series=ROOT/'.local/native-gnu-evaluation-20261107';cases=[(1,38),(2,39),(3,44)]
r={'complete':False,'cases':cases,'seconds':60,'results':[]}
def save():
 p=out/'result.tmp';p.write_text(json.dumps(r,indent=2)+'\n');p.replace(out/'result.json')
save()
cmd=[sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--run-root',str(out)]
with Engine(cmd,ROOT,out/'usi',{'Threads':1,'USI_OwnBook':False,'USI_Ponder':False}) as e:
 for game,ply in cases:
  moves=(series/f'game-{game:03}.usi').read_text().split()[2:ply+2]
  e.reset();v=e.search_position('position startpos moves '+' '.join(moves),'go btime 0 wtime 0 byoyomi 60000',150)
  r['results'].append({'game':game,'ply':ply,**v});save();print(json.dumps(r['results'][-1]),flush=True)
r['complete']=True;save()
