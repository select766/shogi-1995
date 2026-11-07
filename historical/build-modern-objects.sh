#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f historical/modern32/source/src/*.o historical/modern32/source/src/gnushogir
# Compilation only: final linking uses GCC 2.7.0's driver and 1995 binutils/libc.
objects='mainN.o globals.o bookN.o genmoveR.o patternR.o ataksR.o utilR.o evalR.o initR.o searchR.o tcontrlN.o dspcomR.o nondspR.o'
nice -n 19 make -C historical/modern32/source/src -j1 $objects \
 CC='gcc -m32 -march=i486 -mtune=i486 -W -fsigned-char $(OPT) $(GENOPT)' \
 CFLAGS="-O2 -funroll-loops -std=gnu89 -fcommon -fgnu89-inline -fno-pie -fno-stack-protector -nostdinc -isystem $PWD/historical/guest/usr/lib/gcc-lib/i486-linux/2.7.0/include -isystem $PWD/historical/guest/usr/include" \
 LIBDIR=/work/old/misc > historical/results/build-modern32.log 2>&1
cp historical/modern32/source/src/*.o historical/guest/work/modern/
cp historical/relay.c historical/guest/work/relay.c
cp historical/guest-build.sh historical/guest/work/build.sh
truncate -s 128M historical/guest.ext2
mke2fs -q -F -t ext2 -r 0 -O none -I 128 -b 1024 -N 8192 -d historical/guest historical/guest.ext2
debugfs -w -f /dev/stdin historical/guest.ext2 <<'DEVICES'
cd /dev
mknod ttyS0 c 4 64
mknod console c 4 0
mknod null c 1 3
mknod zero c 1 5
mknod tty c 5 0
DEVICES
python3 historical/guest-build.py
rm -f historical/bin/gnushogi-gcc270 historical/bin/gnushogi-gcc1140
debugfs -R 'dump /work/old/src/gnushogir historical/bin/gnushogi-gcc270' historical/guest.ext2
debugfs -R 'dump /work/modern/gnushogir historical/bin/gnushogi-gcc1140' historical/guest.ext2
debugfs -R 'dump /work/build-old.log historical/results/build-gcc270.log' historical/guest.ext2
python3 - <<'PYTHON'
from pathlib import Path
for name in ('gnushogi-gcc270','gnushogi-gcc1140'):
 p=Path('historical/bin')/name
 if not p.is_file() or p.read_bytes()[:4]!=b'\x7fELF':raise RuntimeError('missing/invalid guest build: '+name)
 p.chmod(0o755)
PYTHON
