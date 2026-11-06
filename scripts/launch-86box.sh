#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
printf '%s\n' "$DISPLAY" > .local/run/display
printf '%s\n' "$XAUTHORITY" > .local/run/xauthority
exec .local/86box/app/AppRun -N -P "$PWD/.local/run/vm" \
    -R "$PWD/.local/86box/roms-master" "$PWD/.local/run/vm/86box.cfg"
