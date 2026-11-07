# ゲスト内の将棋GUI

Slackware 3.0 / Linux 1.2.13 / Pentium / RAM 32 MiB上で動く、Tcl 7.4・Tk 4.0のウィンドウアプリです。XFree86 3.1.2とtwmを使います。対局ルール、時計、USI通信はC製の小さな子プロセスが担当します。ホストから盤面を描画したり、ホスト上でAIを動かしたりしません。

## 作業の分離

専用ブランチ `feature/guest-shogi-gui`、専用worktreeに実装しています。エンジン側のソース、測定履歴、ビルド出力、VM、ロック、ログは変更しません。GUIの成果物とVMは、このworktreeの `.local/gui/` 内だけに置きます。CPU・メモリ・ディスク等のホスト資源は共有します。

ゲストからのエンジン起動はLinux 1.2向けのfork/exec経路を用意し、古いOSで互換libcのTLS状態を子へ持ち越す問題を避けています。この対応もGUI側だけに閉じています。

ビルド時にエンジンリポジトリの `.local/guest-root/` をコピーします。エンジンを再コンパイル・改変しません。利用した `/shogi` のSHA-256は `.local/gui/image-build.json` に記録します。別セッションがビルド中のタイミングを避けてイメージを生成してください。エンジンを更新した後はGUI用イメージを再生成すると反映されます。

## 初回ビルド

既存エンジン環境のセットアップが完了していることが前提です。以下はGUIのworktree内で実行します。

```bash
export SHOGI_GUI_DEPS=/home/select766/shogi/shogi-1995
bash gui/build-image.sh
python3 gui/install-launcher.py --deps "$SHOGI_GUI_DEPS"
```

追加のSlackwareパッケージは `packages.json` のURLから取得し、SHA-256を検証します。sudoやホストOSのパッケージ変更は不要です。最初のビルドにはネットワーク接続が必要です。クロスコンパイラの実行やX11/VMの操作は、Codexのsandbox外での実行を必要とする場合があります。

通常の起動：OSのアプリケーション一覧から **将棋 1995（ゲスト）** を選びます。86Boxのウィンドウ内にゲストのデスクトップと設定画面が開きます。フルスクリーンにはしません。設定画面を閉じた後は、ゲストのデスクトップで左／右クリック → **Applications → Shogi 1995** から再起動できます。twmのタイトルバーを右クリックするとCloseメニューが開きます。

コマンドで起動する場合：

```bash
python3 gui/run-guest.py --deps "$SHOGI_GUI_DEPS"
# 速い機能診断用。性能評価には使いません。
python3 gui/run-guest.py --deps "$SHOGI_GUI_DEPS" --backend qemu
```

起動時は常に専用の基準ディスクからコピーします。ゲスト内で行ったファイル変更は次回起動へ引き継ぎません。GUI用VMの多重起動は専用ロックで防ぎます。86Boxウィンドウを閉じるとVMも終了します。

## 対局

- 先手・後手それぞれに「人間」「AI」を選択します。人間同士ならエンジンは起動しません。AIを使う場合も、両者合わせてエンジンは1プロセスだけです。相手の手も含めた `position startpos moves ...` を手番ごとに送信します。
- 持ち時間の既定は双方5分、毎手10秒加算のフィッシャールールです。開始前に分・秒で変更できます。0も指定できます。時計は着手確定時に加算します。時間を使い切っても負けにせず、マイナスを表示します。USIの残り時間は0以上に丸め、GUIの負の時計は維持します。エンジンの初期化中は時計を止めます。
- 自分の駒、移動先の順にクリックします。持ち駒もクリックしてから盤上の空きマスをクリックして打ちます。成る／成らないを選べる場合はモーダルを表示します。強制成りは自動です。合法手のみ受け付け、王手放置、二歩、行き所のない駒、打ち歩詰めも拒否します。
- 棋譜は「▲7六歩」の形式で1手1行です。駒を動かした元の座標も添えます。成・打を表示し、スクロールバー・マウスホイールで遡れます。新しい手は自動で末尾へスクロールします。
- 投了ボタンは現在の手番側の投了です。27点法の入玉宣言条件を満たす場合は「入玉宣言」に変わります。先手28点／後手27点、敵陣の駒10枚以上（玉以外）、玉が敵陣にあり王手がないことを判定します。
- 詰み、四回同一局面、連続王手の千日手、USIの `resign` / `win` も処理します。終局後の盤面・時計・棋譜を保持し、「次の対局」で設定へ戻ります。安全上、2048手で引き分けにします。
- 音声はありません。先手が下の固定表示です。

## エンジン設定

ホスト側の `gui/engine.conf` をテキストで編集します。次回VM起動時に `/etc/shogi-gui.conf` へ反映します。別ファイルは `--engine-config /absolute/path/to/config` で指定できます。

```ini
Engine=/shogi
EngineDir=/
USI_Hash=2
Threads=1
USI_Ponder=false
EvalFile=/eval/model.bin
```

`Engine` はゲスト内の実行ファイルの絶対パス、`EngineDir` はゲスト内の作業ディレクトリです。シェルコマンドや引数列にはしません。その他の `名前=値` は `usiok` の後に `setoption name 名前 value 値` として送ります。スペースのあるオプション名・値も利用できます。オプション名はエンジンの表記に合わせます（このリポジトリは `USI_Hash`、別のエンジンなら例えば `USIHash=64`）。32 MiBゲスト向けの既定ハッシュは2 MiBです。`EvalFile=/eval/model.bin` で、このリポジトリのゲストルートからコピーした評価モデルを読み込みます。別エンジンでは設定名やモデルパスをそのエンジンに合わせて変更します。

別のUSIエンジンも、ゲストで実行できるLinux 1.2互換バイナリと必要なデータを `.local/gui/root/` に配置し、専用イメージに収録すれば利用できます。ビルドスクリプトによる再生成ではこのディレクトリを作り直すので、恒常的な差し替えはビルドスクリプトのコピー部分へ追加してください。起動は実行ファイルを直接execします。USIの初期化タイムアウトは120秒です。切断や不正な応答・着手は対局を止めて表示し、盤面を保持します。

## Codexからのデバッグ

### ホストで同じGUIを確認

現代のTkでも同じ `app.tcl` とルール・通信プロセスを実行できます。

```bash
bash gui/run-host.sh
xvfb-run -a -s '-screen 0 800x600x24' python3 gui/tests/test_gui.py
```

ホストモードでAIを使う場合は、ホスト上で直接起動できるUSIバイナリを指定した設定ファイルを `SHOGI_GUI_CONFIG` に指定します。ゲスト用 `/shogi` はホストのファイルパスではありません。

### 実ゲストの自動テスト

```bash
export SHOGI_GUI_DEPS=/home/select766/shogi/shogi-1995
python3 gui/tests/test_guest.py
```

専用のQEMUゲストを起動し、実際のLinux 1.2.13／Tk 4.0で、着手、成りモーダル、次の対局、リポジトリの実エンジンでAI同士・先手AI・後手AIの対局を検証して終了します。結果、画面PPM、USIログは `.local/gui/run/` に残します。PPMは `convert input.ppm output.png` で確認できます。`guest-test-result.json` に利用したエンジンのSHA-256も残ります。

### 対話的なゲスト診断

```bash
python3 gui/run-guest.py --deps "$SHOGI_GUI_DEPS" --backend qemu --headless --debug
# 別ターミナル。最初の接続でVMの起動が始まります。
python3 gui/guest-debug.py --boot --command '/usr/local/bin/gui-tools cat /tmp/shogi-gui-launch.log'
python3 gui/guest-debug.py --screenshot /tmp/shogi-gui.ppm
```

シリアルコンソールから `/tmp/shogi-gui-debug` を作ってGUIを再起動すると、`/tmp/shogi-gui.fifo` を使えます。`test_guest.py` がその一連の操作の実例です。

GUIのデバッグコマンドは `setup human human 5 10`、`start`、`click x y`（盤面canvas内の座標）、`promote 1` / `promote 0`、`action`、`settings`、`quit` です。`core ...` で下記プロトコルも呼べます。任意のTcl評価やネットワーク待受は行いません。状態はFIFOと同じパスの `.state` に保存します。通常起動時はデバッグ入口を作りません。

シリアルコンソールの補助コマンド： `gui-tools cat ファイル`、`gui-tools sync`。`/proc` もマウントするのでメモリ等を調査できます。ログは `/tmp/shogi-gui.log`（UIプロトコル、USI送受信、エンジンPID、Tkエラー）、`/tmp/xserver.log`、`/tmp/twm.log`。ホスト側のVMログは `.local/gui/run/vm.log` と `serial.log` です。debugモードのシリアル出力は接続側で取得します。

### ルール・通信の独立テスト

```bash
bash gui/build.sh
python3 gui/tests/test_rules.py --reference="$SHOGI_GUI_DEPS/.local/test-python"
python3 gui/tests/test_session.py
```

ルールテストは既存のテスト用python-shogi 1.1.1と、ランダム500局面の全合法手・遷移・王手判定を照合します。追加で打ち歩詰め、強制成り、入玉点数を確認します。通信テストはUSIプロセスの共有、設定の送信、加算時計、マイナス時間、千日手・連続王手、初期化失敗、次の対局を検証します。

画面なしで `.local/gui/bin/core --debug --config gui/engine.conf` を起動し、標準入力へ `new human human 300 10`、`targets 56 0`、`move 7g7f`、`state`、`action`、`close` を1行ずつ渡せます。出力は `state`、`targets`、`move`、`error` 等の行形式です。`--debug` 時だけ `sfen ...`（人間同士限定）と `legal` も使用できます。SFEN指定後は人間同士での操作確認用とし、AIに渡す開始局面には利用しません。

通常の86Box起動経路も `SHOGI_GUI_DEPS=... xvfb-run -a -s '-screen 0 1200x900x24' python3 gui/tests/test_86box.py` で確認できます。

## ファイル構成・再生成

`rules.c` が将棋ルール、`core.c` が対局進行・時計・USI子プロセス、`app.tcl` が画面とクリック操作です。日本語はTk 4.0にUnicodeがないため同梱XBMで描画します。`assets/` をそのまま配布でき、実行時に追加フォントやPythonは不要です。字形の再生成に限り、ホストのPillowとNoto Sans CJKフォントを使う `make-glyphs.py` を実行します。
