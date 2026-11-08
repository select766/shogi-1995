#!/usr/bin/env python3
"""Analyse completed GNU-vs-86Box games with a fixed external NNUE evaluator."""
import argparse, hashlib, json, re, sys
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--series',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--nodes',type=int,default=500000);p.add_argument('--max-games',type=int,default=0);p.add_argument('--game',type=int);args=p.parse_args()
 engine=ROOT/'.local/suisho5-analysis/engine';evaldir=ROOT/'.local/suisho5-analysis/official';model=evaldir/'nn.bin'
 r=json.loads(args.series.read_text());games=[(i+1,g) for i,g in enumerate(r['games']) if g['status']=='complete']
 if args.game is not None:games=[x for x in games if x[0]==args.game]
 if args.max_games:games=games[:args.max_games]
 if not games:raise ValueError('no completed games selected')
 args.output.mkdir(parents=True,exist_ok=True);out=args.output.resolve();report_path=out/'analysis.json'
 if report_path.exists(): raise ValueError('refusing to overwrite analysis')
 report={'complete':False,'engine_sha256':digest(engine),'model_sha256':digest(model),'nodes_requested':args.nodes,'options':{'Threads':1,'USI_Hash':128,'USI_OwnBook':False,'FV_SCALE':24,'PvInterval':0,'EvalDir':str(evaldir)},'score_convention':'cp from GNU side; mate values separate; score is a searched engine estimate','games':[]}
 def save():
  path=out/'analysis.tmp';path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');path.replace(report_path)
 save()
 with Engine([str(engine)],out,out/'usi',report['options']) as e:
  report['engine_id']=e.name;save()
  for number,g in games:
   path=args.series.parent/f'game-{number:03}.usi';tokens=path.read_text().strip().split()
   if tokens[:2]!=['startpos','moves']:raise ValueError('bad record')
   moves=tokens[2:];played=[x['actual'] for x in g['moves'] if x['actual'] not in ('resign','win')]
   opening=len(moves)-len(played)
   if opening<0 or (played and moves[opening:]!=played):raise ValueError('record and game history disagree')
   board=cshogi.Board()
   for move in moves[:opening]:
    m=board.move_from_usi(move)
    if not board.is_legal(m):raise ValueError('illegal opening '+move)
    board.push(m)
   game={'number':number,'opening_line':g['opening_line'],'gnu_side':g['gnu_side'],'opening_plies':opening,'outcome':g['outcome'],'positions':[]};report['games'].append(game);save()
   e.reset()
   for ply in range(opening,len(moves)+1):
    if not board.is_game_over():
     e.send('position startpos'+(' moves '+' '.join(moves[:ply]) if ply else ''))
     e.send('go nodes '+str(args.nodes));_,lines=e.until('bestmove ',90)
     valid=[]
     for line in lines:
      if not line.startswith('info ') or ' score ' not in line or ' lowerbound' in line or ' upperbound' in line:continue
      m=re.search(r'\bscore (cp|mate) (-?\d+|[+-])',line)
      if m:valid.append((line,m))
     if not valid:
      pos={'ply':ply,'turn':int(board.turn),'score_type':'unknown','score_gnu':None,'depth':None,'nodes':None,'bestmove':lines[-1].split()[1],'played_next':moves[ply] if ply<len(moves) else None,'pv':'','reason':'no unbounded score reported'}
     else:
      line,m=valid[-1];sign=1 if board.turn==g['gnu_side'] else -1
      val=m.group(2);score=int(val)*sign if val not in ('+','-') else (val if sign==1 else ('-' if val=='+' else '+'))
      def number_field(k):
       v=re.search(r'\b'+k+r' (\d+)',line);return int(v.group(1)) if v else None
      pos={'ply':ply,'turn':int(board.turn),'score_type':m.group(1),'score_gnu':score,'depth':number_field('depth'),'nodes':number_field('nodes'),'bestmove':lines[-1].split()[1],'played_next':moves[ply] if ply<len(moves) else None,'pv':line.split(' pv ',1)[1] if ' pv ' in line else ''}
     game['positions'].append(pos);save()
    if ply<len(moves):
     move=board.move_from_usi(moves[ply])
     if not board.is_legal(move):raise ValueError('illegal move at %s:%s'%(number,ply))
     board.push(move)
   print('analyzed game',number,'positions',len(game['positions']),flush=True)
  report['complete']=True;save()
if __name__=='__main__':main()
