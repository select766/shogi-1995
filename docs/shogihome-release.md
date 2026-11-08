# 最良候補のShogiHome用イメージとRelease添付物

## 採用するエンジン

現時点の完了済み測定に基づき、**標準HalfKP(Friend)幅8・2層、駒得への残差モデルD42、出力積和radix版**を採用候補とする。独立4,096局面・Pentium 100 MHz・32 MiB・通常2秒で、駒得基準1,168件（28.5156%）に対して1,542件（37.6465%）、差+9.1309ポイント、対応あり95%区間+7.5439〜+10.7178ポイントだった。両版とも異常・反則・時間超過0件。[全件結果](halfkp-development.md)を参照。定跡による改善やEloを測った結果ではない。

選択記録は[`config/release/denryu-halfkp-v1.json`](../config/release/denryu-halfkp-v1.json)。学習済みモデルは評価時と同一バイト列を使用する。エンジンはオプション上限変更だけを加えて再ビルドした固定イメージから取り出す。

|対象|SHA-256|
|---|---|
|エンジン `shogi-pentium1995`|`01ead057e47a7c887c6de203fb5b53db83dde172c8d0d1f0c987f3c144689c33`|
|モデル `halfkp-w8-d42.bin`|`d42b68f3da24fe3d77d9549aeca1c0b6a4ced375d7ff7fa6b14c737d876bdeff`|
|ゲストinit `guest-init-pentium1995`|`0164b73503a213aeb93f249f1950f12da8c00c54a5b059eab53dcce3948c26c9`|

エンジンの対応ソースcommitは`a96c9273eb8dc0554e2c29fa4c8ea6386b13c6d5`。全件測定したabf8666からのエンジンソース差分はNetworkDelay2の上限10000→60000 msだけで、初期値1120 ms・モデル・探索・評価処理は維持する。この再ビルド版で独立4,096局面の再測定はしていない。モデルは上流の任意のNNUEファイルとは互換でなく、この企画専用の形式である。通常のたぬき棋譜をシャッフル・新規qsearchして学習したもので、学習履歴は[`halfkp-model-frozen-20261107-1000.json`](../manifests/halfkp-model-frozen-20261107-1000.json)にある。

## このマシンでの登録先

定跡が手元にあったため、次の専用イメージには定跡を組み込んでいる。

```text
/home/select766/shogi/shogi-1995/.local/shogihome/denryu-halfkp-v1/run.sh
```

ShogiHomeのエンジン実行ファイルに上の絶対パスを登録する。登録前に最大起動待ち時間を120秒にする。起動スクリプトは作業ディレクトリに依存せず、専用`root.ext2`を使う。起動するのはCUIゲストで、盤面はShogiHomeに表示する。従来の`.local/images/engine-root.ext2`と通常ランチャーは変更しない。同じ既定VM領域を使うため、通常起動と同時使用しない。

専用profileがUSIで返す名称は`shogi-1995 HalfKP NNUE w8 D42 radix (Pentium 100MHz)`。評価済みバイナリ内部の旧ビルド名`MaterialLv1`は残っているため、専用ランチャーの`--engine-name`でUSIの`id name`だけを置き換える。エンジン・モデル・イメージのバイト列とSHAは変えない。汎用起動や駒得基準版の名称は変更しない。表示名を更新する場合は対局終了後にエンジンを再起動し、ShogiHomeが名称を保存している場合はエンジン情報の再取得または再登録を行う。

定跡を含めない検証用の起動先は`.local/shogihome/denryu-halfkp-v1-no-book/run.sh`。各profileの`manifest.json`に実際のイメージSHA・設定・定跡の有無を保存する。

|設定|初期値|
|---|---|
|EvalFile|`/eval/model.bin`（モデル同一性を固定）|
|Threads / USI_Hash|1 / 2 MiB|
|MaxMovesToDraw / EnteringKingRule|512 / CSARule27|
|USI_Ponder|false|
|NetworkDelay / NetworkDelay2|120 / 1120 ms（実対局環境に合わせて変更）|
|USI_OwnBook / BookFile|定跡ありはtrue / user_book1.db、なしはfalse / no_book|

定跡ありでは`BookDir=/book`、`BookOnTheFly=true`、`IgnoreBookPly=true`、`FlippedBook=true`、`BookMoves=999`、`BookEvalDiff=0`、`BookDepthLimit=0`、`BookPvMoves=1`も初期設定する。32 MiBでは定跡を全件メモリに読む設定に変更しない。

モデル以外は起動時にUSIの初期値として設定する。ShogiHomeに通知する既定値にも反映するため、新規登録時に定跡が自動で有効になる。保存済みのShogiHome設定はそちらが優先されるので、登録後に値を確認する。定跡やNetworkDelayはShogiHomeから変更できる。`engine_options.txt`に固定するのはEvalFileだけ。ブリッジは`go`の時間を書き換えず、独自の思考期限によるstopも送らない。

`NetworkDelay2=10120`を大会用に設定できるよう、指定範囲を0〜60000 msに拡張した。初期値は1120 msのまま。更新前のShogiHome登録情報には上限10000が保存されている場合があるため、対局終了後にエンジンを再起動し、オプション情報を再取得するか同じrun.shを再登録してから10120を設定する。

対局設定は**先手3分・後手10分・双方1手2秒加算**。ShogiHome経由での実際の接続と連続対局、両方の先後での大会時計の確認はユーザーが行う。USI試験の成功をGUI対局済みとは扱わない。

## Releaseに添付するファイル

公開前の添付物はGit対象外の次のフォルダへまとめる。**このフォルダ内の8ファイルだけを添付する。ローカルのイメージや定跡は添付しない。** 今回はReleaseの作成・アップロードを行わない。

```text
.local/release-assets/denryu-halfkp-v1/
  shogi-pentium1995                 評価済みELF32 staticエンジン
  halfkp-w8-d42.bin                 学習済みモデル（2,006,300 bytes）
  guest-init-pentium1995            構築済みゲストinit
  release-manifest.json             バイト数・SHA・出典・評価結果
  SHA256SUMS                       全添付物の照合用
  shogi-1995-engine-source.tar.gz   エンジン対応commitのソース・ビルド手順・依存物manifest
  COPYING.YaneuraOu                エンジンのライセンス
  README.txt                       添付物の説明
```

生成には、このマシンに保存されている固定候補イメージが必要。出力先が既にある場合は上書きしない。再生成時は新しい出力先を指定する。

```bash
python3 scripts/prepare-release.py --output .local/release-assets/denryu-halfkp-v1
(cd .local/release-assets/denryu-halfkp-v1 && sha256sum -c SHA256SUMS)
```

この処理は固定イメージからエンジン・モデル・initだけを明示して抽出し、SHAを選択記録と照合する。`private/`、定跡、root.ext2、OS/ROM一式、学習棋譜をコピーしない。対応ソースはエンジンの元commitから`git archive`で作る。公開時はこの組み立てスクリプトと文書が入ったcommitをReleaseの対象にする。添付物の`packaging_commit`は準備時点のcommitで、エンジン自体の出典は別の`engine_source_commit`である。

## Releaseから取得したファイルでイメージを組み立てる

Linux x86-64ホストを想定する。Python 3、bash、tar、e2fsprogs（mke2fs/debugfs）、Xvfb/xvfb-run、libX11、libXtstを用意する。**エンジン・initのコンパイラや学習環境は不要。** 86Box・ROM・Slackwareパッケージ・起動カーネルは固定URLとSHAを持つmanifestから別途取得する。これらはRelease添付物に含めない。既存ホストに必要なツールは導入済み。

1. このスクリプトを含むReleaseのタグをチェックアウトする。以下の`<release-tag>`を実際のタグに置き換える。

   ```bash
   git clone https://github.com/select766/shogi-1995.git
   cd shogi-1995
   git checkout <release-tag>
   mkdir -p .local/release-assets/denryu-halfkp-v1
   ```

2. GitHubのRelease画面から上記8ファイルをダウンロードし、`.local/release-assets/denryu-halfkp-v1/`へ置く。GitHubが自動生成するSource codeアーカイブと、エンジン対応ソース添付物は別である。照合する。

   ```bash
   (cd .local/release-assets/denryu-halfkp-v1 && sha256sum -c SHA256SUMS)
   ```

3. 実行環境だけを準備する。既存の`scripts/setup.sh`はエンジンをビルドする経路なので、Releaseのバイナリ利用時はこちらを使う。

   ```bash
   bash scripts/setup-runtime.sh
   ```

4. 定跡は任意。権利を持つ利用者だけが[私有定跡の手順](private-book.md)で`private/petashock/reduced/user_book1.ybb`を用意する。加工済みファイルが既にあればそのまま使える。元の7zだけがある場合は、先に`python3 scripts/reduce-petashock.py --max-ply 20`で加工する（7zと作業用空き容量が必要）。**加工済み定跡がなければ次の処理は自動でスキップし、入手・購入・展開を試みない。**

5. 新規の専用イメージを作る。

   ```bash
   python3 scripts/assemble-shogihome.py \
     --assets .local/release-assets/denryu-halfkp-v1 \
     --output .local/shogihome/denryu-halfkp-v1
   realpath .local/shogihome/denryu-halfkp-v1/run.sh
   ```

   処理は空の専用rootへSlackwareパッケージを展開し、照合済みエンジン・モデル・initを配置して、Linux 1.2.13向けの旧形式ext2を生成する。定跡があれば`/book/user_book1.ybb`へコピーする。ファイル配置とSHAをイメージから読み戻して確認し、run.shと設定を生成する。既定イメージや共有guest-rootを流用・変更しない。入力はダウンロード済み添付物と固定OSパッケージだけであり、`prepare-release.py`や元の学習データは不要。

   手元に定跡があっても除外したい場合は`--no-book`、別の加工済みファイルを指定したい場合は`--book /absolute/path/user_book1.ybb`を追加する。出力先が既存なら新しいディレクトリにする。定跡なしでは`USI_OwnBook=false`・`BookFile=no_book`とし、以前の定跡を引き継がない。各構築のイメージSHAはfilesystem生成時刻等で変わり得るため、バイナリ・モデルSHAと実際のprofile manifestで同一性を確認する。

6. 表示されたrun.shの絶対パスをShogiHomeへ登録する。CLIで先に確認する場合はrun.shを起動し、`usi`→`isready`→`quit`を順に送る。初回起動は約30秒。より詳しい運用試験は次のとおり（結果ファイルは新規名を使う）。

   ```bash
   python3 tests/shogihome_release.py \
     --profile .local/shogihome/denryu-halfkp-v1 \
     --output .local/tests/shogihome-release-check.json
   ```

   この試験は実86Boxで設定取得、モデル/radix有効、定跡ありならヒット、定跡と遅延設定の変更、通常2秒、非対称大会時計のgo/stop、512手履歴、終了と再起動を確認する。プロトコルログは`.local/tests/`に置く。定跡由来の指し手やログも公開しない。

## ソースから再ビルドする場合

ビルドには[ソース構築の依存ツール](getting-started.md)とGit履歴が必要。リポジトリの別クローンでエンジン対応commit `a96c9273eb8dc0554e2c29fa4c8ea6386b13c6d5`をチェックアウトし、`bash scripts/setup.sh`で互換ツールチェーンとエンジンをビルドする。対応ソース添付物にもソースと依存物manifestを収録しているが、Git履歴は含まないため、その展開だけではGit由来のビルド記録を生成できない。これはモデルを取得・学習する処理ではない。バイナリ再ビルドとReleaseバイナリ利用を混同しない。評価に使った同一バイト列を必要とする場合は照合済み添付物を使う。独自ビルドを出場候補にする場合は別途動作確認・測定を行う。

## 公開・配布に含めないもの

`private/`、加工済み定跡、定跡入りイメージ、定跡由来のプロトコルログはGitへコミットせず、Releaseにも添付しない。`.local/`全体を圧縮して配布しない。定跡の有無にかかわらず今回のReleaseは上記8ファイルだけとし、ゲストOS・ROMのイメージ自体の配布は行わない。

## 2026年11月8日の動作確認結果

同日、NetworkDelay2の指定上限を60000 msへ拡張した再ビルド版を追加検証した。10120・60000を指定してisready後も値が保持され、60001は拒否された。初期値1120・NNUE/radix・定跡ヒット・通常2秒・大会時間go/stop・512手履歴・再起動も成功。[実ゲスト記録](../results/2026-11-08/shogihome-networkdelay2-range-v1.json)と[Release・既存起動先への反映記録](../results/2026-11-08/networkdelay2-package-update-v1.json)を参照。以下の初回検証表と監査記録は上限変更前の履歴であり、現在の添付物のSHAは冒頭の表とRelease内のSHA256SUMSで確認する。

Release添付物と同じSHAの入力から、空の専用rootを使って両構成を生成した。定跡なし版は存在しない定跡パスを指定してスキップ動作も確認した。両profileの`release_manifest_sha256`が実際の添付フォルダ内のmanifestと一致することを確認済み。

|構成|開始局面・depth 1の応答|通常movetime 2000|起動・モデルロード後の空きRAM / swap|USI・設定変更・512手履歴・大会go/stop・再起動|
|---|---|---|---|---|
|定跡なし|約0.263秒|約2.032秒|14,675,968 bytes / 0|成功|
|定跡あり|約3.588秒、定跡ヒット|約2.032秒（定跡無効へ切り替えて測定）|14,655,488 bytes / 0|成功|

定跡ありの応答時間は1局面・1回の観測であり、上限保証ではない。大会時計での連続対局とShogiHome画面での接続操作は引き続き確認する。これらのUSI試験をGUI対局済みや棋力測定とは扱わない。

証跡：[定跡なし](../results/2026-11-08/shogihome-release-no-book-v1.json)、[定跡あり](../results/2026-11-08/shogihome-release-with-book-v1.json)、[添付物の監査](../results/2026-11-08/shogihome-release-assets-audit-v1.json)。添付物の全チェックサム、対応ソースと測定版のソースツリー一致、私有定跡・イメージの除外を確認し、改変モデルがイメージ作成前に拒否されることも検証した。ブリッジの既定値表示と範囲・選択肢の保持、時間指定の非変更、改行を含む設定拒否の単体試験3件も成功した。
