# 86Box Pentium 100 MHz の公開ベンチマークとの比較

測定日: 2026-11-12。結論は **整数の小規模な合成負荷では公開実機値と同じ桁だが、86Boxの実機に対する誤差は特定できない**。Pentium 100 MHzのLinux実機として公開された Dhrystone 2.1 の147,189回/秒に対し、本環境の86Boxは166,666.6回/秒、比は1.132倍（+13.2%）だった。これは異なるコンパイラ、ライブラリ、OS、マザーボードを含むシステム間比較であり、CPUエミュレーションの誤差を13.2%と主張できない。

## 比較対象

整数演算、分岐、ポインタ操作、文字列操作を含む古典的ベンチマーク Dhrystone 2.1 の[原版](https://netlib.org/benchmark/dhry-c)を使った。公開値は J. Buss の [VAX MIPS Benchmark](https://www.xanthos.se/~joachim/results.pdf) の Toshiba Laptop P100、Pentium 100 MHz、Linux 2.4.14、147,189 Dhrystones/秒（83.8 DMIPS）。コンパイラ、最適化、バイナリ、キャッシュ構成は資料から確認できない。

補助的な参考として、[Netlib PDSの1996年の一覧](https://netlib.org/performance/html/dhrystone.data.col1.html)には Pentium 100 MHz の Dhrystone 2.1 が複数あり、Acer Power/M Ultima、FreeBSD 2.1 は71.3 DMIPS、Windows 95の Pentium P5-100 は79.7および138.1 DMIPS と記載されている。同じ名目CPU速度でも結果が広く分かれる。DMIPS は Dhrystones/秒を1757で割った指標で、実行命令数の MIPS ではない。これらの資料はビルド条件の一致を確認できないため、86Boxの精度の上下限ではない。

| 実行環境 | Dhrystones/秒 | DMIPS | 公開Linux実機との比 |
|---|---:|---:|---:|
| Toshiba P100、Linux 2.4.14、公開値 | 147,189 | 83.8 | 1.000 |
| 86Box、Linux 1.2.13、今回の3回の中央値 | 166,666.6 | 94.9 | 1.132 |

Netlibの値71.3と138.1 DMIPSに対する今回の比はそれぞれ1.33倍と0.69倍。差は環境とコンパイル条件の相違を含む。Dhrystone は小さくキャッシュ外のメモリ挙動を測らず、最適化や文字列処理に敏感で、将棋探索の速度を代表するものではない。[Netlibの説明](https://netlib.org/performance/html/dhrystone.intro.html)もこれらの限界を指摘する。浮動小数点、RAMやL2キャッシュ、実際の将棋エンジンの性能の精度は今回未検証。86Box自身も[CPUキャッシュを扱わない](https://86box.net/2022/01/07/pcem-migration-guide.html)と説明している。

## 測定条件と結果

- 86Box 6.0 AppImage SHA-256 `535d3c329f8c32b601103970c86d80aa80298f345452c3524ea2f433624727a4`、ホスト AMD Ryzen 7 5700X。仮想マシンは `plato`、Pentium P54C 100 MHz、倍率1.5、dynarec有効、RAM 32 MiB、ET4000AX。設定は [pentium100.cfg.in](../config/86box/pentium100.cfg.in) に準拠し、32 MiBの検証用ディスクに合わせてジオメトリだけ変更した。[公式マニュアル](https://86box.readthedocs.io/en/v5.3/settings/machine.html)によればPentiumではdynarecが必須。
- ゲスト Linux 1.2.13、シングルプロセス。原版の `dhry_1.c`、`dhry_2.c` を別翻訳単位として GCC 11.2.1 `-march=pentium -O2 -fno-pie -DTIME -static -no-pie -nostartfiles`、既存の旧Linux用libcでリンク。`register`指定なし。原版のCには古い暗黙宣言などのコンパイル警告が出る。
- 原版の `time()` でゲスト内経過時間を測定。2,000,000回を3回独立実行し、それぞれ12秒、166,666.6回/秒。原版が出力する最終値はポインタの実アドレスを除き期待値と整合した。生ログは [dhrystone-86box.txt](../results/2026-11-12/dhrystone-86box.txt)。
- 時刻の分解能は1秒。12秒という表示だけでは真の所要時間は概ね11〜13秒であり、量子化だけで約153,846〜181,818回/秒となり得る。3回とも同値でも誤差がゼロとは限らない。ホストの独立時計とゲスト時計との同期、および負荷中の実時間動作率は測っていない。
- 原版アーカイブ SHA-256 `038a7e9169787125c3451a6c941f3aca5db2d2f3863871afcdce154ef17f4e3e`、実行バイナリ SHA-256 `e8a78d7973290299054597bb4baf3df86ab72cef464e6fb4300e9ae445e3f89c`。Linuxイメージなどの準備物は本リポジトリの既存手順による。

## 再現手順

[セットアップ手順](getting-started.md)に従って86Box、ROM、ゲストのブートディスクと検証用ディスク、既存のi486クロスコンパイラと旧Linux用libcを用意する。`scripts/build-guest-probe.sh` でシェル起動用 `.local/images/probe-root.ext2` が必要。86Box、Xvfb、debugfs、Python 3を使う。86Box起動時のBIOS設定は必要に応じて確認する。

```sh
curl -fL https://netlib.org/benchmark/dhry-c -o /tmp/shogi-dhry-c
python3 benchmarks/pentium100/run.py /tmp/shogi-dhry-c | tee /tmp/shogi-dhry-result.txt
```

スクリプトは原版のハッシュを確認してから展開・コンパイルし、検証ディスクのコピーにバイナリを入れて隔離VMを起動する。3回の出力と主要な最終値を検査し、不一致なら失敗する。元のゲストイメージは変更しない。起動後はシリアル出力が終了するまで待つ。標準出力が生ログで、`.local/pentium100-dhry/` に一時ファイルを残す。ネットワークや32ビットコンパイラの実行が制限された環境では、それらの許可が必要な場合がある。

より厳密な比較には公開実機のソース、コンパイラ、最適化、ライブラリとハードウェア構成を特定し、可能なら同一バイナリ・同一入力・独立時計で測定する必要がある。さらにメモリ負荷、浮動小数点、固定局面・固定探索量の将棋エンジンを追加し、複数の公開実機結果と照合する。この結果だけで既存の86Boxによる将棋の実時間評価を実機換算することはできない。
