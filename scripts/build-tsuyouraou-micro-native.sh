#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
out="$root/.local/tsuyouraou-micro"
archive="$root/private/tsuyouraou/TuyouraOu11micro-SFNN_ka2_2048_8_64_progress8-epoch0010-20261001.7z"
# Keep this build and its generated architecture header separate from all other builds.
mkdir -p "$out/source" "$out/eval"
cp -a "$root/vendor/YaneuraOu/source/." "$out/source/"
7z x -y -o"$out/eval" "$archive" > "$out/extract.log"
make -C "$out/source" -j"${BUILD_JOBS:-8}" normal \
  YANEURAOU_EDITION=YANEURAOU_ENGINE_SFNN_ka2_2048_8_64_progress8 \
  TARGET_CPU=AVX2 COMPILER=g++ PYTHON=python3 \
  OBJDIR="$out/obj-native" TARGET="$out/yaneuraou-native" \
  > "$out/build.log" 2>&1
printf 'Built %s\n' "$out/yaneuraou-native"
