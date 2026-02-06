#!/usr/bin/env bash
# setup.sh - 一鍵安裝專案依賴
# 使用方式：bash scripts/setup.sh

set -e  # 錯誤立即停止

echo "開始執行一鍵安裝..."

# 強制切到專案根目錄（project/）
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/.." || {
    echo "錯誤：無法切換到專案根目錄"
    exit 1
}

# 確認在正確根目錄
if [ ! -f "requirement.txt" ] || [ ! -d "src" ]; then
    echo "錯誤：請確認專案根目錄有 requirement.txt 和 src/ 資料夾"
    echo "目前目錄：$(pwd)"
    ls -la
    exit 1
fi

echo "已切換到專案根目錄：$(pwd)"

# Step 1: 更新系統與安裝基本工具
echo "Step 1: 更新系統並安裝基本工具..."
sudo apt update -y
sudo apt install -y git python3-venv python3-pip build-essential cmake \
    libopenblas-dev libsndfile1-dev portaudio19-dev libportaudio2 alsa-utils \
    python3-gpiozero graphviz graphviz-dev pkg-config libsdl2-dev libsdl2-2.0-0

# Step 2: 安裝 SoX
echo "安裝 SoX..."
sudo apt install -y sox libsox-fmt-all

# Step 3: 建立虛擬環境與安裝套件
if [ ! -d ".venv" ]; then
    echo "Step 3: 建立虛擬環境 .venv..."
    python3 -m venv .venv
else
    echo "虛擬環境 .venv 已存在。"
fi

echo "Step 4: 啟用虛擬環境並安裝 Python 套件..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirement.txt

# 完成
echo ""
echo "安裝完成！"
echo "啟動程式：source .venv/bin/activate && python -m src.main"