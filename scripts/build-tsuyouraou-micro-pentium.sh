#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
out="$root/.local/tsuyouraou-micro"
mkdir -p "$out/source-pentium" "$out/bin" "$out/obj-pentium-rebuild"
cp -a "$root/vendor/YaneuraOu/source/." "$out/source-pentium/"
# This diagnostic is implemented only by the project's material evaluator.
python3 - "$out/source-pentium/usi.cpp" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); text=p.read_text()
line='    if(token=="shogi1995halfkp") { Eval::print_halfkp_features(engine.get_position()); return false; }'
if text.count(line)!=1: raise SystemExit('unexpected USI diagnostic source')
p.write_text(text.replace(line, '#if defined(EVAL_MATERIAL)\n'+line+'\n#endif'))
PY
# On the single-process 1995 target, keep the successfully loaded network in
# its original allocation rather than hashing and copying it to shared memory.
python3 - "$out/source-pentium/shm.h" "$out/source-pentium/eval/nnue/evaluate_nnue.cpp" <<'PYCODE'
import sys
from pathlib import Path
p=Path(sys.argv[1]); text=p.read_text()
old='    SharedMemoryBackendFallback() = default;'
new=old+'\n#if defined(SHOGI1995_SINGLE_THREAD)\n    explicit SharedMemoryBackendFallback(LargePagePtr<T> p) : fallback_object(std::move(p)) {}\n#endif'
assert text.count(old)==1;text=text.replace(old,new)
old='    SystemWideSharedConstant() = default;'
new=old+'\n#if defined(SHOGI1995_SINGLE_THREAD)\n    explicit SystemWideSharedConstant(LargePagePtr<T> p) : backend(SharedMemoryBackendFallback<T>(std::move(p))) {}\n#endif'
assert text.count(old)==1;text=text.replace(old,new);p.write_text(text)
p=Path(sys.argv[2]);text=p.read_text()
old='\t\tshared_networks = SystemWideSharedConstant<NnueNetworks>(*tmp);'
new='#if defined(SHOGI1995_SINGLE_THREAD)\n\t\tshared_networks = SystemWideSharedConstant<NnueNetworks>(std::move(tmp));\n#else\n'+old+'\n#endif'
assert text.count(old)==1;text=text.replace(old,new);p.write_text(text)
PYCODE
cat > "$out/bin/legacy-g++-micro" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../../.." && pwd)
compiler="$repo/.local/i486-linux-musl-cross/bin/i486-linux-musl-g++"
for arg in "$@"; do
    case "$arg" in
        -c|-E|-S|--version|-dumpmachine|-dumpversion|-print-*) exec "$compiler" "$@" ;;
    esac
done
exec "$compiler" -static -no-pie -nostartfiles -Wl,-Map,"$repo/.local/tsuyouraou-micro/engine-rebuild.map" \
    "$repo/.local/legacy-libc/crt1.o" -L "$repo/.local/legacy-libc/lib" "$@"
WRAPPER
chmod +x "$out/bin/legacy-g++-micro"
make -C "$out/source-pentium" -j"${BUILD_JOBS:-8}" normal \
  YANEURAOU_EDITION=YANEURAOU_ENGINE_SFNN_ka2_2048_8_64_progress8 \
  TARGET_CPU=PENTIUM1995 COMPILER="$out/bin/legacy-g++-micro" PYTHON=python3 LTOFLAGS= \
  OBJDIR="$out/obj-pentium-rebuild" TARGET="$out/yaneuraou-pentium-rebuild" \
  > "$out/build-pentium-rebuild.log" 2>&1
printf 'Built %s\n' "$out/yaneuraou-pentium-rebuild"
