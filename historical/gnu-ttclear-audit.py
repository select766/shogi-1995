#!/usr/bin/env python3
"""Replay previous thinking before critical positions, comparing TT clearing."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
out=ROOT/'.local/native-gnu-audit/ttclear-critical';out.mkdir(exist_ok=False)
series=ROOT/'.local/native-gnu-evaluation-20261107';cases=[(1,36,38),(2,37,39),(3,36,44)]
versions={'original':ROOT/'.local/native-gnushogi/src/gnushogir','ttclear':ROOT/'.local/native-gnu-audit/ttclear-fix/gnushogir'}
r={'complete':False,'cases':cases,'hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in versions.items()},'results':[]}
def save():
 p=out/'result.tmp';p.write_text(json.dumps(r,indent=2)+'\n');p.replace(out/'result.json')
save()
for mode,binary in versions.items():
 for game,start,end in cases:
  cmd=[sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--native-binary',str(binary),'--run-root',str(out)]
  with Engine(cmd,ROOT,out/f'{mode}-game{game}',{'Threads':1,'USI_Ponder':False,'USI_OwnBook':False}) as e:
   moves=(series/f'game-{game:03}.usi').read_text().split()[2:]
   for ply in range(start,end+1,2):
    q=e.search_position('position startpos moves '+' '.join(moves[:ply]),'go btime 0 wtime 0 byoyomi 10000',90)
    r['results'].append({'mode':mode,'game':game,'ply':ply,'actual_game_move':moves[ply],**q});save();print(json.dumps(r['results'][-1]),flush=True)
r['complete']=True;save()
