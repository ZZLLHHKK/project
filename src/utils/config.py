# src/config.py 放檔案路徑的地方
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # 調整層級到 project 根目錄
# 重要 : 這裡要根據你的檔案目錄來決定, 要找出 project root 路徑才會對
# /home/pi/project/src/utils/config.py
# parents[0] → /home/pi/project/src/utils
# parents[1] → /home/pi/project/src
# parents[2] → /home/pi/project

# data part
DATA_DIR = PROJECT_ROOT / "data"
INPUT_TXT_PATH = DATA_DIR / "input.txt"
OUTPUT_TXT_PATH = DATA_DIR / "output.txt"
RECORDINGS_DIR = DATA_DIR / "recordings"

# src part (待補)
SRC_DIR = PROJECT_ROOT / "src"

# whisper.cpp model path 
WHISPER_DIR = PROJECT_ROOT / "whisper.cpp"
WHISPER_MAIN = WHISPER_DIR / "build" / "bin" / "whisper-cli"
MODELS_DIR = WHISPER_DIR / "models" / "ggml-tiny.bin"
# 模型也可選 ggml-base.bin, ggml-small.bin 依需求新增

# 錄音配置 (尚未套用)
RECODING_DURATION = 8          # 秒
LANGUAGE = "auto"                # whisper 語言代碼 (中英適用)
GEMINI_MODEL_NAME = "gemini-flash-latest"