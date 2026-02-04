#!/usr/bin/env bash

# setup.sh - 一鍵安裝 whisper.cpp 前三步 + 其他專案依賴
# 使用方式：bash scripts/setup.sh
# 注意：請在專案根目錄執行

set -e  # 遇到錯誤立即停止

# 檢查是否在專案根目錄
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
    echo "錯誤：請在專案根目錄執行此腳本（需要 requirements.txt 和 src/ 目錄）"
    exit 1
fi

echo "開始一鍵安裝 whisper.cpp 與專案環境..."

# Step 1: 更新系統與安裝基本工具
echo "Step 1: 更新系統並安裝基本工具..."
sudo apt update -y
sudo apt install -y git python3-venv python3-pip build-essential cmake \
    libatlas-base-dev libopenblas-dev libsndfile1-dev portaudio19-dev \
    libportaudio2 alsa-utils gpiozero graphviz graphviz-dev pkg-config \
    libsdl2-dev libsdl2-2.0-0

# 下載SOX
echo "安裝 SOX..."
sudo apt update
sudo apt install -y sox libsox-fmt-all

# Step 2: 下載 whisper.cpp
WHISPER_DIR="whisper.cpp"
if [ ! -d "$WHISPER_DIR" ]; then
    echo "Step 2: 下載 whisper.cpp..."
    git clone https://github.com/ggml-org/whisper.cpp.git
else
    echo "whisper.cpp 已存在，跳過下載。"
fi

cd "$WHISPER_DIR"

# 下載前三個模型
echo "Step 3: 下載 whisper.cpp 模型..."
if [ ! -f "models/ggml-tiny.bin" ]; then
    bash ./models/download-ggml-model.sh tiny
else
    echo "tiny 模型已存在。"
fi
if [ ! -f "models/ggml-base.bin" ]; then
    bash ./models/download-ggml-model.sh base
else
    echo "base 模型已存在。"
fi
if [ ! -f "models/ggml-small.bin" ]; then
    bash ./models/download-ggml-model.sh small
else
    echo "small 模型已存在。"
fi

# Step 4: 編譯 whisper.cpp
echo "Step 4: 編譯 whisper.cpp..."
cmake -B build -DWHISPER_SDL2=ON
cmake --build build --config Release -j$(nproc)

cd ..

# Step 5: 建立虛擬環境（若不存在）
if [ ! -d ".venv" ]; then
    echo "Step 5: 建立虛擬環境 .venv..."
    python3 -m venv .venv
else
    echo "虛擬環境 .venv 已存在。"
fi

# 啟用虛擬環境
echo "Step 6: 啟用虛擬環境並安裝 Python 套件..."
source .venv/bin/activate

# 安裝 Python 套件
pip install --upgrade pip
pip install -r requirements.txt

# 完成
echo ""
echo "安裝完成！"