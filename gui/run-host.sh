#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash gui/build.sh host
export SHOGI_GUI_HOME="$PWD/gui"
export SHOGI_GUI_CORE="$PWD/.local/gui/bin/core"
export SHOGI_GUI_CONFIG="${SHOGI_GUI_CONFIG:-$PWD/gui/engine.conf}"
exec wish gui/app.tcl
