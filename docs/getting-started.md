# クローンから対局まで

Linux x86-64ホスト上で、1995年相当のPentium 100 MHz・RAM 32 MiBのゲストを動かす手順です。盤面をホストのShogiHomeに表示する方法と、ゲスト内のTcl/Tk GUIで人間と対局する方法があります。コマンドはすべてクローンのルートで実行します。ShogiHome、86Boxおよび配布物の利用条件は各配布元で確認してください。

```bash
git clone https://github.com/select766/shogi-1995.git
cd shogi-1995
```

Ubuntu 22.04 x86-64での構築を想定します。ホストにPython 3、GCC（32bitコード生成が可能なもの）、make、tar、e2fsprogs（mke2fsとdebugfs）、Xvfb/xvfb-run、ImageMagickのimport、libX11、libXtstが必要です。GUIは表示可能なデスクトップ、診断にはqemu-system-i386も必要です。インターネット接続と数GiBの空き容量を用意します。初回の構築は既存の `.local/` を更新します。保存したいイメージやモデルがある場合は先に退避してください。

## エンジンとゲスト環境の準備

### ソースから構築

```bash
bash scripts/setup.sh > /tmp/shogi-1995-setup.log 2>&1
```

失敗したらログの末尾を確認します。固定URLから86Box、ROM、Slackwareパッケージ、クロスツールチェーン等を取得してハッシュを検証し、互換ライブラリとエンジンをビルドして `.local/images/engine-root.ext2` を作ります。上流ソースは `vendor/YaneuraOu` に含まれています。ビルドは学習データや評価関数ファイルを取得しません。既定は評価ファイル不要の駒得版です。生成されたエンジンは `.local/guest-root/shogi`、ゲスト内では `/shogi` です。

同じ実装にはこのリポジトリの軽量NNUEモデルを読む機能があります。対応するモデルを用意した場合、下の「評価関数」を参照してください。上流の任意のNNUEファイルと互換とは限りません。

### GitHub Releasesから入手する場合

[最良NNUE候補のRelease手順](shogihome-release.md)に、添付物の名前・SHA・配置先と、コンパイラなしでCUIゲストを組み立てる方法を記載しています。Release自体は動作確認後に公開予定です。エンジン・モデル・ゲストinit等の添付物を取得し、`bash scripts/setup-runtime.sh`で固定したエミュレータ・ROM・OSパッケージを準備した後、`scripts/assemble-shogihome.py`で専用イメージとShogiHome用run.shを生成します。私有定跡は配布せず、各利用者の手元に加工済みファイルがある場合だけ組み込みます。

これはShogiHome用のCUIゲスト経路です。ゲスト内GUIの`gui/build-image.sh`は引き続きGUI本体とinitをコンパイルします。GNU Shogiは別の構築手順です。ホストのPython、エミュレータ、イメージ操作ツール等は引き続き必要です。

## 評価関数を使う場合

対応する学習済みファイルを別途入手するか、[学習手順](training.md)に従って生成します。リリースのモデルを使う場合は、そのモデルに対応するエンジン版とSHA-256を配布説明で確認します。例えば手元のモデルを `model.bin` として、次のようにゲストに入れます。

```bash
mkdir -p .local/guest-root/eval
cp /path/to/model.bin .local/guest-root/eval/model.bin
bash scripts/build-guest-probe.sh --engine
```

`/path/to/model.bin` は入手したファイルに置き換えます。ShogiHome側で `EvalFile=/eval/model.bin` を設定してください。モデル未指定の `<none>` は駒得評価です。ゲストGUI側の設定方法は後述します。モデルの配置や設定後はイメージの再構築が必要です。学習・実験用の固定候補から、評価ファイルを自動設定する専用起動を作る場合は[学習手順](training.md)の `prepare-usi-profile.py` を参照してください。

## 私有定跡を使う場合（任意）

[定跡の手順](private-book.md)に従い、権利を持つ利用者が `private/petashock/user_book1-19003763.7z` を用意します。配布物には含めません。

```bash
.local/venv/bin/python scripts/reduce-petashock.py
bash scripts/build-guest-probe.sh --engine
```

要7z。加工結果がある場合、イメージに `/book/user_book1.ybb` が含まれます。加工済みデータや定跡入りイメージも公開・コミットしないでください。ゲストGUI用にも反映するには上のイメージ生成後にGUIイメージを生成します。ゲスト32 MiBでは丸読みを避け、USIの `BookOnTheFly=true` を使用します。大会向けの具体的なオプションと容量・応答時間の実測は[定跡の手順](private-book.md)を参照してください。強さ測定では `USI_OwnBook=false` とし、大会などで使うときだけ有効にします。`BookFile=no_book` も定跡を無効にします。

## ShogiHomeから対局

1. 起動確認として `./run-shogi-1995.sh` を実行し、`usi`、`isready`、`quit` を順に入力します。初回起動には約30秒かかります。
2. ShogiHomeの最大起動待ち時間を120秒にし、USIエンジンとしてこのクローンの `run-shogi-1995.sh` の**絶対パス**を登録します。絶対パスは `realpath run-shogi-1995.sh` で確認できます。実際に指すエンジンはVM内で動きます。
3. `Threads=1`、`USI_Hash=2`、`USI_Ponder=false` を指定します。駒得版では `EvalFile=<none>`、モデル利用時は `/eval/model.bin` にします。定跡を使わない場合は `USI_OwnBook=false` にします。
4. 人間対エンジンの対局を選び、先後と持ち時間を設定して開始します。定跡を使う場合は上記設定に加え[定跡の手順](private-book.md)のオプションを指定します。

詳細やトラブル時のログは[起動と対局の手順](runtime.md)を参照してください。`--backend qemu` は診断用です。`run-shogi-1995.sh` の既定の86BoxブリッジはVMを1台専有し、同時起動できません。

## ゲスト内GUIで人間と対局

先に上記のエンジンと、必要ならモデル・定跡を `.local/guest-root/` に準備します。GUIはその内容をコピーして独立したイメージを作るため、内容を変えたら再生成します。画像処理・X関連パッケージを追加取得します。

```bash
export SHOGI_GUI_DEPS="$PWD"
bash gui/build-image.sh
cp gui/engine.conf .local/gui/my-engine.conf
```

`.local/gui/my-engine.conf` を編集します。駒得の場合は `EvalFile=<none>`、モデルの場合は `EvalFile=/eval/model.bin` にします。定跡を使う場合は `USI_OwnBook=true` とし、[定跡の手順](private-book.md)の各USIオプションを `名前=値` の行で追加します。使わない場合は `USI_OwnBook=false` のままにします。設定ファイルはホストにあり、`Engine` や `EvalFile` のパスはゲスト内のパスです。

```bash
python3 gui/run-guest.py --deps "$SHOGI_GUI_DEPS" --engine-config "$PWD/.local/gui/my-engine.conf"
```

86Boxウィンドウ内で先手・後手をそれぞれ「人間」「AI」に設定し、持ち時間を選んで開始します。自分の駒と移動先を順にクリックします。成りや持ち駒などの操作は[GUIの説明](../gui/README.md)を参照してください。既定設定でアプリ一覧から起動したい場合は `python3 gui/install-launcher.py --deps "$SHOGI_GUI_DEPS"` を実行します。このランチャーは `gui/engine.conf` を使います。各起動は専用基準イメージのコピーから始まり、ゲスト内の変更は次回に残りません。

## GNU ShogiをShogiHomeで使う

GNU Shogiは別の1995年版比較エンジンです。上記のやねうら王・定跡・モデルとは別のゲストと、ホスト側USI変換を使います。GUI内での利用は対象外です。

```bash
bash historical/setup.sh
python3 -m venv .local/gnu-venv
.local/gnu-venv/bin/pip install -r requirements-evaluation.txt
```

GCC 11.4.0を基準とし、異なる版での構築条件や依存関係は[GNU Shogiの手順](../historical/README.md)を参照してください。86BoxのROMや起動フロッピーには上記の通常セットアップも必要です。ShogiHomeから引数付きPythonを起動するため、このクローンに次のラッパーを作ります。

```bash
cat > .local/run-gnu-shogi.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec "$PWD/.local/gnu-venv/bin/python" "$PWD/historical/usi.py" --backend 86box --compiler old
SH
chmod +x .local/run-gnu-shogi.sh
realpath .local/run-gnu-shogi.sh
```

表示された絶対パスをShogiHomeのエンジンとして登録します。初期化にはVM起動が含まれるため待ち時間を十分に取ります。USI変換が受け付ける時間指定は固定秒の `movetime` または残り時間0の `byoyomi` に限られます。通常の持ち時間やフィッシャー加算は使えず、ShogiHomeが対応する形式で送信できない場合は対局できません。[GNU Shogiの検証と制限](historical-engine-validation.md)を確認してください。
