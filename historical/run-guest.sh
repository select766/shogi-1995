#!/bin/bash
set -eu
cd "$(dirname "$0")"
export TMPDIR=/tmp
exec nice -n 19 qemu-system-i386 -machine pc -cpu pentium -m 32 -snapshot \
 -kernel guest-vmlinuz -append 'root=/dev/hda rw' \
 -drive file=guest.ext2,format=raw,if=ide -display none -serial stdio \
 -monitor none -no-reboot -net none
