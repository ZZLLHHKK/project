#!/bin/bash

# HomVoice 啟動腳本
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 啟用虛擬環境（如果有的話）
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

RUNTIME_MODE=desktop python -m src.main --gui
