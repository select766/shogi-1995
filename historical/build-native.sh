#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out=.local/native-gnushogi
if [[ -e "$out/src/gnushogir" ]]; then
  printf 'Native build already exists: %s\n' "$out/src/gnushogir" >&2
  exit 1
fi
mkdir -p "$out"
tar -xzf historical/vendor/gnushogi-1.2p03.tar.gz -C "$out" --strip-components=1
patch -d "$out" -p1 < historical/compatibility.patch
make -C "$out/src" -j1 gnushogir CFLAGS='-O2 -funroll-loops -std=gnu89 -fcommon -fgnu89-inline -DLONG64' LIBDIR="$PWD/$out/misc" > "$out/build.log" 2>&1
sha256sum historical/vendor/gnushogi-1.2p03.tar.gz historical/compatibility.patch "$out/src/gnushogir" > "$out/sha256.txt"
gcc --version | head -1 > "$out/compiler.txt"
