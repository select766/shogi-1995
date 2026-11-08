#!/usr/bin/env python3
"""Paired native GNU original versus recapture-only fix, exploratory."""
import hashlib,json,sys
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
from shogi1995.match_rules import Referee
out=ROOT/'.local/native-gnu-audit/recapture-match'
if out.exists():raise ValueError('output already exists')
out.mkdir();runs=out/'runs';runs.mkdir()
files={'original':ROOT/'.local/native-gnushogi/src/gnushogir','fix':ROOT/'.local/native-gnu-audit/recapture-fix/gnushogir'}
source=json.loads((ROOT/'.local/native-gnu-evaluation-20261107/series.json').read_text());lines=(ROOT/'private/gokaku/taya36.sfen').read_text().splitlines()
indices=source['selected_line_numbers'][:3]
r={'complete':False,'source':'same first three dataset positions as main series','selected_line_numbers':indices,'gnu_side_means':'original side','seconds_per_move':10,'hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},'games':[]}
def save():
 p=out/'series.tmp';p.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');p.replace(out/'series.json')
save();engines=[]
try:
 for name,binary in files.items():
  cmd=[sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--native-binary',str(binary),'--run-root',str(runs)]
  engines.append(Engine(cmd,ROOT,out/(name+'-usi'),{'Threads':1,'USI_OwnBook':False,'USI_Ponder':False}))
 for index in indices:
  opening=lines[index-1].split()[2:]
  for side in (0,1):
   ref=Referee(cshogi.STARTING_SFEN,1000000000,0,256)
   g={'opening_line':index,'gnu_side':side,'moves':[],'status':'running','outcome':None};r['games'].append(g);number=len(r['games']);record=out/f'game-{number:03}.usi'
   def snapshot():record.write_text('startpos moves' + (' '+' '.join(ref.moves) if ref.moves else '')+'\n');save()
   try:
    for move in opening:
     if ref.accept(move,0):raise ValueError('terminal opening')
    snapshot()
    for e in engines:e.reset()
    result=None
    while not result:
     turn=ref.board.turn;e=engines[0 if turn==side else 1]
     v=e.search_position(ref.position_command(),'go btime 0 wtime 0 byoyomi 10000',90);ref.remaining[turn]=1000000000
     result=ref.accept(v['actual'],v['host_ms']);g['moves'].append({'side':turn,**v});snapshot()
    if result['reason'] in ('illegal_move','illegal_declaration','time_forfeit'):raise ValueError(str(result))
    g['status']='complete';g['outcome']=result;snapshot();print(json.dumps({'game':number,'side':side,'outcome':result}),flush=True)
   except (RuntimeError,TimeoutError,OSError,ValueError) as exc:
    g['status']='abnormal';g['error']=str(exc);snapshot();raise
 r['complete']=True
finally:
 for e in reversed(engines):e.close()
 save()
