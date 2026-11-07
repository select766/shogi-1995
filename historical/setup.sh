#!/usr/bin/env bash
# Only the GNU comparator is rebuilt. Research binaries/models/images are untouched.
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in python3 gcc make patch tar mke2fs debugfs qemu-system-i386 flock; do
    command -v "$tool" >/dev/null || { echo "Required tool missing: $tool" >&2; exit 1; }
done
exec 9>historical/build.lock
flock -n 9 || { echo 'Another GNU Shogi build is running' >&2; exit 1; }
version=$(gcc -dumpfullversion)
if [[ "$version" != 11.4.0 && "${GNU_SHOGI_ALLOW_DIFFERENT_GCC:-0}" != 1 ]]; then
    echo "The recorded modern compiler is GCC 11.4.0; found $version." >&2
    echo 'Use GNU_SHOGI_ALLOW_DIFFERENT_GCC=1 only to create a separately identified compiler variant.' >&2
    exit 1
fi
python3 historical/prepare.py "$@"
bash historical/build-modern-objects.sh
python3 historical/write-manifests.py
echo 'GNU Shogi comparator ready. See historical/README.md.'
