#!/usr/bin/env bash
# setup.sh - 一鍵安裝 whisper.cpp 前三步 + 專案依賴
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

# Step 3: 強制在 project/whisper.cpp 下載與操作
WHISPER_DIR="whisper.cpp"

if [ ! -d "$WHISPER_DIR" ]; then
    echo "Step 3: 下載 whisper.cpp 到 $(pwd)/whisper.cpp..."
    git clone https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR" || {
        echo "git clone 失敗，請檢查網路或權限"
        exit 1
    }
else
    echo "whisper.cpp 已存在於 $(pwd)/whisper.cpp，跳過下載。"
fi

# 進入 whisper.cpp 資料夾
cd "$WHISPER_DIR" || {
    echo "錯誤：無法進入 whisper.cpp 資料夾"
    exit 1
}

# Step 4: 下載模型
echo "Step 4: 檢查並下載 whisper.cpp 模型..."
for model in tiny base small; do
    MODEL_FILE="models/ggml-${model}.bin"
    if [ ! -f "$MODEL_FILE" ]; then
        echo "  下載 ggml-${model}.bin..."
        bash ./models/download-ggml-model.sh "$model" || {
            echo "下載 ${model} 模型失敗，請檢查網路"
            exit 1
        }
    else
        echo "  ggml-${model}.bin 已存在，跳過"
    fi
done

# Step 5: 編譯 whisper.cpp
echo "Step 5: 編譯 whisper.cpp..."
# 先清舊 build
rm -rf build 2>/dev/null || true

cmake -B build -DWHISPER_SDL2=ON || {
    echo "cmake 失敗，請確認 cmake 已安裝"
    exit 1
}
cmake --build build --config Release -j$(nproc) || {
    echo "編譯失敗，請檢查記憶體或改 -j2"
    exit 1
}

cd ..

# Step 6: 建立虛擬環境與安裝套件
if [ ! -d ".venv" ]; then
    echo "Step 6: 建立虛擬環境 .venv..."
    python3 -m venv .venv
else
    echo "虛擬環境 .venv 已存在。"
fi

echo "Step 7: 啟用虛擬環境並安裝 Python 套件..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirement.txt

# 完成
echo ""
echo "安裝完成！"
echo "whisper.cpp 已安裝在：$(pwd)/whisper.cpp"
echo "啟動程式：source .venv/bin/activate && python -m src.main"