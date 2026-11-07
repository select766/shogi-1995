#!/usr/bin/env python3
"""Generic USI fixed-byoyomi matches; no shared measurement/history writes."""
import argparse,json,sys,time
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
from shogi1995.sessions import COMMON
from shogi1995.match_rules import Referee

def main():
 p=argparse.ArgumentParser();p.add_argument('--a',required=True,help='JSON argv');p.add_argument('--a-options',default='{}');p.add_argument('--b-options',default='{}');p.add_argument('--b',required=True,help='JSON argv');p.add_argument('--output',type=Path,required=True);p.add_argument('--opening',default='7g7f 3c3d');p.add_argument('--start-sfen',default=cshogi.STARTING_SFEN);p.add_argument('--milliseconds',type=int,default=2000);p.add_argument('--grace-ms',type=int,default=200,help='Explicit host overtime allowance; never subtracted from engine time');p.add_argument('--max-plies',type=int,default=512);p.add_argument('--depth',type=int,help='Operational smoke only');p.add_argument('--backend-label',choices=('diagnostic','86box'),default='diagnostic');a=p.parse_args()
 if a.output.exists():raise ValueError('output already exists')
 if a.milliseconds<1000 or a.grace_ms<0 or a.max_plies<1:raise ValueError('invalid limits')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 engine_options=[json.loads(a.a_options),json.loads(a.b_options)]
 if any(set(o)&set(COMMON) for o in engine_options):raise ValueError('model options may not override common options')
 opening=a.opening.split();commands=[json.loads(a.a),json.loads(a.b)]
 report=dict(complete=False,mode='fixed_depth_smoke' if a.depth else 'fixed_byoyomi',backend=a.backend_label,commands=commands,engine_options=engine_options,opening=opening,start_sfen=a.start_sfen,milliseconds=a.milliseconds,grace_ms=a.grace_ms,games=[],note='Two color-swapped games from one opening; no independent-sample Elo claim.')
 def save():
  tmp=a.output.with_suffix('.partial');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(a.output)
 save();engines=[]
 try:
  for i,c in enumerate(commands):engines.append(Engine(c,ROOT,str(a.output)+f'.logs/{i}',{**COMMON,**engine_options[i]}))
  for swap in (0,1):
   for engine in engines:engine.reset()
   referee=Referee(a.start_sfen,1000000,0,a.max_plies+len(opening))
   for move in opening:
    outcome=referee.accept(move,0)
    if outcome:raise ValueError('opening ends game: '+str(outcome))
   game=dict(a_color=swap,moves=[]);report['games'].append(game);save();outcome=referee.terminal()
   while outcome is None:
    side=referee.board.turn;engine=engines[0 if side==swap else 1]
    command=f'go depth {a.depth}' if a.depth else f'go btime 0 wtime 0 byoyomi {a.milliseconds}'
    try:
     result=engine.search_position(referee.position_command(),command,60 if a.depth else a.milliseconds/1000+10)
    except (RuntimeError,TimeoutError,OSError) as error:
     outcome=dict(winner=1-side,reason='engine_failure',error=str(error));break
    game['moves'].append(dict(side=side,**result));referee.remaining[side]=1000000 if a.depth else a.milliseconds+a.grace_ms
    outcome=referee.accept(result['actual'],result['host_ms']);save()
   game['outcome']=outcome;game['a_result']='draw' if outcome['winner'] is None else 'win' if outcome['winner']==swap else 'loss';save()
  report['complete']=True
  report['score_a']={k:sum(g['a_result']==k for g in report['games']) for k in ('win','draw','loss')}
 finally:
  for engine in engines:engine.close()
  save()
 print(json.dumps({k:v for k,v in report.items() if k!='games'},indent=2))
if __name__=='__main__':main()
