# 取り込み元と移植差分

## やねうら王

- 取得日: 2026年11月6日
- URL: https://github.com/yaneurao/YaneuraOu
- コミット: `3a0e4fd2394e40f72fc6e2ad5aada832b4045cd9`
- 取得アーカイブとSHA-256: `manifests/assets.json`の`yaneuraou.tar.gz`
- コピー範囲: 上流アーカイブ全体を`vendor/YaneuraOu/`へ配置。生成バイナリは配布元ソースの一部ではない。
- ライセンス: [取り込んだLICENSE](../vendor/YaneuraOu/LICENSE)

専用の`PENTIUM1995`ビルドターゲットを追加した。通常の駒得評価と探索を用い、1系統の同期実行、探索中のUSI入力ポーリング、小容量の履歴とHash、定跡無効、最大512手を初期設定とする。前の駒種を履歴テーブルの4区分へまとめるため、上流と同一の探索結果や棋力は保証しない。変更はGitで追跡する。

## ランタイム

musl 1.2.5を元に、Linux 1.2専用の起動コードとシステムコール互換層を構築する。構築スクリプトと変更部分は`src/compat/`および`scripts/build-legacy-libc.sh`にある。muslのソースとクロスコンパイラはハッシュで固定し、`.local/`に配置する。

静的ELFに渡されないauxiliary vectorを補い、当時のLDT制約でTLSを設定する。mmap、readv/writev、select、時刻、スリープなどを当時の呼出しへ対応付ける。OSスレッドはサポートしない。単一CPU・専用プロセスで検証した範囲の互換層であり、汎用の旧Linux対応libcではない。単調時刻の取得はゲストの壁時計に基づくため、対局中の時計変更を避け、ホスト実時間の監視も併用する。

GCC 11.2.1のi486向けmuslクロスツールチェーンを使用し、アプリケーションはPentium命令へ限定する。i686向けランタイムの混入を避ける。コンパイラ・ライブラリのソースとライセンスの公開条件は、実行ファイルの外部配布時にも満たす。

libstdc++の`random.o`にはCPU判定で分岐するRDRAND/CMOV実装が含まれていたため、GCC公式11.2.0リリースの該当ソースからハードウェア乱数機能を無効にして再構築する。ソースのURLとハッシュは同じmanifestに記録する。これにより、専用イメージに不要な後世の命令を残さない。

## エミュレータとOS

- 86Box 6.0 build 9001の公式Linux AppImage。
- Intel Premiere/PCI II（Plato）、Pentium 100 MHz、32 MiB、ET4000AX、504 MiB IDE、シリアル通信。
- BIOSはPlatoのIntel AMIBIOS 1.00.16.AX1。公式ROMセット内の日付は1995年10月10日。
- ROM取得時の解決コミットは`c4cd8da9034a8557896ff6a975ae58499a83bb80`。取得アーカイブの内容はハッシュ照合する。ROMをGitや本プロジェクトの配布物に含めない。
- Slackware 3.0の`idenet.tgz`に含まれるLinux 1.2.13と、同じ配布媒体の基本パッケージを使用。ホストから必要なファイルを展開してext2イメージを生成する最小構成であり、インストーラによるフルインストールではない。
- カーネルの自己起動機能を使うフロッピーを生成し、ルートデバイスをIDEに設定する。カーネル本体を改造せず、ブートヘッダのみ変更する。

取得URL、サイズ、SHA-256は[資産manifest](../manifests/assets.json)を参照。モデルや棋譜のダウンロードは含まない。
