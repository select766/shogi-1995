# GNU Shogi: 6手目△3三角（2b3c）の調査

対象: `startpos moves 2g2f 3c3d 2f2e 5a6b 2e2d`（録画用平手対局 recording-gnu-gote-02 の6手目、GNU後手）。

- `gnu-30s-move6.txt`: GNU（新規プロセス）に30秒読ませた反復深化ログ。`historical/gnu-position-probe.py`。
- `gnu-20s-after-2c2d.txt`: △同歩▲同飛 の局面と、さらに △2三歩▲3四飛 の局面を GNU に20秒読ませたログ。
- `suisho5-5M.txt`: 水匠5（500万ノード、MultiPV 4）による同じ局面群の評価。`historical/suisho5-position-probe.py`（`.local/suisho5-analysis` で実行）。
- `../gnu-timecontrol-audit/result.json`: 対局と同じく1プロセスで2,4,6手目を順に探索し、`level 0 0:10`（1手10秒固定）と `level 1 0:10`（1手ごとの持ち時間制）を各3回比較。`historical/gnu-timecontrol-audit.py`。

評価値は手番側から見た値（GNUは後手視点、水匠5は各局面の手番視点）。
