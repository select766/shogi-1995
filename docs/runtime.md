# 起動と対局の手順

## ユーザーが行う作業

電竜戦の申込操作と、ShogiHome上での接続先設定・画面操作の確認を行う。エンジン登録前に、アプリ設定の「最大起動待ち時間」を120秒へ変更する。OSパッケージの手動導入は今回の既存ホストでは不要だった。セットアップ先はリポジトリ内の`.local/`で、sudoは使用しない。

## 再構築

Ubuntu 22.04 x64で、Python 3、gcc、make、tar、mke2fs、debugfs、Xvfbとxvfb-run、libX11、libXtstが必要。診断用にはqemu-system-i386を使う。画面確認にはImageMagickのimportを使う。これらのホスト側ツールは今回の環境に導入済み。

```bash
bash scripts/setup.sh > /tmp/shogi-1995-setup.log 2>&1
```

manifestに列挙したエミュレータ、ツールチェーン、ソース、OSパッケージだけを取得し、ハッシュを検証する。棋譜・モデルのダウンロードや学習は行わない。ネットワーク利用と32bitツール・VMの実行は、Codexのsandbox外での実行が必要になる場合がある。

上流ソースはリポジトリに取り込み済み。`vendor/YaneuraOu`を再取得したアーカイブで上書きすると移植差分が失われるため、setupでは上書きしない。成果物の再構築には`.local/`と数GiB程度の空き容量を確保する。現在はホストのローカルディスクを使用し、大規模データや学習成果物は生成していない。

## ShogiHomeへの登録

USIエンジンの実行ファイルとして、次の絶対パスを登録する。

```text
/home/select766/shogi/shogi-1995/run-shogi-1995.sh
```

起動はCUIゲストを分離したXvfb内の86Boxで行う。ゲストGUIは起動しない。初期化を含めて起動には約30秒かかる。導入済みのShogiHome 1.22.1ではエンジンタイムアウトが既定10秒、設定可能範囲は1〜300秒であるため、アプリ設定から120秒に変更してから登録する。GUIでの実際の接続操作はユーザーが確認する。[ShogiHome 1.22.1の設定定義](https://github.com/sunfish-shogi/shogihome/blob/v1.22.1/src/common/settings/app.ts)

エンジン設定を次のようにする。

| 項目 | 値 |
| --- | --- |
| Threads | 1固定 |
| USI_Hash | 2 MiB、変更可能範囲1〜4 MiB |
| MaxMovesToDraw | 512 |
| EnteringKingRule | CSARule27 |
| USI_OwnBook | false |
| USI_Ponder | false |

大会の持ち時間は先手3分、後手10分、双方1手ごとに2秒加算。ShogiHomeで設定し、対局側から残り時間と加算をUSIのbtime/wtime/binc/wincで送る。

ホストで盤面を表示して人間と対局する場合も、同じエンジンを登録する。将来のゲスト内GUI版は未実装。

## CLIでの検証

```bash
python3 tests/usi_smoke.py --backend 86box
```

usi/isready、局面設定、深さ指定探索、大会の時間指定での探索とstop、go infiniteからのstop、終了を検証する。QEMUの切り分けは`--backend qemu`で行う。

独立した合法手判定を用いる短時間対局テストには、テスト用のpython-shogi 1.1.1が必要。

```bash
python3 -m pip install --target .local/test-python python-shogi==1.1.1
python3 tests/selfplay.py --games 20 --backend 86box
```

これは固定nodesの動作検査で、棋力測定ではない。開始局面は固定seedで合法手を生成したものを使う。train-nnue内の実験資産は使用しない。

## ログと復旧

`.local/run/transport.log`にVM起動ログとゲスト出力、`.local/run/usi.log`に時刻付きUSI入出力、`.local/tests/`に検証結果を保存する。通常のログは次の起動で上書きするため、測定結果として保存する場合は実行前後に別ディレクトリへ退避する。

1台のVMを専有する構成であり、同時に複数エンジンを起動できない。二重起動はロックでエラーになる。quitまたはstdinのEOFで終了する。起動スクリプトを終了すると所有するVMとXvfbも回収する。対局中の切断は自動再起動せずエラーとして扱う。

VMのディスクは起動時に基準イメージから複製する。異常終了後も、次回起動で基準イメージからやり直せる。エンジンやランタイムを変更したときは`build-engine.sh`だけでなく、`build-guest-probe.sh --engine`でゲストイメージも更新する。

現行ブリッジはコールドブートする。GUIの待ち時間を延ばせない場合の常駐VM・事前起動モードは今後の対応事項。
