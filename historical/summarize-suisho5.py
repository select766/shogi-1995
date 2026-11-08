#!/usr/bin/env python3
"""Summarize one completed external-evaluator analysis and draw per-game traces."""
import argparse, collections, json, statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 p=argparse.ArgumentParser();p.add_argument('analysis',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 r=json.loads(a.analysis.read_text());a.out.mkdir(parents=True,exist_ok=True)
 games=r['games'];losses={'gnu':[],'yaneuraou':[]};summaries=[]
 cols=2;shown=min(len(games),6);rows=max(1,(shown+1)//2);fig,axes=plt.subplots(rows,cols,figsize=(12,2.8*rows),squeeze=False)
 for i,g in enumerate(games):
  ax=axes.flat[i] if i<shown else None
  pos=g['positions']; cp=[x for x in pos if x['score_type']=='cp' and isinstance(x['score_gnu'],int)];
  if ax is not None:
   ax.plot([x['ply'] for x in cp],[max(-3000,min(3000,x['score_gnu'])) for x in cp],color='#284b8b',linewidth=1.4)
   ax.axhline(0,color='gray',linewidth=.6);ax.set_ylim(-3100,3100);ax.grid(alpha=.2)
   mates=[x for x in pos if x['score_type']=='mate']
   for x in mates:
    if isinstance(x['score_gnu'],int):ax.scatter([x['ply']],[3000 if x['score_gnu']>0 else -3000],s=12,color='#b63b32')
   ax.set_title('Game %d; GNU %s'%(g['number'],'first' if g['gnu_side']==0 else 'second'));ax.set_xlabel('Total ply');ax.set_ylabel('Score for GNU (cp, clipped)')
  start=pos[0] if pos else None
  summaries.append({'game':g['number'],'gnu_side':g['gnu_side'],'start':start,'last':pos[-1] if pos else None})
  for x,y in zip(pos,pos[1:]):
   if x['score_type']!='cp' or y['score_type']!='cp' or not isinstance(x['score_gnu'],int) or not isinstance(y['score_gnu'],int):continue
   if x['ply']+1!=y['ply']:continue
   mover='gnu' if x['turn']==g['gnu_side'] else 'yaneuraou'
   loss=(x['score_gnu']-y['score_gnu'])*(1 if mover=='gnu' else -1)
   losses[mover].append({'loss':loss,'game':g['number'],'ply':y['ply'],'move':x['played_next'],'before':x['score_gnu'],'after':y['score_gnu'],'bestmove':x['bestmove']})
 for ax in list(axes.flat)[shown:]:ax.remove()
 fig.tight_layout();fig.savefig(a.out/'evaluation-trajectories.png',dpi=150);plt.close(fig)
 stats={}
 for k,v in losses.items():
  q=[x['loss'] for x in v];stats[k]={'count':len(q),'median_loss':statistics.median(q) if q else None,'mean_loss':statistics.mean(q) if q else None,'loss_ge_200':sum(x>=200 for x in q),'loss_ge_500':sum(x>=500 for x in q),'largest_losses':sorted(v,key=lambda x:x['loss'],reverse=True)[:10]}
 (a.out/'summary.json').write_text(json.dumps({'source':str(a.analysis),'analysis_complete':r.get('analysis_complete_through',len(games))>=100 if 'analysis_complete_through' in r else r['complete'],'nodes':r['nodes_requested'],'unknown_scores':sum(x['score_type']=='unknown' for g in games for x in g['positions']),'games':summaries,'statistics':stats},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
