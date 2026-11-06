#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The upstream Makefile does not track our external runtime as a prerequisite.
rm -f .local/guest-root/shogi
# Make does not notice command-line/compiler-flag changes in existing objects.
# Keep separate generated caches so a configuration change always recompiles.
shogi_build_key=$(sha256sum vendor/YaneuraOu/source/Makefile scripts/legacy-g++.sh scripts/build-engine.sh | sha256sum | cut -d ' ' -f 1)
shogi_object_dir="$PWD/.local/obj-pentium1995-$shogi_build_key"
make -C vendor/YaneuraOu/source normal -j"${BUILD_JOBS:-8}" \
    YANEURAOU_EDITION=YANEURAOU_ENGINE_MATERIAL TARGET_CPU=PENTIUM1995 \
    COMPILER="$PWD/scripts/legacy-g++.sh" LTOFLAGS= LIBS="${SHOGI_EXTRA_LIBS:-}" \
    OBJDIR="$shogi_object_dir" TARGET="$PWD/.local/guest-root/shogi"
SHOGI_BUILD_KEY="$shogi_build_key" SHOGI_OBJECT_DIR="$shogi_object_dir" python3 - <<'PY'
import hashlib,json,os,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from shogi1995.provenance import source_identity
binary=root/'.local/guest-root/shogi'
report={**source_identity(),'build_key':os.environ['SHOGI_BUILD_KEY'],
        'object_dir':os.environ['SHOGI_OBJECT_DIR'],
        'engine_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
(root/'.local/last-engine-build.json').write_text(json.dumps(report,indent=2)+'\n')
PY
