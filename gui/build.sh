#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local/gui/bin
case "${1:-host}" in
 host) gcc -std=c99 -O2 -Wall -Wextra -Wno-misleading-indentation gui/core.c gui/rules.c -o .local/gui/bin/core ;;
 guest)
  deps=${SHOGI_GUI_DEPS:?Set SHOGI_GUI_DEPS to the existing repository with .local toolchain}
  "$deps/.local/i486-linux-musl-cross/bin/i486-linux-musl-gcc" -DSHOGI_GUI_LEGACY -std=c99 -Os -march=pentium -fno-stack-protector -static -no-pie -nostartfiles \
    "$deps/.local/legacy-libc/crt1.o" -L "$deps/.local/legacy-libc/lib" gui/core.c gui/rules.c -o .local/gui/bin/core-guest
  "$deps/.local/i486-linux-musl-cross/bin/i486-linux-musl-gcc" -DSHOGI_GUI_LEGACY -std=c99 -Os -march=pentium -fno-stack-protector -static -no-pie -nostartfiles \
    "$deps/.local/legacy-libc/crt1.o" -L "$deps/.local/legacy-libc/lib" gui/guest-tools.c -o .local/gui/bin/guest-tools ;;
 *) exit 2 ;;
esac
