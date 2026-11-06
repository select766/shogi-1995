#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
compiler="$repo/.local/i486-linux-musl-cross/bin/i486-linux-musl-g++"
for arg in "$@"; do
    case "$arg" in
        -c|-E|-S|--version|-dumpmachine|-dumpversion|-print-*)
            exec "$compiler" "$@" ;;
    esac
done
exec "$compiler" -static -no-pie -nostartfiles \
    -Wl,-Map,"$repo/.local/engine.map" \
    "$repo/.local/legacy-libc/crt1.o" -L "$repo/.local/legacy-libc/lib" "$@"
