#!/usr/bin/env python3
"""Snapshot a truthful final report when requested workers finish or at 09:00 JST."""
import datetime,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/suisho5-native-gnu-live'
DEADLINE=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

def read(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return {}

def write(final):
 progress=read(OUT/'progress.json');score=progress.get('score',{});analysis=progress.get('suisho5',{});stats=analysis.get('statistics',{});rec=progress.get('recapture_test',{});patched=progress.get('recapture_vs_yane',{});videos=progress.get('videos',[])
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
 text=['# GNU Shogi 対やねうら王・水匠5調査 最終集計' if final else '# GNU Shogi 対やねうら王・水匠5調査 途中集計','',f"集計時刻: {now.strftime('%Y-%m-%d %H:%M:%S JST')}（元進捗: {progress.get('updated_jst','不明')}）",'',f"正常終局: やねうら王 {score.get('yaneuraou',0)}勝、GNU {score.get('gnu',0)}勝、引分 {score.get('draw',0)}。未完了 {score.get('running',0)}、異常 {score.get('abnormal',0)}、同一開始盤面の除外 {score.get('duplicate_excluded',0)}。100正常局に到達していなければ未達として扱う。",'',f"水匠5評価関数を用いた解析は {analysis.get('games',0)} 局。対局終了と解析終了の間に差がある場合がある。"]
 if stats:
  g=stats.get('gnu',{});y=stats.get('yaneuraou',{})
  text += ['',f"連続する数値評価の変化では、GNU {g.get('count',0)}手中 {g.get('loss_ge_200',0)}手、やねうら王 {y.get('count',0)}手中 {y.get('loss_ge_200',0)}手で指し手側の評価が200以上低下した。固定ノードで別々に探索した概算であり、詰み評価をまたぐ手は除外。局面間の相関や評価誤差がある。"]
 text += ['',f"原版と取り返し修正版の直接対局: 原版 {rec.get('original',0)}勝、修正版 {rec.get('fix',0)}勝、引分 {rec.get('draw',0)}、未完了 {rec.get('running',0)}。小標本の参考値。",'',f"修正版と86Boxやねうら王: 修正版 {patched.get('fix',0)}勝、やねうら王 {patched.get('yaneuraou',0)}勝、引分 {patched.get('draw',0)}、未完了 {patched.get('running',0)}。",'','撮影結果:']
 for v in videos:text.append(f"- {v['path']}: {v['status']}、{v.get('moves',0)}手、検証 {v.get('verification','未完了')}"+(f"、エラー {v['error']}" if v.get('error') else ''))
 text += ['','開始局面は先頭6局ではほぼ互角だったが、GNUの着手後に水匠5評価が大きく下がる例が複数あった。取り返し延長の原版バグと、置換表初期化の問題は確認できたが、この限定的な対照試験だけで勝敗の原因を一つに特定できない。GNUの探索・評価設計と現代の学習済み評価関数の差、時間や内部状態なども寄与し得る。水匠5は絶対的な正解ではなく、比較対象とやねうら王系の探索を共有する。','', '[調査本文・方法・具体例](../../docs/gnu-shogi-suisho5-investigation.md) / [評価推移（先頭6局）](evaluation-trajectories.png) / [解析集計](summary.json) / [各種進捗](progress.md)','','元の棋譜・映像・ログは `.local/native-gnu-evaluation-20261107/`、`.local/native-gnu-evaluation-20261107-worker2/`、`.local/native-gnu-evaluation-supplement/`、`.local/match-video/` に保存。早送り・テロップなどの30秒編集は行っていない。']
 p=OUT/'final-report.tmp';p.write_text('\n'.join(text)+'\n');p.replace(OUT/('final-report.md' if final else 'interim-report.md'))
while True:
 progress=read(OUT/'progress.json');s=progress.get('score',{});v=progress.get('videos',[]);count=sum(s.get(k,0) for k in ('gnu','yaneuraou','draw'))
 patched=progress.get('recapture_vs_yane',{});patched_done=sum(patched.get(k,0) for k in ('fix','yaneuraou','draw'))>=6
 rec=progress.get('recapture_test',{});rec_done=sum(rec.get(k,0) for k in ('original','fix','draw'))>=6
 done=count>=100 and progress.get('suisho5',{}).get('games',0)>=100 and patched_done and rec_done and len(v)==2 and all(x.get('verification')=='pass' for x in v)
 if done or datetime.datetime.now(datetime.timezone.utc)>=DEADLINE+datetime.timedelta(seconds=45):
  write(True);break
 write(False);time.sleep(30)
