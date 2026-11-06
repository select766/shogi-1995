# shogi-1995
2026年の将棋ソフトを1995年のパソコン環境に移植する実験

- [企画と要件](idea.md)
- [ツール選定と実装計画](docs/implementation-plan.md)

Pentium 100 MHz、RAM 32 MiBの86BoxでSlackware 3.0のLinux 1.2.13を動かし、移植したやねうら王をUSI経由で操作します。現在の評価関数は駒得評価です。

```bash
bash scripts/setup.sh > /tmp/shogi-1995-setup.log 2>&1
./run-shogi-1995.sh
```

- [起動とShogiHomeへの登録](docs/runtime.md)
- [取り込み元と移植差分](docs/upstream.md)
- [検証結果と制限](docs/validation.md)

ゲストの初回起動には約30秒かかります。ShogiHome側のエンジン起動待ち時間を十分に取ってください。QEMUによる診断は`./run-shogi-1995.sh --backend qemu`で行えますが、性能比較には86Boxを使います。
