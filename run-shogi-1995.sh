#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 src/bridge/main.py "$@"
