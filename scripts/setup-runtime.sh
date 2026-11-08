#!/usr/bin/env bash
# Runtime dependencies only: no compiler, engine build or private book access.
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in python3 tar mke2fs debugfs xvfb-run; do
    command -v "$tool" >/dev/null || { echo "Required host tool missing: $tool" >&2; exit 1; }
done
python3 scripts/fetch-assets.py --runtime-only
mkdir -p .local/86box .local/images
if [[ ! -d .local/86box/roms-master ]]; then
    mkdir -p .local/86box/roms-master
    tar -xzf .local/downloads/86box-roms.tar.gz --strip-components=1 -C .local/86box/roms-master
fi
if [[ ! -d .local/86box/app ]]; then
    chmod +x .local/downloads/86Box-v6.0.AppImage
    (cd .local/86box && ../downloads/86Box-v6.0.AppImage --appimage-extract > extract.log)
    mv .local/86box/squashfs-root .local/86box/app
fi
tar -xzf .local/downloads/idenet.tgz -C .local
python3 - <<'PY'
from pathlib import Path
b = bytearray(Path('.local/vmlinuz').read_bytes())
b[508:510] = (0x300).to_bytes(2, 'little')
b[504:506] = b'\0\0'
if len(b) > 1474560:
    raise ValueError('unexpected boot kernel size')
b += bytes(1474560 - len(b))
Path('.local/images/boot.img').write_bytes(b)
PY
echo 'Runtime ready; assemble the engine image with scripts/assemble-shogihome.py'
