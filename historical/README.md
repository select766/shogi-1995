# GNU Shogi 1.2p03 — 研究エンジンの比較対象

リポジトリルートから実行する。GNU Shogiは外部比較対象であり、研究エンジンやモデルを置き換えない。[選定・互換修正・時間制御・過去の検証結果](../docs/historical-engine-validation.md)も参照。

## ソースからの構築

ホストに Python 3、GCC 11.4.0、make、patch、tar、e2fsprogs（mke2fs/debugfs）、QEMU（qemu-system-i386）、flock が必要。rootやホストへの旧ライブラリのインストールは不要。

```bash
bash historical/setup.sh
# 必要なアーカイブがすべてキャッシュされている場合
bash historical/setup.sh --offline
```

`assets.json` に固定した取得先・容量・SHA-256を検証してから展開する。`historical/downloads/` を使い、既存の `.local/downloads/` に同一ファイルがあれば読取りで再利用する。独立クローンの展開済みディレクトリやバイナリは不要。

処理の内訳:

1. `prepare.py`: GNU Shogi 1.2p03とSlackware 3.0のGCC 2.7.0、binutils、libc等を展開。`compatibility.patch` を適用し、Linux 1.2.13のヘッダー、libcのシンボリックリンク、専用initを構築する。当時のパッケージの `install/doinst.sh` はホストで実行しない。
2. `build-modern-objects.sh`: 現代GCCで旧ヘッダーを使って32bitオブジェクトを構築。128MiBの専用ext2ディスクを作る。
3. `guest-build.sh` / `guest-build.py`: 専用QEMU内で旧GCC版をビルド。両版とも旧GCCドライバ・旧binutils・libc 5.0.9でリンク。中継プロセスも旧GCCで構築。ゲストをsyncし、ルートをread-onlyへ再マウントしてからVMを終了する。これはLinux 1.2の未書込みデータを残さないために必要。
4. `write-manifests.py`: バイナリ、ディスク、カーネル、パッチ、ビルドスクリプト、実際のコンパイラ版のハッシュ・識別情報を保存する。

最適化は旧版 `-O2 -funroll-loops -m486`、現代版 `-O2 -funroll-loops -m32 -march=i486 -mtune=i486`。現代版はGNU89/common/inlineの互換設定を加え、PIEとstack protectorを無効化する。別のGCCを使う場合は `GNU_SHOGI_ALLOW_DIFFERENT_GCC=1 bash historical/setup.sh` と明示し、別コンパイラの結果として扱う。互換ファイル名 `gnushogi-gcc1140` は維持するが、manifestとUSIの名前は実際のコンパイラ版を記録する。

`manifest-old.json` / `manifest-modern.json` はビルドごとの生成物。VMのファイルシステム日時等が異なるため、イメージ全体のbit単位の再現は保証しない。入力・修正・設定を固定し、各構築結果をハッシュで識別する。

**バイナリ・ディスク・展開済みソース・旧コンパイラ・ダウンロード・実行ログ・生成manifestは `.gitignore` で除外する。** Git管理対象はコード、パッチ、入力manifest、文書、少量の検証用テキスト証跡。研究用の `scripts/setup.sh` や `build-engine.sh` は呼ばない。再構築はこの比較対象の生成領域だけを作り直す。

## USI起動と検証

Python依存は `requirements-evaluation.txt` と共通。既存venv、または同ファイルから作成した環境を使用する。

```bash
PY="$PWD/.local/venv/bin/python"
# Pentium 100MHzで比較。既存の86Box実行ファイル・ROM・ブートフロッピーを読取り利用
"$PY" historical/usi.py --backend 86box --compiler old
# QEMUは動作確認用。Pentiumの性能測定には使用しない
"$PY" historical/usi.py --backend qemu --compiler modern
# 両コンパイラ版の履歴・成り・駒打ち・時間指定とエラー処理を検証
"$PY" historical/test-protocol.py
```

各VMのディスク・シリアル・Xサーバー・ログは専用。通常のUSI例:

```text
usi
isready
usinewgame
position startpos moves 7g7f 3c3d
go btime 0 wtime 0 byoyomi 2000
quit
```

2秒はGNU側で `level 0 0:02` として設定する。通信マージンの差引きなし。ただし歴史的な1000ノードごとの時間確認と最低深さにより超過する。過去の86Box試験ではホスト時間2.25〜2.62秒で、既存評価の2200ms閾値を全件超過した。厳密な2秒上限を保証するエンジンではない。`stop` も即時ではない。未対応の非整数秒・Fischer等はエラーにして条件の取り違えを防ぐ。

## 正解率評価

```bash
"$PY" historical/evaluate.py \
  --dataset .local/evaluation-data-repro/quick.jsonl \
  --output historical/results/gnu-old-quick-86box.json --backend 86box --compiler old
```

既存評価器の採点・合法手・時間超過判定を使用する。`--no-history` により研究の測定履歴へ自動登録しない。接続試験には別の出力先で `--limit 4 --backend qemu` を指定する。出力済みの結果は上書きしない。

## 凍結済み研究エンジンとの対局

```bash
"$PY" historical/match-frozen.py \
  --candidate-manifest manifests/halfkp-fixed-w8-h0-128m-radix-v1-candidate.json \
  --output-dir historical/results/vs-frozen-radix-86box \
  --backend 86box --compiler old --opening '7g7f 3c3d'
```

比較相手は明示した凍結manifestで固定し、image SHAを照合する。`--prepare-only` は実行引数の保存だけ。短い接続試験には `--backend qemu --depth 2 --max-plies 8`。先後入替2局で、短手数打切りの勝敗を棋力測定にしない。

任意のUSIエンジン同士は `match.py --a '<JSON argv>' --b '<JSON argv>' --output <新規JSON>`。通常は2秒/手、明示的な200ms超過許容。GNUの時間超過はそのまま記録する。再現用に開始局面・時間条件・両エンジンの識別情報を保存し、同一の決定的な開始局面の反復を独立な標本として数えない。
