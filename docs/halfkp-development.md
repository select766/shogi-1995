# HalfKPを基準とする強化

2026年11月6日のユーザー指定により、次の順序を優先する。現在の駒得版は動作する基準として保存する。

1. 許可済みたぬき原本を本プロジェクト用に抽出し、シャッフルとqsearchを新規に適用する。train-nnueは処理方法とソースの参照に限り、加工済みデータ・学習成果物は使わない。
2. やねうら王標準HalfKP(Friend)の特徴量を使う純線形モデルを学習する。各特徴のスカラー重みを合計し、双方の視点の差を評価値とする。持ち駒の序数を区別し、標準設定どおり金と小駒の成駒は同じカテゴリにする。入力は81×1548。標準NNUEのファイル形式・層構造との互換性を意味しない。
3. 数分の試走で採用せず、訓練・独立validationのloss、学習率、延べ局面数を記録し、改善の飽和を確認してから評価する。lossが増えたcheckpointを漫然と使わず、学習率を下げた後の推移も調べる。時間切れなら収束したとは表記しない。
4. 線形モデルの整数値・通常USI・RAMと棋譜一致率が確認できたら、2層以上のネットワークへ拡張する。学習用GPUの速度を旧CPUの推論性能として扱わない。
5. Pentiumで使用可能な整数命令の範囲で、差分更新・ループ・重み配置・量子化等を最適化する。AVX、SSE、MMX、CMOVは使わない。
6. 構造と演算の最適化を反復し、32 MiB内で稼働する候補を86Box実時間のdevelopment一致率で選ぶ。testは最終候補1個を固定してから使用する。測定日時・条件・コミット・構造・演算差分・成績は測定履歴に残す。

既存のPSQTおよびtiny-v1〜v7の試作は、qsearch未適用の原局面で学習していた。これらは前処理を修正する前の探索的な測定記録として保存し、今回指定された適切な前処理と十分な学習を済ませたHalfKP基準とは扱わない。

qsearchは公開たぬきHalfKP評価関数（2023-05-08）を用いた前処理であり、配布エンジンへのその重みの流用やfine-tuneはしない。末端局面へ置換し、元と末端で手番が変わった場合は元の教師スコア・勝敗を反転する。通常の単一局面shuffleを使用し、特殊実験用のpaired/grouped生成は使わない。原本のファイル分離に加え、変換後の評価集合・validationとの同一局面も除外する。

## 線形基準の学習と検証

原本からtrain 64,000,000件と別ファイル群のvalidation 262,144件を抽出する。qsearch・固定シードでの全体シャッフル後に、末端のvalidation重複および評価集合との重複を除く。trainは変換後validationとの同一局面も除く。validationの変換後は204,662件で、57,482件の同一末端重複を除いた。qsearchの入力・出力、公開教師、バイナリ、ソース差分、seedをmanifestで追跡する。

[入力来歴の照合](../results/2026-11-06/halfkp-input-provenance-audit.json)では、trainの984ファイルとvalidationの32ファイルの分離、split内の抽出ブロック位置の一意性、抽出結果からqsearch入力へのSHA連鎖、公開教師とシャッフルシードを確認した。この記録は原本抽出と処理入力の検証であり、未完了のtrain変換や学習の完了を意味しない。

trainのqsearch・シャッフルは11月6日14:03:46 JSTに64,000,000件で完了した。所要約32.7分、入力との件数一致と、完了ファイルのSHAを別途照合した。[処理manifest](../manifests/halfkp-qsearch-train-v1.json)、[完了検証](../results/2026-11-06/halfkp-qsearch-complete-audit.json)。続く符号化と学習の完了とは区別する。

`scripts/encode-halfkp-data.py`は変換済み末端を標準HalfKPへ符号化し、元のqsearchファイルのレコード番号も保存する。`scripts/train-halfkp-linear.py --data <trainとvalidationを含む特徴量ディレクトリ> --output <新規モデル>`で、共有したスカラー重みから双方の視点の総和の差を学習する。初期値は駒得評価と一致する重みであり、既存の学習済み重みは使わない。教師スコア/600のsigmoidに対する交差エントロピーを用い、整数推論には256倍したint32を出力する。モデルは501,568 bytes。

約19 GBのtrain特徴量は、空き165 GBを確認したローカルSSDの`.local/feature-cache/halfkp-v2/train`を作業キャッシュとする。外部ディスク側の`training/halfkp-features-v2/train`はこのディレクトリへのリンク。validationは先に確定したv1の204,662件を共有する。原本・抽出レコード・qsearch結果・モデルは外部ディスクに保存し、キャッシュは固定入力とコードから再生成できる。保存先だけを変更した小規模変換で、特徴量・教師値・元インデックス・局面キーの全ハッシュが一致した。[保存先の検証](../results/2026-11-06/halfkp-ssd-cache-validation.json)。

逐次符号化の途中成果v1を保存し、`scripts/encode-halfkp-parallel.py`で4プロセス・入力順固定の符号化へ切り替えた。131,072件の実データで、逐次版と特徴量・教師値・元インデックス・局面キー・除外件数が一致し、ホスト処理時間は5.50秒から1.59秒だった。本データの先頭65,536件とも一致した。[並列化の検証](../results/2026-11-06/halfkp-parallel-encoding-validation.json)。完了後は`scripts/verify-halfkp-prefix.py`で、保存した逐次版のcheckpoint全範囲と照合してから学習する。v2は符号化処理の変更であり、64,000,000件のqsearch入力・順序・除外規則・学習条件を変更するものではない。

全件符号化は約12.3分で完了し、validationとの重複21,861件と固定評価集合との重複705件を除いた63,977,434件になった。[確定manifest](../manifests/halfkp-training-features-v2.json)。逐次版の保存済み16,382,352行について、特徴量・教師値・qsearch出力内のインデックスの全バイトが一致した。[全prefix照合](../results/2026-11-06/halfkp-production-prefix-parity.json)。この照合後に本学習を開始した。

既定の終了条件は、最低20 epoch、延べ10億局面、学習率が初期値の3%以下、直近5 epochでvalidation lossの範囲が2e-5以下かつ訓練lossの範囲が5e-5以下をすべて満たすこと。validationの改善が頭打ちになった際には学習率を段階的に下げる。100 epochの上限に達しても条件を満たさなければ`converged=false`とし、収束済みと称して評価しない。epoch末のcheckpointから明示的な`--resume`で継続できる。固定データ・コード・設定の照合とCPU/CUDA乱数・optimizer・schedulerの復元を行う。

512局面でPython特徴量とC++の標準BonaPiece一覧が一致し、合成した整数重みによる評価値も一致した。小規模な新規qsearch・符号化・GPU学習の通し試験では、連続2 epochと1 epoch終了後の再開が、重み・optimizer・scheduler・乱数・loss・最良モデルのバイト列まで一致した。これは学習パイプラインの動作確認であり、収束した棋力候補としては扱わない。

合成重みを使った実ゲストでも16局面の整数値が一致し、通常USI起動でモデルが自動ロードされた。NetworkDelayとNetworkDelay2は引き続き変更可能だった。ゲストRAMは31,866,880 bytes、空き17,788,928 bytes、swap 0。[ゲスト動作検証](../results/2026-11-06/halfkp-linear-guest-operational.json)。この検証は学習済みモデルの棋力や、負荷を排除した実時間速度を測るものではない。

## 線形基準の確認後に比較する構造

以下は次段階の候補であり、実装・学習・棋力測定を済ませた構造ではない。標準HalfKPを両視点で共有する埋め込み層に入れ、clipped ReLU後に連結して出力する。追加隠れ層がなくても、埋め込みと出力の2層になる。先の純線形基準にはこの活性化を入れない。

| 埋め込み幅 / 追加隠れ幅 | 重みファイル概算 | 加算値更新後の出力部の積和回数 | 比較順序 |
| --- | ---: | ---: | --- |
| 8 / なし | 1.913 MiB | 16 | 小さい非線形基準 |
| 16 / なし | 3.827 MiB | 32 | 表現力と差分更新費用を比較 |
| 16 / 8 | 3.827 MiB | 264 | 追加層の精度が演算費用を上回るか確認 |
| 24 / 8 | 5.741 MiB | 392 | 先行結果が有望でRAMに余裕がある場合 |

容量はint16埋め込み・重み、int32バイアス、24-byteヘッダの想定値であり、プロセス全体のRAM使用量ではない。旧OSのファイルキャッシュ、Hash、探索状態、実行コードもゲスト内で測る。幅32・追加隠れ8は重みだけで約7.654 MiBになるため、最初の候補群には入れず、必要性と実RAMが確認できた場合に検討する。

構造の比較では同じ前処理・validationを使い、十分に学習してから2秒一致率で選ぶ。演算の変更は独立した整数参照との値一致と、同ノード探索の一致を先に確かめる。候補を成績だけで小さな局面集合へ差し替えない。

11月8日12:00 JSTまでに最終評価と運用確認を行えるよう、11月7日15:00 JSTを最終候補固定の目安とする。testの4096局面×2版に約6時間、20局の補助対局に最大約8時間と運用確認の時間を残す。想定より費用が増えた場合は、固定評価集合を減らさず、追加構造の数を減らす。

### 多層版の実装と検証

標準HalfKPの小型ネットワーク用に`S95NN03`形式を追加するソースを用意した。入力は81×1548で、旧試作の独自入力形式とは区別する。全再加算は標準BonaPiece一覧を使い、差分更新は`dirtyPiece`の旧・新BonaPieceを直接加減算する。既存の最大8手の祖先参照、玉移動時の更新、null moveの扱い、`EvalVerify`による全再計算照合を引き継ぐ。

`src/shogi1995/halfkp_network.py`は共有埋め込み・clipped ReLU・出力、任意の追加隠れ層を持ち、固定駒得値への補正を学習する。`scripts/train-halfkp-nnue.py`は同じqsearch済み特徴量を使い、既定で最低40epoch・延べ25億局面とloss停滞を確認する。モデル構造・コードSHA・データSHAを固定し、epoch末の正確な再開を検証してから本学習に使う。

線形モデルの全1,024局面の実時間比較が完了した後、多層版をビルドし、ELF32静的実行形式と対象外命令のスクリーニングを通過した。[対象検査](../results/2026-11-06/halfkp-nnue-target.json)。2層・3層の既知の計算例、旧NN01/NN02形式の読み込み、誤ったstrideと末尾データの拒否の検査も通過した。新バイナリのSHAは`de0dc4e9ca0ed841ced359e12a7106e00d189455115427423d6bc64654550672`。この命令検査だけで実ゲストの動作を証明したとは扱わない。

`tests/halfkp_nnue_smoke.py`によるGPUの短い学習・epoch末の厳密再開・QATが通過した。2層/3層の合成重みと短い学習結果の計5モデルで、それぞれ512局面のC++整数値が独立参照と一致した。固定10,000ノードの256局面では1,251,446回の加算値検証を通過し、bestmove・最終ノード数も一致した。通常のisready/positionによるモデル切替も一致した。[検証結果](../results/2026-11-06/halfkp-nnue-smoke.json)。これは短い学習モデルを棋力候補として扱う試験ではない。この検証後、幅8・追加隠れ層なしの2層版の本学習を実施し、完了後に実ゲストの値・探索照合も通過した。実時間の棋譜一致率は未測定。

`scripts/run-nnue-after-measurement.py`は、指定した実行中の比較が全1,024局面・86Box・通常2秒で完走し、運用上の異常がないことを確認してから後続処理を開始する。親プロセスが未完走で終了した場合は自動再開せず、予定したソース・データmanifestが変わった場合も停止する。待機・完了後の開始・異常終了・ソース変更・ホスト/固定ノード結果の拒否をfixtureで検証した。後続のビルド・CUDA検証・本学習は現在の実時間測定の終了後に限る。

`scripts/validate-halfkp-nnue.py`は、選択checkpointから全重みを再出力してバイト一致を確認し、学習時と同じ独立validationの全局面について整数化後のloss・評価値誤差を測る。整数演算はTorchのforwardから独立したCPU int64参照を使い、持ち駒等の視点別の半CP値も差し引くまで保持する。2層・3層の256局面で盤面からの整数参照との一致を確認した。本学習済みモデルの検証は学習完了後に実施する。通常は収束していないモデルを拒否し、小規模な動作確認だけ明示的に許可できる。

合成重みの幅16・隠れ8を32 MiBのPentiumゲストに載せ、通常USIでの自動ロードと16局面の独立整数参照との一致を確認した。NetworkDelay類も引き続き設定でき、空きRAMは10,473,472 bytes、swap 0だった。[実ゲスト検証](../results/2026-11-06/halfkp-nnue-w16-h8-guest-operational-v1.json)、[検証専用manifest](../manifests/halfkp-nnue-w16-h8-operational-v1.json)。重みは4,013,068 bytes。これは3層構造の動作・収容確認であり、棋力候補ではない。

短い学習結果に全件量子化検証器を通したところ、非QATの2層版は97局面で正常に完了した。一方、QATの3層版は97局面中1局面で浮動小数点forwardと独立整数推論が1 CPずれ、検証が失敗した。[非QAT](../results/2026-11-06/halfkp-nnue-float-quantization-smoke.json)、[QATの失敗記録](../results/2026-11-06/halfkp-nnue-qat-quantization-smoke.json)。C++と独立整数参照の一致とは別の問題であり、QATの丸め境界を修正して再検証するまではQAT版を棋力候補にしない。発見時に進行中だった幅8の非QAT本学習は、この失敗を理由とした再起動をせず完了まで継続した。

この差は、出力バイアス6272（整数スケール153600）だけでも、float32では24.5 CPが24.499998 CPになることで再現した。`9d53c1c`でQAT forwardを整数スケールでの正確な計算へ変更した。学習時はfloat64で整数積和を保持し、STEで元のfloat32パラメータへ勾配を返す。ゲストの整数形式・演算を変更したものではない。正負の0.5 CP境界と全層への勾配を回帰テストに加え、GPUの学習・厳密再開・5モデル各512局面の整数照合・256局面の同ノード探索も再通過した。[再検証](../results/2026-11-06/halfkp-nnue-smoke-v2.json)。97局面の修正後QATは1点単位の差が0件で、forwardと整数推論のlossが一致した。[QAT検証器の通し試験](../results/2026-11-06/halfkp-nnue-qat-quantization-smoke-v2.json)。失敗記録は削除せず残す。

学習時のモデルソースも`model-source.py`として保存し、検証器はSHAが一致する保存ソースから古いrunを再検証できる。非QATの幅8モデルは修正前後の検証器で全204,662局面のloss・誤差が一致した。[保存ソースでの再検証](../results/2026-11-06/halfkp-nnue-w8-h0-v1-quantization-frozen-source.json)。

## 線形モデルの学習結果

純線形モデルは125,388係数。以下は学習・validationの診断であり、棋譜一致率や棋力の測定ではない。

| 完了日時（JST） | run | 学習commit | epoch / 延べ局面数 | 最良validation loss | 採用epoch | 計算秒数 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 11/06 14:32:55 | [halfkp-linear-v1](../manifests/halfkp-linear-v1-training.json) | `efb4a3e` | 20 / 1,279,548,680 | 0.565455774 | 20 | 189.9 |
| 11/06 14:42:50 | [halfkp-linear-v2](../manifests/halfkp-linear-v2-training.json) | `dd261f9` | 40 / 2,559,097,360 | 0.565455228 | 29 | 307.3 |

20epoch版の後、同じデータ・seedで最低40epoch・延べ25億局面の確認学習を行った。最初の20epochはloss・学習率・更新する範囲の順序が完全一致した。追加学習による最良validation lossの改善は約5.47e-7、40epoch時点の直近5epochの範囲は訓練loss約3.26e-8、validation loss約2.40e-7だった。学習率は0.003から0.000003まで低下しており、実用上の飽和を確認した。[確認結果](../results/2026-11-06/halfkp-linear-convergence-confirmation.json)。

測定候補は40epochの確認実験の最良checkpoint（29epoch）とする。保存checkpointと整数モデルは全125,388係数で対応し、validation全204,662局面で整数化の評価値誤差RMSEは約0.289、最大約0.528。C++と独立Python参照の512局面の整数値も一致した。[整数化検証](../results/2026-11-06/halfkp-linear-v2-quantization.json)、[値の照合](../results/2026-11-06/halfkp-linear-v2-trained-parity.json)。

学習済み候補も実ゲストで、固定10,000ノードの8局面のbestmove・最終ノード数・完了深さがホストと一致した。[探索照合](../results/2026-11-06/halfkp-linear-v2-guest-nodes-parity.json)。自動ロードの16局面も整数値が一致し、NetworkDelay設定は独立に変更できた。ゲスト空きRAMは17,788,928 bytes、swap 0。[USI検証](../results/2026-11-06/halfkp-linear-v2-guest-auto-model.json)。ホスト固定ノード診断はquickで80/256一致。これはPentiumの2秒一致率と区別し、棋力はゲスト実時間で比較する。

2026年11月6日16:24:51 JSTに、development全1,024局面・86Box Pentium 100 MHz・通常秒読み2秒・NetworkDelay/NetworkDelay2=0の交互測定が完了した。基準は294/1,024（28.7109%）、HalfKP線形モデルは339/1,024（33.1055%）。差は+4.3945 pp、対応ありbootstrap 95%区間は+1.5625〜+7.3242 ppだった。両版とも反則・異常終了・時間超過0件。[全件の比較](../results/2026-11-06/halfkp-linear-v2-development-comparison.json)。最初の256局面では改善が未確定だったが、全件でdevelopmentの候補条件（+2 pp以上）を満たした。独立test全4,096局面と補助対局はまだ使っておらず、最終採用を確定した結果ではない。

通常USIのNPS中央値は基準7,092.5、線形版7,463。両者は探索木とビルド条件が異なるため、この差を特徴量や単一の演算変更だけの効果とは解釈しない。4ブロックそれぞれの開始・終了の観測では、空きRAMの最小値は基準17,383,424 bytes、線形版16,355,328 bytes、swapはすべて0だった。[ブロックごとのメモリ](../results/2026-11-06/halfkp-linear-v2-development-memory.json)。日時・条件・コミット・主な機能差分・成績は[測定履歴](measurement-history.md)にも保存した。以後はこの十分に学習した線形版を、多層版の比較対象として保持する。

## 2層モデルの学習結果

幅8・追加隠れ層なしの非QATモデルは2026年11月6日16:34:53 JSTに40epoch・延べ2,559,097,360局面で飽和条件を満たした。学習時間564.4秒、最良checkpointは34epoch。最終学習率3e-6、直近5epochの訓練loss範囲1.55e-6、validation loss範囲4.23e-6だった。学習commitは`7921e59`で、開始時に未commit差分があったため、モデル・trainer・特徴量の実SHAもmanifestに固定した。[学習manifest](../manifests/halfkp-nnue-w8-h0-v1-training.json)、[全epochの履歴](../results/2026-11-06/halfkp-nnue-w8-h0-v1-training-history.json)。

全validation 204,662局面の最良checkpoint lossは0.55917149、整数化後は0.55923609だった。重みファイル2,006,300 bytes。量子化の評価値誤差RMSEは18.6225 CP、99%点50.8604 CP、最大103.6313 CPであり、量子化の影響は残る。[全validationの検証](../results/2026-11-06/halfkp-nnue-w8-h0-v1-quantization.json)。C++と独立整数参照の512局面は完全一致した。[学習済み重みの照合](../results/2026-11-06/halfkp-nnue-w8-h0-v1-trained-parity.json)。lossの改善を棋力の改善とは読み替えず、この非QAT版を保持したまま、修正済みQATで同じ幅8構造を学習して比較する。

学習済み2層版は、実Pentiumでも通常USIで自動ロードされ、16局面の評価値が一致した。空きRAM14,643,200 bytes、swap 0。[起動・値・メモリ](../results/2026-11-06/halfkp-nnue-w8-h0-v1-guest-auto-model.json)。固定10,000ノードの8局面はホストとbestmove・最終ノード数・完了深さが一致した。[探索照合](../results/2026-11-06/halfkp-nnue-w8-h0-v1-guest-nodes-parity.json)。ホストquick診断は97/256一致だが、Pentiumの2秒一致率とは区別する。[固定候補](../manifests/halfkp-nnue-w8-h0-v1-candidate.json)。

### 同じ幅8のQAT比較

QAT版は2026年11月6日17:07:42 JSTに100epoch・延べ6,397,743,400局面で終了した。学習commitは`4b79ba5`、開始時の未commit差分なし、所要1681.8秒。直近5epochの訓練loss範囲は3.90e-6だが、validation loss範囲は1.09e-4で、事前の上限2e-5を満たさなかった。終了理由は`max_epochs_without_saturation`、`converged=false`として保存し、採用候補にはしない。[学習manifest](../manifests/halfkp-nnue-w8-h0-qat-v1-training.json)、[全100epoch](../results/2026-11-06/halfkp-nnue-w8-h0-qat-v1-training-history.json)。

最良checkpointは96epoch。全validation 204,662局面の整数lossは0.55873017、QAT forwardと整数推論の1点単位の不一致は0件だった。表示上のlogitをCPへ戻すfloat32誤差の最大値は0.000283 CP。これは丸め修正の全件診断であり、未達の収束判定を上書きしない。[診断結果](../results/2026-11-06/halfkp-nnue-w8-h0-qat-v1-quantization-diagnostic.json)。以後の最初の速度・実時間一致率測定には、収束条件を満たした非QAT版を使う。

| 完了日時（JST） | 構造 / 学習 | 学習commit | epoch / 延べ局面数 | 整数validation loss | 収束条件 |
| --- | --- | --- | --- | ---: | --- |
| 11/06 16:34:53 | 幅8・2層 / 非QAT | `7921e59` + 記録済み差分SHA | 40 / 2,559,097,360 | 0.55923609 | 通過 |
| 11/06 17:07:42 | 幅8・2層 / QAT | `4b79ba5` | 100 / 6,397,743,400 | 0.55873017 | 未達・採用保留 |

## Pentiumの加減算更新

逆アセンブルで、`tiny_add`の各laneに`weights[j] * count`のスカラー乗算が残っていた。標準HalfKPの更新はcountが+1か−1なので、`e2c242e`で加算・減算のループへ分けた。従来形式の複数枚の持ち駒を扱う一般のcountには従来の乗算を残す。AVX等の追加命令は使わない。

変更後の対象命令検査と学習済み512局面の整数値照合は通過した。合成重み・学習済み重みの両方で256局面のbestmove・ノード数・再ロード結果が一致し、学習済みモデルでは1,214,176回の加算値照合も通過した。[学習済みの同ノード照合](../results/2026-11-06/halfkp-nnue-addsub-trained-search-parity-v1.json)、[対象命令](../results/2026-11-06/halfkp-nnue-addsub-target-v1.json)。実Pentiumの8局面もホストと一致した。[実ゲスト照合](../results/2026-11-06/halfkp-nnue-addsub-guest-nodes-parity-v1.json)。[同一重みの比較候補](../manifests/halfkp-nnue-w8-h0-addsub-v1-candidate.json)を固定したが、実時間の速度向上はまだ主張しない。

[速度測定計画](../manifests/halfkp-nnue-addsub-speed-plan-v1.json)はquick全256局面・10,000ノード・64局面のAB/BA交互測定。同じモデル・局面・bestmove・最終ノード数・完了深さと運用異常0件を条件に、ホスト時間の削減率中央値と対応ありbootstrap区間を計算する。区間下限が0より大きいことを高速化の証拠とし、ブロック間の偏りも調べる。通常の2秒棋力測定とは分け、重い学習が終了してから速度を測る。固定ノード交互測定の伝達・再開条件・不一致拒否の3件の検査、速度比較の同一モデル・探索結果・時間条件の3件の検査は通過した。

加減算版の速度比較は2026年11月6日17:31:13 JSTに完走した。両版とも97/256一致で、全局面のbestmove・最終ノード数・完了深さも一致し、運用異常は0件。対応あり時間短縮率中央値は5.3653%、bootstrap 95%区間は5.1789〜5.6695%だった。4ブロックそれぞれの中央値は5.4394%、5.7427%、5.2190%、5.3519%で、全ブロックで短縮を確認した。この演算変更を採用する。[速度比較](../results/2026-11-06/halfkp-nnue-addsub-speed-v1-comparison.json)、[同じ一致率の確認](../results/2026-11-06/halfkp-nnue-addsub-speed-v1-accuracy-comparison.json)。これは同一探索の高速化であり、5.37%の棋力向上を意味しない。

| 測定終了（JST） | 条件 | ソースcommit（旧→新） | 同じ重みでの変更 | 時間短縮率中央値（対応あり95%） | 探索一致 |
| --- | --- | --- | --- | ---: | --- |
| 11/06 17:31:13 | Pentium / quick全256 / 10,000 nodes / 64局面AB/BA | `4b79ba5` → `e2c242e` | ±1特徴量更新を乗算から加減算へ | 5.37%（5.18〜5.67%） | 256/256 |
| 11/06 18:01:13 | Pentium / quick全256 / 10,000 nodes / 64局面AB/BA | `e2c242e` → `e6d5f38` | 同じ加減算版に範囲証明付き32bit出力和を追加 | 0.21%（0.18〜0.29%） | 256/256 |

### 次の演算候補：範囲を証明した32bit出力和

出力の各活性値は0〜128なので、ロード時にバイアスへ正の重み×128を加えた上限と、負の重み×128を加えた下限を計算できる。部分和と最後の絶対値・128加算までsigned int32に収まる場合だけ32bit積和を使うソースを準備した。証明できないモデルは従来の64bit積和へ戻す。重みファイル形式と評価値は変えず、診断コマンドの`output_bits`で選択経路を確認する。

加減算版の測定終了後にビルド・対象命令検査を通過した。`tests/nnue_output_accumulation.py`は、正負の丸め境界、int32両端、積によって範囲を超えるケース、追加隠れ層、モデル切替・無効化を検査する11ケース・176局面で通過した。[整数境界と64bit切替](../results/2026-11-06/halfkp-nnue-output32-boundaries-v1.json)。学習済み512局面の整数値が一致し、256局面のbestmove・ノード数・再ロードも一致した。1,214,176回の加算値照合と、実モデルが32bit経路を選ぶことも確認した。[学習済み探索照合](../results/2026-11-06/halfkp-nnue-output32-trained-search-parity-v1.json)。

実Pentiumでも8局面のbestmove・最終ノード数・完了深さが一致し、診断カウンタの`output_bits=32`で実経路を確認した。[実ゲスト照合](../results/2026-11-06/halfkp-nnue-output32-guest-nodes-parity-v1.json)。[別の固定ノード速度比較](../manifests/halfkp-nnue-output32-speed-plan-v1.json)で採否を決める。同じ学習済み重みを使い、採用済み加減算版からの追加改善として測る。32bitの利用だけを理由に高速と主張しない。

この比較後は追加の演算候補を挟まず、[2層NNUEの実時間評価計画](../manifests/halfkp-nnue-w8-h0-development-plan-v1.json)に進む。重みは収束済み非QAT幅8の同一ファイル。32bit版の速度区間下限が正ならその版、そうでなければ採用済み加減算版を選ぶ。現在の最良HalfKP線形版とdevelopment全1,024局面・通常2秒・256局面のAB/BAで比較する。固定した駒得版との比較も条件照合を通して報告する。testはまだ使わない。

32bit版の比較も全256局面でbestmove・最終ノード数・完了深さが一致し、両版とも97/256一致、運用異常0件だった。加減算版に対する追加の時間短縮率中央値は0.2105%、対応あり95%区間は0.1772〜0.2875%。4ブロックの中央値は0.2181%、0.1977%、0.2984%、0.0390%だった。小さい改善であり、局面bootstrapが時間ブロックの相関を扱わない制限も残るが、全ブロックが同方向で事前条件を満たしたため採用する。[速度比較](../results/2026-11-06/halfkp-nnue-output32-speed-v1-comparison.json)、[一致率・探索量](../results/2026-11-06/halfkp-nnue-output32-speed-v1-accuracy-comparison.json)。通常2秒評価にはこの固定候補を使う。

2026年11月6日18:05 JSTに、計画どおり32bit出力和版の収束済み2層モデルと、最良HalfKP線形版のdevelopment全1,024局面・通常2秒の交互比較を開始した。開始前にGPU計算・他の測定・学習・ビルドがないことと、両固定イメージ、重み、評価集合のSHAを確認した。[開始条件の記録](../results/2026-11-06/halfkp-nnue-w8-h0-development-preflight-v1.json)。この主評価が完了するまで重い処理を重ねない。実時間一致率の結果はまだ確定していない。
