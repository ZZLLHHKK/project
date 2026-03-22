#!/usr/bin/env bash
# setup.sh - 專案一鍵安裝（支援 desktop / pi 模式）
# 用法：
#   bash setup.sh --mode desktop
#   bash setup.sh --mode pi
#   bash setup.sh --mode desktop --skip-piper --skip-model

set -euo pipefail

MODE="desktop"
INSTALL_PIPER=1
INSTALL_MODEL=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="${2:-desktop}"
            shift 2
            ;;
        --skip-piper)
            INSTALL_PIPER=0
            shift
            ;;
        --skip-model)
            INSTALL_MODEL=0
            shift
            ;;
        -h|--help)
            echo "Usage: bash setup.sh [--mode desktop|pi] [--skip-piper] [--skip-model]"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [[ "$MODE" != "desktop" && "$MODE" != "pi" ]]; then
    echo "錯誤：--mode 只能是 desktop 或 pi"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d src || ! -d requirements ]]; then
    echo "錯誤：請在專案根目錄執行此腳本"
    exit 1
fi

echo "[setup] Project root: $PROJECT_ROOT"
echo "[setup] Mode: $MODE"

echo "[setup] 安裝系統依賴..."
sudo apt update -y
sudo apt install -y \
    git curl wget ca-certificates \
    python3 python3-venv python3-pip \
    build-essential cmake pkg-config \
    libopenblas-dev libsndfile1-dev \
    portaudio19-dev libportaudio2 alsa-utils \
    sox libsox-fmt-all ffmpeg \
    graphviz graphviz-dev

if [[ "$MODE" == "pi" ]]; then
    sudo apt install -y python3-gpiozero
fi

if [[ ! -d .venv ]]; then
    echo "[setup] 建立 .venv"
    python3 -m venv .venv
fi

echo "[setup] 安裝 Python 套件..."
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ "$MODE" == "pi" ]]; then
    python -m pip install -r requirements/pi.txt
else
    python -m pip install -r requirements/desktop.txt
fi

install_piper_runtime() {
    local arch
    arch="$(uname -m)"
    local url

    case "$arch" in
        x86_64)
            url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
            ;;
        aarch64)
            url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"
            ;;
        *)
            echo "[setup] 不支援的架構: $arch，略過 Piper runtime 下載"
            return
            ;;
    esac

    if [[ -x piper/piper ]]; then
        echo "[setup] Piper runtime 已存在，略過"
        return
    fi

    echo "[setup] 下載 Piper runtime ($arch)..."
    local tgz
    tgz="/tmp/piper_runtime_${arch}.tar.gz"
    wget -qO "$tgz" "$url"
    tar -xzf "$tgz" -C "$PROJECT_ROOT"
    rm -f "$tgz"
    echo "[setup] Piper runtime 完成"
}

download_default_model() {
    local model_dir="$PROJECT_ROOT/data/models"
    mkdir -p "$model_dir"

    if [[ -f "$model_dir/voice.onnx" && -f "$model_dir/voice.onnx.json" ]]; then
        echo "[setup] voice.onnx 已存在，略過"
        return
    fi

    local model_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx?download=true"
    local json_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json?download=true"

    echo "[setup] 下載預設語音模型 (zh_CN-huayan-medium)..."
    wget -qO "$model_dir/voice.onnx" "$model_url"
    wget -qO "$model_dir/voice.onnx.json" "$json_url"
    echo "[setup] 語音模型完成"
}

if [[ "$INSTALL_PIPER" -eq 1 ]]; then
    install_piper_runtime
else
    echo "[setup] 依參數略過 Piper runtime"
fi

if [[ "$INSTALL_MODEL" -eq 1 ]]; then
    download_default_model
else
    echo "[setup] 依參數略過語音模型下載"
fi

echo
echo "[setup] 完成"
echo "1) source .venv/bin/activate"
echo "2) cp .env.example .env  # 填入 GEMINI_API_KEY"
echo "3) python -m src.main"