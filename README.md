# shogi-1995
2026年の将棋ソフトを1995年のパソコン環境に移植する実験

- [クローンからビルド・定跡・対局までの手順](docs/getting-started.md)
- [最良候補のShogiHome用イメージ・Release添付物と再構築](docs/shogihome-release.md)
- [企画と要件](idea.md)
- [ツール選定と実装計画](docs/implementation-plan.md)
- [強化と棋譜一致率の評価計画](docs/strength-evaluation-plan.md)
- [HalfKPの学習・構造と演算の比較状況](docs/halfkp-development.md)
- [測定履歴の一覧表](docs/measurement-history.md) / [グラフ用CSV](results/measurement-history.csv)
- [補助対局の履歴](docs/match-history.md) / [Elo換算・得点率のCSV](results/match-history.csv)

Pentium 100 MHz、RAM 32 MiBの86BoxでSlackware 3.0のLinux 1.2.13を動かし、移植したやねうら王をUSI経由で操作します。評価済みの最良候補はHalfKP幅8・2層のNNUE版です。[専用イメージと起動手順](docs/shogihome-release.md)を用意しています。従来のソース構築の既定は駒得評価です。

```bash
bash scripts/setup.sh > /tmp/shogi-1995-setup.log 2>&1
./run-shogi-1995.sh
```

- [ゲスト内の将棋GUI（Tcl/Tk）](gui/README.md)
- [起動とShogiHomeへの登録](docs/runtime.md)
- [取り込み元と移植差分](docs/upstream.md)
- [検証結果と制限](docs/validation.md)

ゲストの初回起動には約30秒かかります。ShogiHome側のエンジン起動待ち時間を十分に取ってください。QEMUによる診断は`./run-shogi-1995.sh --backend qemu`で行えますが、性能比較には86Boxを使います。

新規学習と候補モデルの検証手順は[学習・検証の手順](docs/training.md)を参照してください。主評価は固定したHCPE局面を86Box上で通常の2秒指定で探索し、収録手との一致率を比較します。

- [1995年版GNU Shogiとの比較・再現ビルド](historical/README.md) / [選定と検証結果](docs/historical-engine-validation.md)
- [GNU Shogi 対局と水匠5による調査報告](docs/gnu-shogi-suisho5-investigation.md) / [対局・録画の進捗](results/suisho5-native-gnu-live/progress.md)
