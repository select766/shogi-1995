# エンジンの測定履歴

各行は完走した一回の測定。同じ `comparison_group` の行は、評価局面・標本数・時間またはノード数・共通オプション・実行環境が同じ。異なる条件の一致率を一つの成績系列として接続しない。

[CSV](../results/measurement-history.csv) / [JSON](../results/measurement-history.json)。グラフの横軸には `finished_at_utc`、縦軸には `accuracy_percent` を使い、`comparison_group` で系列を分ける。レーティングは未測定のため空欄。

86BoxはPentium 100 MHz・RAM 32 MiB、実時間評価は通常の秒読み2秒。NetworkDelayとNetworkDelay2はともに0。nativeの固定ノード試験はホスト診断であり、Pentiumの実時間評価とは分ける。機械構成と依存物は評価計画およびassets manifestに固定する。

日時の†は、旧結果ファイルの更新日時と所要時間から復元した概算。以後は開始・終了UTCを測定器自身が記録する。ソースコミットが未特定の旧試作は「未確定」とし、実行ファイル・モデル・ソースツリーのSHAで追跡する。測定器のコミットとソースのコミットはCSVに別々に記録する。

| 測定終了日時（JST） | エンジン | 条件 / 集合 | 一致数 | 一致率（Wilson 95%） | ソースcommit | 主な機能差分 |
| --- | --- | --- | ---: | ---: | --- | --- |
| 11/06 10:11:55† | [material-v1](../results/2026-11-06/material-v1-smoke32.json) | 86box / 2000ms / quick 32局面 | 12/32 | 37.50% (22.93–54.75) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 10:22:10† | [psqt-v2](../results/2026-11-06/psqt-v2-smoke32.json) | 86box / 2000ms / quick 32局面 | 8/32 | 25.00% (13.25–42.11) | 未確定 | 新規学習した左右対称の駒位置・持ち駒637係数 |
| 11/06 10:36:29† | [material-v1](../results/2026-11-06/material-v1-quick256.json) | 86box / 2000ms / quick 256局面 | 80/256 | 31.25% (25.88–37.17) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 10:41:24† | [tiny-v1](../results/2026-11-06/tiny-v1-smoke32.json) | 86box / 2000ms / quick 32局面 | 7/32 | 21.88% (11.02–38.75) | `6532b40` | 新規学習の玉位置条件付き16×16ネットワーク、全特徴再加算 |
| 11/06 10:42:28† | [material-v1](../results/2026-11-06/material-v1-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 76/256 | 29.69% (24.42–35.55) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 10:43:26† | [psqt-v2](../results/2026-11-06/psqt-v2-native-nodes10000-quick256-v2.json) | native / 10000 nodes / quick 256局面 | 78/256 | 30.47% (25.15–36.36) | 未確定 | 新規学習した左右対称の駒位置・持ち駒637係数 |
| 11/06 10:43:31† | [tiny-v1](../results/2026-11-06/tiny-v1-native-nodes10000-quick256-v2.json) | native / 10000 nodes / quick 256局面 | 72/256 | 28.12% (22.97–33.92) | `6532b40` | 新規学習の玉位置条件付き16×16ネットワーク、全特徴再加算 |
| 11/06 11:02:09 | [tiny-v1-ancestor](../results/2026-11-06/tiny-v1-ancestor-20261106T020209466701Z-tiny-v1-ancestor-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 72/256 | 28.12% (22.97–33.92) | `e04f6fc` | tiny-v1と同じ重み、玉移動時の再計算と最大8手の祖先差分更新 |
| 11/06 11:02:14 | [tiny-v2](../results/2026-11-06/tiny-v2-20261106T020214773163Z-tiny-v2-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 83/256 | 32.42% (26.98–38.38) | `e04f6fc` | 新規学習を1600万局面へ拡張、16×16の玉位置条件付き評価と祖先差分更新 |
| 11/06 11:04:37 | [tiny-v1-ancestor](../results/2026-11-06/tiny-v1-ancestor-20261106T020437624490Z-tiny-v1-ancestor-86box-quick32.json) | 86box / 2000ms / quick 32局面 | 9/32 | 28.12% (15.56–45.37) | `e04f6fc` | tiny-v1と同じ重み、玉移動時の再計算と最大8手の祖先差分更新 |
| 11/06 11:15:51 | [tiny-v2](../results/2026-11-06/tiny-v2-20261106T021551626893Z-tiny-v2-86box-quick256.json) | 86box / 2000ms / quick 256局面 | 82/256 | 32.03% (26.62–37.98) | `e04f6fc` | 新規学習を1600万局面へ拡張、16×16の玉位置条件付き評価と祖先差分更新 |
| 11/06 11:27:30 | [tiny-v3-small](../results/2026-11-06/tiny-v3-small-20261106T022730550025Z-tiny-v3-small-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 84/256 | 32.81% (27.35–38.78) | `52ab271` | 1600万局面、全玉位置特徴、幅8・隠れ8へ縮小して128乗算 |
| 11/06 11:27:36 | [tiny-v4-sym-linear](../results/2026-11-06/tiny-v4-sym-linear-20261106T022736434124Z-tiny-v4-sym-linear-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 80/256 | 31.25% (25.88–37.17) | `52ab271` | 1600万局面、左右対称95400特徴、幅32・隠れなしの64乗算 |
| 11/06 11:27:42 | [tiny-v5-sym-dense](../results/2026-11-06/tiny-v5-sym-dense-20261106T022742222343Z-tiny-v5-sym-dense-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 87/256 | 33.98% (28.46–39.99) | `52ab271` | 1600万局面、左右対称95400特徴、幅16・隠れ8の256乗算 |
| 11/06 11:33:15 | [tiny-v6-sym-qat](../results/2026-11-06/tiny-v6-sym-qat-20261106T023315941870Z-tiny-v6-sym-qat-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 75/256 | 29.30% (24.06–35.15) | `b40cc88` | 左右対称・幅32の線形出力、量子化を含めて新規学習し途中validationで選択 |
| 11/06 11:33:21 | [tiny-v7-sym-early](../results/2026-11-06/tiny-v7-sym-early-20261106T023321838376Z-tiny-v7-sym-early-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 91/256 | 35.55% (29.94–41.58) | `b40cc88` | 左右対称・幅32の線形出力、量子化なし学習でepoch途中のcheckpointを選択 |

反則・異常終了・時間超過の件数、モデル・バイナリ・イメージのSHA、共通設定、対応あり比較の元になる各局面の指し手はCSV/JSONおよびリンク先の明細に保存する。
