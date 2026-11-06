#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The upstream Makefile does not track our external runtime as a prerequisite.
rm -f .local/guest-root/shogi
make -C vendor/YaneuraOu/source normal -j"${BUILD_JOBS:-8}" \
    YANEURAOU_EDITION=YANEURAOU_ENGINE_MATERIAL TARGET_CPU=PENTIUM1995 \
    COMPILER="$PWD/scripts/legacy-g++.sh" LTOFLAGS= LIBS="${SHOGI_EXTRA_LIBS:-}" \
    OBJDIR="$PWD/.local/obj-pentium1995" TARGET="$PWD/.local/guest-root/shogi"
