#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image=.local/images/probe-root.ext2
size=32M
extra=()
if [[ "${1:-}" == --engine ]]; then
    image=${2:-.local/images/engine-root.ext2}
    size=504M
    extra=(-DSHOGI1995_ENGINE_INIT)
fi
mkdir -p .local/guest-root/{dev,proc,tmp,sbin,bin,lib} .local/images
for pkg in aaa_base bash ldso shlibs bin sh_utils; do
    tar -xzf ".local/downloads/$pkg.tgz" -C .local/guest-root
done
# Slackware package symlinks are normally created by install/doinst.sh.
ln -sfn bash .local/guest-root/bin/sh
ln -sfn ld-linux.so.1.7.3 .local/guest-root/lib/ld-linux.so.1
ln -sfn libc.so.5.0.9 .local/guest-root/lib/libc.so.5
gcc -m32 -march=pentium -Os -fno-pie -no-pie -fno-stack-protector \
    -nostdlib -static "${extra[@]}" src/compat/guest-init.c -o .local/guest-root/sbin/init
# Optional private tournament book. The staging tree is ignored by git.
if [[ "${1:-}" == --engine && -f private/petashock/reduced/user_book1.ybb ]]; then
    mkdir -p .local/guest-root/book
    cp private/petashock/reduced/user_book1.ybb .local/guest-root/book/user_book1.ybb
else
    rm -f .local/guest-root/book/user_book1.ybb
fi
truncate -s "$size" "$image"
mke2fs -q -F -t ext2 -r 0 -O none -I 128 -b 1024 \
    -N 4096 -d .local/guest-root "$image"
debugfs -w -f /dev/stdin "$image" <<'DEVICES'
cd /dev
mknod ttyS0 c 4 64
mknod console c 4 0
mknod null c 1 3
mknod zero c 1 5
mknod tty c 5 0
DEVICES
