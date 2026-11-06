#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in python3 gcc make tar mke2fs debugfs xvfb-run import; do
    command -v "$tool" >/dev/null || { echo "Required host tool missing: $tool" >&2; exit 1; }
done
python3 scripts/fetch-assets.py
mkdir -p .local/86box .local/guest-root .local/images
if [[ ! -d .local/i486-linux-musl-cross ]]; then
    tar -xzf .local/downloads/i486-linux-musl-cross.tgz -C .local
fi
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
bash scripts/build-legacy-libc.sh
bash scripts/build-engine.sh
bash scripts/build-guest-probe.sh --engine
python3 - <<'PY'
from pathlib import Path
b=bytearray(Path('.local/vmlinuz').read_bytes())
b[508:510]=(0x300).to_bytes(2,'little')  # root=/dev/hda
b[504:506]=b'\0\0'                    # no boot-time ramdisk prompt
b+=bytes(1474560-len(b))
Path('.local/images/boot.img').write_bytes(b)
PY
python3 scripts/record-build.py
echo 'Ready: ./run-shogi-1995.sh (86Box), or --backend qemu (diagnostic only)'
