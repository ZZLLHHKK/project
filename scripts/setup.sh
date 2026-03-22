#!/usr/bin/env bash
# 相容入口：允許沿用 bash scripts/setup.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT_DIR/setup.sh" "$@"
