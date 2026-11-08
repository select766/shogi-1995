#!/usr/bin/env python3
"""Publish progress from existing local data without touching running games."""
import collections,datetime,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/suisho5-native-gnu-live';OUT.mkdir(parents=True,exist_ok=True)
DEADLINE=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
SERIES=[ROOT/'.local/native-gnu-evaluation-20261107/series.json',ROOT/'.local/native-gnu-evaluation-20261107-worker2/series.json',ROOT/'.local/native-gnu-evaluation-supplement/series.json']
VIDEOS=[ROOT/'.local/match-video/recording-gnu-sente-02/result.json',ROOT/'.local/match-video/recording-gnu-gote-02/result.json']
def run():
 score=collections.Counter();observed=[]
 for j,p in enumerate(SERIES):
  if not p.exists():continue
  r=json.loads(p.read_text());games=r['games'][:50] if j==0 else r['games']
  for i,g in enumerate(games):
   if (j==0 and i+1 in (25,26)) or (j==1 and i+1 in (11,12,13,14)):
    if g['status']=='complete':score['duplicate_excluded']+=1
    continue
   if g['status']=='complete':
    winner=g['outcome']['winner'];score['draw' if winner is None else 'gnu' if winner==g['gnu_side'] else 'yaneuraou']+=1
   else:score[g['status']]+=1
  observed.append({'series':str(p.relative_to(ROOT)),'finished':sum(g['status']=='complete' for g in games),'complete_flag':r.get('complete',False)})
 analysis={}
 try:
  a=json.loads((OUT/'summary.json').read_text());analysis={'games':len(a['games']),'statistics':a['statistics']}
 except (OSError,ValueError,KeyError):pass
 videos=[]
 for p in VIDEOS:
  try:
   x=json.loads(p.read_text());videos.append({'path':str(p.parent.relative_to(ROOT)),'status':x['status'],'moves':len(x['moves']),'outcome':x.get('outcome'),'error':x.get('error')})
  except (OSError,ValueError,KeyError):videos.append({'path':str(p.parent.relative_to(ROOT)),'status':'not_started'})
  try:videos[-1]['verification']=json.loads((p.parent/'verification.json').read_text())['status']
  except (OSError,ValueError,KeyError):pass
 recapture=collections.Counter()
 try:
  q=json.loads((ROOT/'.local/native-gnu-audit/recapture-match/series.json').read_text())
  for g in q['games']:
   if g['status']=='complete':
    w=g['outcome']['winner'];recapture['draw' if w is None else 'original' if w==g['gnu_side'] else 'fix']+=1
   else:recapture[g['status']]+=1
 except (OSError,ValueError,KeyError):pass
 patched=collections.Counter()
 try:
  q=json.loads((ROOT/'.local/native-gnu-audit/recapture-vs-yane/series.json').read_text())
  for g in q['games']:
   if g['status']=='complete':
    w=g['outcome']['winner'];patched['draw' if w is None else 'fix' if w==g['gnu_side'] else 'yaneuraou']+=1
   else:patched[g['status']]+=1
 except (OSError,ValueError,KeyError):pass
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
 data={'updated_jst':now.isoformat(),'score':dict(score),'series':observed,'suisho5':analysis,'recapture_test':dict(recapture),'recapture_vs_yane':dict(patched),'videos':videos}
 temp=OUT/'progress.tmp';temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(OUT/'progress.json')
 lines=['# 対局・水匠5解析・録画の進行状況','',f"更新: {now.strftime('%Y-%m-%d %H:%M:%S JST')}",'',f"正常終局: やねうら王 {score['yaneuraou']}勝、GNU {score['gnu']}勝、引分 {score['draw']}。進行中 {score['running']}、異常 {score['abnormal']}、同一開始盤面の除外 {score['duplicate_excluded']}。",'',f"水匠5で解析済み: {analysis.get('games',0)}局。棋譜が終局した後に順次解析するため、対局数より遅れる場合がある。",'',f"原版と取り返し修正版の参考対局: 原版 {recapture['original']}勝、修正版 {recapture['fix']}勝、引分 {recapture['draw']}、進行中 {recapture['running']}。",'',f"取り返し修正版と86Boxやねうら王の参考対局: 修正版 {patched['fix']}勝、やねうら王 {patched['yaneuraou']}勝、引分 {patched['draw']}、進行中 {patched['running']}（補充対局の後に開始）。",'','撮影:']
 for x in videos:lines.append(f"- {x['path']}: {x['status']} / {x.get('moves',0)}手"+(f" / 検証 {x['verification']}" if x.get('verification') else '')+(f" / {x['error']}" if x.get('error') else ''))
 if analysis.get('statistics'):
  v=analysis['statistics']
  lines+=['',f"水匠5の連続数値評価の変化: GNU {v['gnu']['count']}手中、指し手側評価が200以上低下 {v['gnu']['loss_ge_200']}手。やねうら王 {v['yaneuraou']['count']}手中 {v['yaneuraou']['loss_ge_200']}手。詰み評価をまたぐ手は除外。値は固定ノード探索による推定で、厳密な失着判定ではない。"]
 lines+=['','[調査報告](../../docs/gnu-shogi-suisho5-investigation.md) / [評価値グラフ（先頭6局）](evaluation-trajectories.png) / [解析集計](summary.json) / [機械可読の進捗](progress.json)','','解析と撮影は対局と並行する。暫定値であり、異常・未完了・重複する開始盤面を勝敗に数えない。']
 t=OUT/'progress-md.tmp';t.write_text('\n'.join(lines)+'\n');t.replace(OUT/'progress.md')
while True:
 run()
 if datetime.datetime.now(datetime.timezone.utc)>=DEADLINE+datetime.timedelta(seconds=60):break
 time.sleep(30)
