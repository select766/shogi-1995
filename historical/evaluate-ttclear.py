#!/usr/bin/env python3
"""Evaluate differences between TT-cleared and ordinary GNU on saved histories."""
import json,re,sys
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
source=json.loads((ROOT/'.local/native-gnu-audit/ttclear-critical/result.json').read_text());series=json.loads((ROOT/'.local/native-gnu-evaluation-20261107/series.json').read_text());groups={}
for x in source['results']:groups.setdefault((x['game'],x['ply']),{})[x['mode']]=x['actual']
out=ROOT/'.local/suisho5-analysis/ttclear-judgment.json';rows=[]
if out.exists():raise ValueError('output already exists')
opts={'Threads':1,'USI_Hash':128,'USI_OwnBook':False,'FV_SCALE':24,'PvInterval':0,'EvalDir':str(ROOT/'.local/suisho5-analysis/official')}
with Engine([str(ROOT/'.local/suisho5-analysis/engine')],ROOT/'.local/suisho5-analysis',ROOT/'.local/suisho5-analysis/ttclear-usi',opts) as e:
 for (game,ply),choices in sorted(groups.items()):
  if len(set(choices.values()))==1:continue
  actual=(ROOT/f'.local/native-gnu-evaluation-20261107/game-{game:03}.usi').read_text().split()[2:];side=series['games'][game-1]['gnu_side']
  for mode,move in choices.items():
   history=actual[:ply]+[move];board=cshogi.Board()
   for s in history:
    m=board.move_from_usi(s)
    if not board.is_legal(m):raise ValueError(s)
    board.push(m)
   e.reset();e.send('position startpos moves '+' '.join(history));e.send('go nodes 3000000');_,ls=e.until('bestmove ',90)
   valid=[l for l in ls if l.startswith('info ') and ' score ' in l and ' lowerbound' not in l and ' upperbound' not in l]
   match=re.search(r'\bscore (cp|mate) (-?\d+)',valid[-1]);rows.append({'game':game,'ply':ply,'mode':mode,'move':move,'score_type':match[1],'score_gnu':int(match[2])*(1 if board.turn==side else -1),'info':valid[-1]});out.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows[-1]),flush=True)
