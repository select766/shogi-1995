# 最終候補の固定と検証手順

**2026年11月7日の指示変更：進行中の独立4,096局面の一致率検証と集計後に一旦停止する。以下に記した20局・大会時間2局・既定構成への反映は自動実行しない。再開後は[電竜戦向けの今後の予定](denryu-next-steps.md)に従い、動作検証を優先する。** 元の固定実行計画は変更前の履歴として保持する。

この文書は実行手順であり、検証完了の記録ではない。実測結果は測定履歴と各結果JSONで確認する。現在のdevelopment測定が終了するまで、ここにあるVMの起動・ファイルの複製・追加測定は実行しない。

## 候補固定前

1. [変更後の進行条件](../manifests/halfkp-fixed-model-optimization-schedule-v1.json)に従い、モデル構造の探索を11月7日10:00 JSTまでに終了する。元の全11工程の正常終了は要求せず、期限による停止と故障を区別して保存する。完了した全件測定だけを選択に使い、出力の存在だけでは完了としない。既存キューは09:59に停止し、終了を確認してから追加の重い処理へ進む。
2. 全1,024局面の一致数・対応あり区間・運用異常を比較する。従来の汎用演算版も候補に残す。対照の繰返しを独立標本として合算しない。128百万件版はデータ量と延べ学習量の両方を増やした実験として扱う。
   [モデル固定の計画](../manifests/halfkp-model-freeze-plan-v1.json)と[`freeze-halfkp-model.py`](../scripts/freeze-halfkp-model.py)は09:58に全件測定済みの候補だけを選ぶ。4つの候補ブロックがすべて完了していれば、対照の最後のブロックが未完了でも候補単独の1,024件として集計できる。その場合は対応あり比較・区間を完成したとは扱わず、元ブロックのSHAとこの制限を固定記録に残す。同数ならモデル容量・層数・事前の優先順で決める。[検証](../results/2026-11-07/halfkp-model-freeze-selector-validation-v1.json)では正常な4ブロックと6種類の不正な明細、未完了・欠落・モデル不一致のブロックを確認した。
3. 追加の累積加算最適化を試す場合は、選んだ重みを変えず、quick256・10,000ノード・64局面AB/BAで従来推論版と比較する。全探索結果の一致、運用異常0、時間短縮率中央値の対応あり95%区間の下限が正、4ブロックすべての中央値が正であることを確認する。その後、通常2秒の全developmentで比較する。候補固定の時間を確保できない場合は追加最適化を採用しない。
4. 2026年11月7日10:00 JSTまでにモデルの構造・重みを1個に固定し、15:00 JSTまではそのモデルのまま演算や探索処理を改善する。モデル固定時に形状・重みSHA・学習入力・seed・収束条件と選択理由を保存する。推論版の選択後、manifest・バイナリ・イメージ・推論ソースと測定器のcommit/SHAも固定する。独立testの前に最終推論版を1個に絞り、testを使った構造・重み・演算の調整を行わない。

## 独立testと実対局

以下の`FINAL_MANIFEST`には、固定記録に保存した候補manifestを指定する。各出力先は新規とし、失敗や途中結果を上書きしない。重い処理を同時実行せず、順に実行する。

```bash
PYTHON=.local/venv/bin/python
DATA=/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1
BASELINE=config/evaluation/material-v1-frozen.json
# FINAL_MANIFEST=固定済み候補manifestのパス
```

主評価は、保存済みdevelopmentの駒得結果を流用せず、駒得基準を改めて同条件で測る。

```bash
"$PYTHON" scripts/evaluate-pair.py \
  --baseline "$BASELINE" --candidate "$FINAL_MANIFEST" \
  --dataset "$DATA/test.jsonl" \
  --output .local/evaluation/final-heldout-4096-v1 \
  --block-size 256 --milliseconds 2000
```

全4,096局面・通常秒読み2秒、Threads 1・Hash 2 MiB・NetworkDelay/NetworkDelay2=0、Pentium 100 MHz・RAM 32 MiBであることを実測記録から確認する。基準との差が+2 pp以上、対応あり95%区間の下限が正、運用異常0が採用条件。条件を満たさない場合も結果を保存し、testに合わせて再学習・再選抜しない。比較JSONも`results`へ保存する。

補助対局は固定matchの先頭10局面を先後入れ替えて20局行う。

```bash
"$PYTHON" scripts/play-match.py \
  --baseline "$BASELINE" --candidate "$FINAL_MANIFEST" \
  --dataset "$DATA/match.jsonl" --openings 10 \
  --initial-ms 180000 --increment-ms 2000 --max-plies 512 \
  --network-delay 120 --network-delay2 1120 \
  --output .local/evaluation/final-auxiliary-20-v1.json
```

2台のVMの同時5秒探索を各3回校正し、ホスト・ゲストの時計が±2%内であることを確認してから対局する。校正失敗時の結果を棋力測定として扱わない。正常完了した実時間対局はrunnerが履歴へ登録する。原記録と履歴の一致、全20局の結果・反則・切断・時間切れ、Eloの区間と少数対局の限界を確認する。

大会時間での動作確認は、平手から先後を入れ替えた2局で行う。

```bash
"$PYTHON" scripts/play-match.py \
  --baseline "$BASELINE" --candidate "$FINAL_MANIFEST" \
  --dataset config/evaluation/tournament-startpos-v1.jsonl \
  --openings 1 --tournament-clock \
  --network-delay 120 --network-delay2 1120 \
  --output .local/evaluation/final-tournament-operational-2-v1.json
```

先手3分・後手10分・双方1手2秒加算、512手上限・入玉27点法を確認する。この2局は非対称時間の稼働試験であり、Eloへ算入しない。

## 既定構成への反映

採用条件と実対局の稼働確認を満たした場合、現在の`.local/images/engine-root.ext2`をSHA付きでバックアップし、検証した候補イメージを同じディレクトリの一時ファイルへ複製する。SHA一致を確認してからatomic renameで置き換える。モデルやバイナリを別途組み直して差し替えない。起動中のVMがないことを確認して実施する。

```bash
"$PYTHON" tests/usi_smoke.py \
  --image .local/images/engine-root.ext2 \
  --output results/2026-11-08/final-default-usi-lifecycle-v1.json
```

実際の既定イメージのSHA・ELFと固定候補の一致、USI開始・評価関数ロード・RAM/swap・着手・大会時間のgo/stop・512手の履歴受信・終了を確認する。別プロセスからの再起動も確認する。`go infinite`は明示stopの動作確認だけに使い、時計校正や強さの測定には使わない。

最後にREADME・稼働手順・検証記録・学習再現手順へ採用候補と限界を反映し、測定日時・条件・commit・主な差分・結果の表とCSV/JSONを確認してcommitする。ShogiHomeの人手による新モデルの対局確認を、CLI試験だけで実施済みとは記載しない。

## 2026年11月7日の実行準備

モデルは09:58にD42へ固定済み。最後の開発比較は14:37に正常終了し、出力積和のradix版401/1,024、対照C30の最新399/1,024だった。固定ルールの選定器を14:59:30に実行してから、[最終検証の固定計画](../manifests/halfkp-final-verification-execution-plan-v1.json)を順に実行する。選定記録が予定したradix版のprofile・エンジン・モデルSHAと異なる場合、testの評価開始前に停止する。

この計画は独立4,096局面を新たな駒得対照と比較し、+2 pp以上・paired 95%下限が正・運用異常0を確認してから、20局の対称時計対局、2局の大会時計の稼働確認へ進む。testに合わせてモデル・演算を選び直さない。いずれかの工程が失敗した場合は原記録を保存して停止し、結果を上書きしない。既定イメージの反映と実際のdefaultの再起動・USI確認は、全採用条件と実対局が通過してから行う。現在は未実行であり、開始・終了・判定は実際のジョブstateと結果JSONで確認する。
