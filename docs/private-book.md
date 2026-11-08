# 電竜戦向け私有定跡

対象は、やねうら王FANBOXの有償会員向けに頒布されたペタショック定跡 `user_book1-19003763.7z`（展開後 `user_book1.ybb`）。[FlippedBookの容量と応手への影響](book-flipped-investigation.md)も参照。

最良のNNUE候補と組み合わせる場合は[ShogiHome用Releaseイメージの手順](shogihome-release.md)を使う。`assemble-shogihome.py`は加工済み定跡があれば組み込み、なければスキップする。Release添付物は定跡を含めず、各利用者がローカルで組み立てる。

`private/readme.md` と配布元の条件に従い、元ファイル・加工結果・定跡入りイメージを公開しない。`private/` と `.local/` は Git の対象外。強さ測定では使用しない。

```
.local/venv/bin/python scripts/reduce-petashock.py
bash scripts/build-guest-probe.sh --engine .local/images/book-engine.ext2
```

ホストのPythonに `cshogi==1.1.0` と `numpy==1.26.4` が必要。例えば `python3 -m venv .local/venv` と `.local/venv/bin/pip install -r requirements-evaluation.txt` で準備する。元ファイルを展開する場合は7zも必要。処理は `private/petashock/user_book1-19003763.7z` を展開し、`private/petashock/reduced/user_book1.ybb` を生成する。作業領域 `.local` に展開用約1.73 GBと出力用の空きが必要。既に展開済みなら `--input` で指定できる。イメージ生成時、加工済みファイルがあれば `/book/user_book1.ybb` に含める。定跡を外すには加工済みファイルを移動してからイメージを再生成する。

USI設定は `USI_OwnBook=true`, `BookFile=user_book1.db`, `BookDir=/book`, `BookOnTheFly=true`, `IgnoreBookPly=true`, `FlippedBook=false`, `BookMoves=999`, `BookEvalDiff=0`, `BookDepthLimit=0`, `BookPvMoves=1`。`.db` が存在しなければ `.ybb` を読む。32 MiB環境では `BookOnTheFly=false` にしない。`BookFile=no_book` は読み込みと使用を無効にする。`USI_OwnBook=false` も使用を無効にするが、BookFileの設定によっては読み込み処理自体は行われる。

既定の加工は、先手用と後手用をそれぞれ平手からたどり、自分の各局面の手を1つに絞る。先手初手は `2g2f`、他は元定跡の評価値最大、同値なら探索深さ最大、さらに同値なら指し手の数値順で選ぶ。相手は元定跡にない手も含む全合法手を展開し、自分の局面が元定跡にない場合はそこで打ち切る。手順の合流は重複排除し、両者の局面を結合する。元定跡にない応手は探索に任せる。反転局面のフォールバックによる想定外の手を避けるため `FlippedBook=false` を使う。`IgnoreBookPly=true` を前提とし、局面キーは手数を含まない。

展開済みファイルがあれば `--input .local/book-work/user_book1.ybb` を指定できる。従来の記録手数による加工は `--max-ply 20` を指定する。元は19,003,763局面、1,730,958,978バイト。従来の20以下では2,215,765局面、230,157,646バイトで、30以下では551,064,008バイト。既定方式は選択する手や元定跡の内容で容量が変わる。記録手数は対局頻度ではなく、手順前後や手数違いで到達できる局面を落とすことがある。

このマシンの元定跡を既定方式で加工した結果は、先手用1,043,320局面、後手用1,092,956局面、結合後2,136,276局面・106,813,832バイト。各局面の指し手は1つ。指定のShogiHome用イメージに組み込み、86Boxで初期局面と先後の複数局面の定跡ヒットを確認した。起動後の空きは14,659,584バイト、swapは0（1回）。この検証は対局や棋力の測定ではない。

従来の20手カット定跡について、QEMUの32 MiBゲストで開始局面が定跡にヒットし、`no_book` に切り替えると探索に戻ることを確認。定跡読み込み直後の空きは18,714,624バイト、検索・無効化後は13,656,064バイト、swapはいずれも0。86Boxでも開始局面の定跡ヒットと `no_book` 切り替えを確認し、検索後の空きは17,416,192バイト、swapは0。開始局面の定跡応答は `BookPvMoves=8` で約11秒、`BookPvMoves=1` で約3.6秒だった（各1回、速度測定ではない）。大会前に持ち時間に照らして複数局面で遅延を確認する。
