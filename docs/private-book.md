# 電竜戦向け私有定跡

`private/readme.md` と配布元の条件に従い、元ファイル・加工結果・定跡入りイメージを公開しない。`private/` と `.local/` は Git の対象外。強さ測定では使用しない。

```
python3 scripts/reduce-petashock.py --max-ply 20
bash scripts/build-guest-probe.sh --engine .local/images/book-engine.ext2
```

要 7z。処理は `private/petashock/user_book1-19003763.7z` を展開し、`private/petashock/reduced/user_book1.ybb` を生成する。作業領域 `.local` に展開用約1.73 GBと出力用の空きが必要。既に展開済みなら `--input` で指定できる。イメージ生成時、加工済みファイルがあれば `/book/user_book1.ybb` に含める。定跡を外すには加工済みファイルを移動してからイメージを再生成する。

USI設定は `USI_OwnBook=true`, `BookFile=user_book1.db`, `BookDir=/book`, `BookOnTheFly=true`, `IgnoreBookPly=true`, `FlippedBook=true`, `BookMoves=999`, `BookEvalDiff=0`, `BookDepthLimit=0`, `BookPvMoves=1`。`.db` が存在しなければ `.ybb` を読む。32 MiB環境では `BookOnTheFly=false` にしない。`BookFile=no_book` は読み込みと使用を無効にする。`USI_OwnBook=false` も使用を無効にするが、BookFileの設定によっては読み込み処理自体は行われる。

記録された手数20以下を残す加工では2,215,765局面、230,157,646バイト。元は19,003,763局面、1,730,958,978バイト。30以下では551,064,008バイトでイメージに入らない。記録手数は対局頻度ではなく、手順前後や手数違いで到達できる局面を落とすことがある。より効率的に残すには実戦棋譜の頻度や、初期局面からの分岐確率に基づく到達性を使う方法があるが、このスクリプトは実装していない。

QEMUの32 MiBゲストで開始局面が定跡にヒットし、`no_book` に切り替えると探索に戻ることを確認。定跡読み込み直後の空きは18,714,624バイト、検索・無効化後は13,656,064バイト、swapはいずれも0。86Boxでも開始局面の定跡ヒットと `no_book` 切り替えを確認し、検索後の空きは17,416,192バイト、swapは0。開始局面の定跡応答は `BookPvMoves=8` で約11秒、`BookPvMoves=1` で約3.6秒だった（各1回、速度測定ではない）。大会前に持ち時間に照らして複数局面で遅延を確認する。
