# 補助対局の測定履歴

[CSV](../results/match-history.csv) / [JSON](../results/match-history.json) / [一致率の履歴](measurement-history.md)。

完走したPentium実時間対局を記録する。横軸は`finished_at_utc`、縦軸は`elo_difference`または`score_percent`を使い、`comparison_group`が同じ行だけを接続する。Eloは固定相手・同じ持ち時間に対する換算差で、リーグのレーティングではない。

先後2局を1組とする保守的な95%区間。全勝・全敗で有限値が得られない端点はCSVの境界ラベルで示す。運用異常のある完走結果は記録するが、Eloは付けない。固定ノードの動作試験と未完了対局は含めない。

| 終了日時（JST） | 候補 / 相手 | 条件 | 勝–分–敗 | 得点率 | Elo換算差（95%） | ソースcommit | 主な機能差分 |
| --- | --- | --- | --- | ---: | --- | --- | --- |

実時間の最終20局はまだ未実施。測定値は登録されていない。
