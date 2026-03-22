#!/usr/bin/env bash
# setup.sh - 一鍵安裝專案依賴
# 使用方式：bash scripts/setup.sh

set -e  # 錯誤立即停止

echo "開始執行一鍵安裝..."

# 強制切到專案根目錄（project/）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || {
    echo "錯誤：無法切換到專案根目錄"
    exit 1
}

# 確認在正確根目錄
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
    echo "錯誤：請確認專案根目錄有 requirements.txt 和 src/ 資料夾"
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

echo "Step 2.5: 安裝 Piper TTS 語音引擎與模型..."

# Piper 引擎放在專案根目錄的 piper 資料夾
PIPER_DIR="$SCRIPT_DIR/piper"
# Piper 模型放在 data/models 資料夾
MODELS_DIR="$SCRIPT_DIR/data/models"

# 1. 下載 Piper 引擎 (若不存在)
if [ ! -d "$PIPER_DIR" ] || [ ! -f "$PIPER_DIR/piper" ]; then
    echo "尚未安裝 Piper，開始下載 (ARM64 版本)..."
    wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
    
    # 解壓縮到專案根目錄 (tar 會自動建立 piper 資料夾)
    tar -zxvf piper_linux_aarch64.tar.gz -C "$SCRIPT_DIR/.."
    
    # 清理壓縮檔
    rm piper_linux_aarch64.tar.gz
    echo "Piper 引擎安裝完成！"
else
    echo "Piper 引擎已存在，跳過下載。"
fi

# 2. 下載語音模型 (若不存在)
mkdir -p "$MODELS_DIR"

MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_TW/taiwan/medium/zh_TW-taiwan-medium.onnx?download=true"
MODEL_JSON_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_TW/taiwan/medium/zh_TW-taiwan-medium.onnx.json?download=true"

if [ ! -f "$MODELS_DIR/voice.onnx" ]; then
    echo "正在下載語音模型..."

    if ! wget --server-response --progress=bar:force -O "$MODELS_DIR/voice.onnx" "$MODEL_URL"; then
        echo "錯誤：找不到指定的 Piper 模型網址。"
        echo "目前 zh_TW/taiwan/medium 這條路徑無法下載。"
        exit 1
    fi

    if ! wget --server-response --progress=bar:force -O "$MODELS_DIR/voice.onnx.json" "$MODEL_JSON_URL"; then
        echo "錯誤：找不到指定的 Piper 模型設定檔網址。"
        exit 1
    fi

    echo "語音模型下載完成！"
else
    echo "語音模型已存在，跳過下載。"
fi

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
pip install -r requirements.txt

# 完成
echo ""
echo "安裝完成！"
echo "啟動程式：source .venv/bin/activate && python -m src.main"