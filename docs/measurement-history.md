# エンジンの測定履歴

初期PSQT・tiny-v1〜v7はqsearch未適用の試作。適切な前処理と十分な学習を行うHalfKP基準とは区別する。以後の強化順序は[HalfKP開発方針](halfkp-development.md)を参照。

各行は完走した一回の測定。同じ `comparison_group` の行は、評価局面・標本数・時間またはノード数・共通オプション・実行環境が同じ。異なる条件の一致率を一つの成績系列として接続しない。

[CSV](../results/measurement-history.csv) / [JSON](../results/measurement-history.json) / [時系列グラフ（SVG）](../results/measurement-history.svg)。グラフの横軸には `finished_at_utc`、縦軸には `accuracy_percent` を使い、`comparison_group` で系列を分ける。レーティングは未測定のため空欄。

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
| 11/06 11:49:18 | [tiny-v7-sym-early](../results/2026-11-06/tiny-v7-sym-early-20261106T024918430625Z-tiny-v7-sym-early-86box-quick256.json) | 86box / 2000ms / quick 256局面 | 90/256 | 35.16% (29.57–41.19) | `b40cc88` | 左右対称・幅32の線形出力、量子化なし学習でepoch途中のcheckpointを選択 |
| 11/06 12:00:28 | [tiny-v3-small](../results/2026-11-06/tiny-v3-small-20261106T030028879349Z-tiny-v3-small-86box-quick256.json) | 86box / 2000ms / quick 256局面 | 90/256 | 35.16% (29.57–41.19) | `52ab271` | 1600万局面、全玉位置特徴、幅8・隠れ8へ縮小して128乗算 |
| 11/06 12:11:38 | [tiny-v5-sym-dense](../results/2026-11-06/tiny-v5-sym-dense-20261106T031138249268Z-tiny-v5-sym-dense-86box-quick256.json) | 86box / 2000ms / quick 256局面 | 85/256 | 33.20% (27.72–39.18) | `52ab271` | 1600万局面、左右対称95400特徴、幅16・隠れ8の256乗算 |
| 11/06 12:25:47 | [material-nopic-v1](../results/2026-11-06/material-nopic-v1-20261106T032547540093Z-material-nopic-v1-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 76/256 | 29.69% (24.42–35.55) | `859cc2e` | 駒得評価のみ、静的PentiumビルドからPIC処理を除去 |
| 11/06 12:25:53 | [tiny-v7-nopic](../results/2026-11-06/tiny-v7-nopic-20261106T032553408899Z-tiny-v7-nopic-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 91/256 | 35.55% (29.94–41.58) | `859cc2e` | tiny-v7と同じ学習重み、静的PentiumビルドからPIC処理を除去 |
| 11/06 12:25:58 | [tiny-v3-nopic](../results/2026-11-06/tiny-v3-nopic-20261106T032558827475Z-tiny-v3-nopic-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 84/256 | 32.81% (27.35–38.78) | `859cc2e` | tiny-v3と同じ学習重み、静的PentiumビルドからPIC処理を除去 |
| 11/06 12:43:22 | [material-v1](../results/2026-11-06/material-v1-20261106T034322121755Z-000-baseline.json) | 86box / 2000ms / development 256局面 | 80/256 | 31.25% (25.88–37.17) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 12:54:36 | [tiny-v7-nopic-usi](../results/2026-11-06/tiny-v7-nopic-usi-20261106T035436933139Z-000-candidate.json) | 86box / 2000ms / development 256局面 | 89/256 | 34.77% (29.20–40.79) | `859cc2e` | tiny-v7と同じ学習重み、静的PentiumビルドからPIC処理を除去、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 13:05:48 | [tiny-v7-nopic-usi](../results/2026-11-06/tiny-v7-nopic-usi-20261106T040548110864Z-001-candidate.json) | 86box / 2000ms / development 256局面 | 79/256 | 30.86% (25.52–36.77) | `859cc2e` | tiny-v7と同じ学習重み、静的PentiumビルドからPIC処理を除去、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 13:16:59 | [material-v1](../results/2026-11-06/material-v1-20261106T041659162931Z-001-baseline.json) | 86box / 2000ms / development 256局面 | 65/256 | 25.39% (20.45–31.06) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 14:54:16 | [halfkp-linear-v2](../results/2026-11-06/halfkp-linear-v2-20261106T055416615380Z-halfkp-linear-v2-native-nodes10000-quick256.json) | native / 10000 nodes / quick 256局面 | 80/256 | 31.25% (25.88–37.17) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算 |
| 11/06 15:06:45 | [material-v1](../results/2026-11-06/material-v1-20261106T060645436810Z-000-baseline.json) | 86box / 2000ms / development 256局面 | 80/256 | 31.25% (25.88–37.17) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 15:17:58 | [halfkp-linear-v2-usi](../results/2026-11-06/halfkp-linear-v2-usi-20261106T061758679873Z-000-candidate.json) | 86box / 2000ms / development 256局面 | 86/256 | 33.59% (28.09–39.58) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 15:29:07 | [halfkp-linear-v2-usi](../results/2026-11-06/halfkp-linear-v2-usi-20261106T062907830923Z-001-candidate.json) | 86box / 2000ms / development 256局面 | 88/256 | 34.38% (28.83–40.39) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 15:40:14 | [material-v1](../results/2026-11-06/material-v1-20261106T064014984754Z-001-baseline.json) | 86box / 2000ms / development 256局面 | 65/256 | 25.39% (20.45–31.06) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 15:51:21 | [material-v1](../results/2026-11-06/material-v1-20261106T065121975777Z-002-baseline.json) | 86box / 2000ms / development 256局面 | 75/256 | 29.30% (24.06–35.15) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 16:02:31 | [halfkp-linear-v2-usi](../results/2026-11-06/halfkp-linear-v2-usi-20261106T070231076244Z-002-candidate.json) | 86box / 2000ms / development 256局面 | 86/256 | 33.59% (28.09–39.58) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 16:13:40 | [halfkp-linear-v2-usi](../results/2026-11-06/halfkp-linear-v2-usi-20261106T071340731403Z-003-candidate.json) | 86box / 2000ms / development 256局面 | 79/256 | 30.86% (25.52–36.77) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 16:13:40 | [halfkp-linear-v2-usi](../results/2026-11-06/halfkp-linear-v2-usi-20261106T071340731403Z-candidate.json) | 86box / 2000ms / development 1024局面 | 339/1024 | 33.11% (30.29–36.05) | `43495b9` | 標準HalfKP純線形125388係数、qsearch済み63977434局面、40epochでloss飽和確認・最良29epoch、評価時に76特徴を再加算、USI通常起動でも同じ評価ファイルを自動設定 |
| 11/06 16:24:51 | [material-v1](../results/2026-11-06/material-v1-20261106T072451072756Z-003-baseline.json) | 86box / 2000ms / development 256局面 | 74/256 | 28.91% (23.70–34.74) | `06219a9` | 駒得評価の基準版（学習なし） |
| 11/06 16:24:51 | [material-v1](../results/2026-11-06/material-v1-20261106T072451072756Z-baseline.json) | 86box / 2000ms / development 1024局面 | 294/1024 | 28.71% (26.02–31.56) | `06219a9` | 駒得評価の基準版（学習なし） |

反則・異常終了・時間超過の件数、モデル・バイナリ・イメージのSHA、共通設定、対応あり比較の元になる各局面の指し手はCSV/JSONおよびリンク先の明細に保存する。
