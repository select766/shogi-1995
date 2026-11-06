#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
repo=$PWD
export PATH="$repo/.local/i486-linux-musl-cross/bin:$PATH"
tar -xzf .local/downloads/musl-1.2.5.tar.gz -C .local
python3 - <<'PY'
from pathlib import Path
p=Path('.local/musl-1.2.5/arch/i386/syscall_arch.h')
s=p.read_text(); s=s[:s.index('#if SYSCALL_NO_TLS')]
s+='\nlong shogi_legacy_syscall(long,long,long,long,long,long,long);\n'
for n in range(7):
    args=['long n']+['long a'+str(i) for i in range(n)]
    vals=['n']+['a'+str(i) for i in range(n)]+['0']*(6-n)
    s+='static inline long __syscall%d(%s) { return shogi_legacy_syscall(%s); }\n'%(n,','.join(args),','.join(vals))
p.write_text(s)
# TLS setup is supplied by our bounded Linux 1.2 LDT implementation.
Path('.local/musl-1.2.5/src/thread/i386/__set_thread_area.s').write_text('')
PY
cp src/compat/legacy-syscall.c .local/musl-1.2.5/src/linux/shogi_legacy.c
mkdir -p .local/musl-1.2.5/src/linux/i386
cp src/compat/legacy-syscall.s .local/musl-1.2.5/src/linux/i386/shogi_raw.s
mkdir -p .local/musl-build .local/legacy-libc
cd .local/musl-build
"$repo/.local/musl-1.2.5/configure" --target=i486-linux-musl --disable-shared \
    --with-malloc=oldmalloc --prefix="$repo/.local/legacy-libc" \
    CC="$repo/.local/i486-linux-musl-cross/bin/i486-linux-musl-gcc" \
    CFLAGS='-Os -march=pentium -mno-mmx -mno-sse -mno-sse2 -fno-stack-protector'
make -j8
make install
cd "$repo"
.local/i486-linux-musl-cross/bin/i486-linux-musl-gcc -c -Os -fno-stack-protector \
    -I .local/musl-1.2.5/arch/i386 src/compat/legacy-crt.c -o .local/legacy-libc/crt1.o
# libstdc++ includes CPU-dispatched hardware RNG code even in an i486 archive.
# Replace that one object so the final image contains no RDRAND/RDSEED/CMOV path.
cp .local/i486-linux-musl-cross/i486-linux-musl/lib/libstdc++.a .local/legacy-libc/lib/libstdc++.a
.local/i486-linux-musl-cross/bin/i486-linux-musl-g++ -c -Os -march=pentium \
    -mno-mmx -mno-sse -mno-sse2 -include src/compat/no-hardware-random.h \
    -x c++ .local/downloads/gcc-random.cc -o .local/random.o
.local/i486-linux-musl-cross/bin/i486-linux-musl-ar r .local/legacy-libc/lib/libstdc++.a .local/random.o
