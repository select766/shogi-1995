#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Diagnostic only: QEMU is not the performance reference.
exec qemu-system-i386 -machine pc -cpu pentium -m 32 -snapshot \
    -kernel .local/vmlinuz -append 'root=/dev/hda rw' \
    -drive file=.local/images/probe-root.ext2,format=raw,if=ide \
    -display none -serial stdio -monitor none -no-reboot -net none "$@"
