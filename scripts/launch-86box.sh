#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
shogi_run_dir="${1:-$PWD/.local/run}"
printf '%s\n' "$DISPLAY" > "$shogi_run_dir/display"
printf '%s\n' "$XAUTHORITY" > "$shogi_run_dir/xauthority"
exec .local/86box/app/AppRun -N -P "$shogi_run_dir/vm" \
    -R "$PWD/.local/86box/roms-master" "$shogi_run_dir/vm/86box.cfg"
