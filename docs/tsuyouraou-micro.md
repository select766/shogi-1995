# つようら王11microの互換性試験

2026-11-08。配布記事の指定は `SFNN_ka2_2048_8_64_progress8`、`FV_SCALE=24`。リポジトリのコミット `c41d684bda1f130df7adc8beee0397ea69c1ed82` にある公開やねうら王由来のソースから、既存エンジンと独立してLinux x86-64ネイティブ版をビルドした。ソースには本プロジェクトの移植変更も含む。

```bash
bash scripts/build-tsuyouraou-micro-native.sh
.local/tsuyouraou-micro/yaneuraou-native
```

AVX2対応CPUが必要。`private/tsuyouraou/` の配布アーカイブ、7z、Python 3、g++、makeが必要。出力は `.local/tsuyouraou-micro/` 内に限定する。エンジンの `EvalDir` 初期値は実行ファイル隣の `eval` で、配布物の `eval_options.txt` が `FV_SCALE=24` を設定する。再ビルドのログは同ディレクトリの `build.log`。

同梱の `nn.bin` と `progress.bin` を読み込み、USIの `isready` が完了した。1スレッド、Hash 16 MiB、定跡なし、各10,000ノードの試験で、平手は `2g2f`、`7g7f 3c3d 2g2f` の局面は `8c8d` を返した。生ログは `.local/tsuyouraou-micro/native-smoke.log`。これは読み込み・探索の動作確認で、評価値の独立検証や棋力測定ではない。

進行度ファイルは125,388個のlittle-endian doubleで、実装の外部 `progress.bin` 形式に一致する。`source/eval/nnue/architectures/README.md` の埋め込み形式の記述は現行実装と食い違っている。実装と `tools/memo/progress-format.md` を参照。

配布アーカイブのSHA-256は `d1326e9a620c30d40ae553259dd0b6828d2f4e9fca3b6ab9440566579ab0e8c2`、`nn.bin` は `7f9545dbf73b87acf312146daabf59c4f17d0845c87d587fa19caed51707dddb`、`progress.bin` は `a2d18f0564639c945b5d6469e9b437cd64a526ad4fbcef02ab1d8f547d08e5f1`。

## 86Box / ShogiHome版

専用起動先をShogiHomeのエンジン実行ファイルとして登録する。

```text
/home/select766/shogi/shogi-1995/.local/shogihome/tsuyouraou-micro-v1/run.sh
```

ShogiHomeの最大起動待ち時間は120秒にする。登録名は `shogi-1995 TsuyouraOu 11 micro (Pentium 100MHz)`。既定はThreads 1、USI_Hash 2 MiB、FV_SCALE 24、定跡なし、MaxMovesToDraw 512、入玉27点法。思考時間はShogiHomeから通常のUSI指定で渡す。専用イメージと既存イメージは別だが、既定ランタイムのVMロックを共有するため、既存エンジンと同時には起動できない。

2026-11-08に登録先そのものを `/tmp` から起動し、86Box Pentium 100 MHz、RAM 32 MiBでUSI設定・両評価ファイルのロード・深さ1・2秒探索・infiniteからのstopを確認した。初期化後の空きは5,595,136 bytes、swap 0、平手2秒探索のホスト計測は約2.119秒、stop応答は約0.066秒だった。平手深さ1はネイティブ版と同じ30ノード、score cp 64、`7g7f`。それぞれ1回の動作確認であり、連続対局や全局面の時間厳守、棋力を保証しない。ユーザーからShogiHomeでの動作検証ができたとの報告を受けた（具体的な操作や対局条件は未記録）。自動試験のログは `.local/tests/tsuyouraou-micro-final/`、結果は `results/2026-11-08/tsuyouraou-micro-86box-smoke.json` に保存。

元の32bit試作は評価関数ロード後、プロセス間共有メモリ用の処理でSIGSEGVとなった。単一プロセスの1995年版では、一時領域にロードしたネットワークをそのまま保持する変更を専用ソースコピーに施し、余分な共有処理を省いて起動できた。クラッシュの詳細な根本原因は未確定。従来のソース・イメージは変更していない。

再構築には既存の1995年向けクロスコンパイラ・互換libc、Slackwareの取得済みパッケージ、既存Release添付物内の `guest-init-pentium1995`、前述の評価関数が必要。まず `bash scripts/build-tsuyouraou-micro-native.sh` で評価ファイルを展開し、`bash scripts/build-tsuyouraou-micro-pentium.sh` で専用32bit版を作る。環境によってはクロスコンパイラ実行にサンドボックス外の実行が必要。その後 `python3 scripts/assemble-tsuyouraou-micro.py` で専用イメージを作る。組み立ては既存の出力先を上書きしないため、再構築する場合は既存ディレクトリを退避するかスクリプトの出力先を変更する。評価ファイルとinit、OSパッケージのSHA、イメージ内のファイルを照合する。`manifest.json` に構築結果のSHAを記録する。

86Boxでの再検証は `python3 tests/tsuyouraou_micro_86box.py`。試験は既存ログを上書きしない。`/tmp` からランチャーを起動するので、ShogiHomeの作業ディレクトリには依存しない。
