# shogi-1995
2026年の将棋ソフトを1995年のパソコン環境に移植する実験

- [企画と要件](idea.md)
- [ツール選定と実装計画](docs/implementation-plan.md)
- [強化と棋譜一致率の評価計画](docs/strength-evaluation-plan.md)
- [HalfKPの学習・構造と演算の比較状況](docs/halfkp-development.md)
- [測定履歴の一覧表](docs/measurement-history.md) / [グラフ用CSV](results/measurement-history.csv)
- [補助対局の履歴](docs/match-history.md) / [Elo換算・得点率のCSV](results/match-history.csv)

Pentium 100 MHz、RAM 32 MiBの86BoxでSlackware 3.0のLinux 1.2.13を動かし、移植したやねうら王をUSI経由で操作します。現在の評価関数は駒得評価です。

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
