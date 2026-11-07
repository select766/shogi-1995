# 移行前の検証証跡

2026-11-07に独立クローンで取得した記録。元の絶対パスやビルドSHAは当時のままで、移行後のパスや再ビルド結果を表すものではない。manifestは当時のバイナリ・イメージ・ソースの識別用。ソースからの再ビルド後は `historical/manifest-{old,modern}.json` が現在の識別情報となる。

`usi-86box.json` / `summary.json` は時間・コンパイラ比較、`compiler-comparison.json` はQEMU自己対局等、`accuracy-qemu-smoke.json` と `vs-frozen-radix-qemu-smoke.json` は既存評価・研究エンジンとの接続試験。`synthetic-position-limitation.json` は時間制御の失敗例も保存する。小規模試験の結果を棋力差やEloとして扱わない。

過去の全ログは移行元 `.local/historical-1995/repo/historical/results/` および `runs/` に残る。ここにはレビューに必要な少量のテキスト証跡だけを置く。
