from __future__ import annotations
# src/config.py 放檔案路徑跟腳位控制的地方
"""
Central configuration shared by parsers and hardware executors.

Notes
- Do NOT hardcode API keys in code. Set them via environment variables.
  Example:
    export GEMINI_API_KEY="..."
    export GEMINI_MODEL="gemini-2.5-flash"
- All txt/jsonl files live under ./data/
"""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # 調整層級到 project 根目錄
# 重要 : 這裡要根據你的檔案目錄來決定, 要找出 project root 路徑才會對
# /home/pi/project/src/utils/config.py
# parents[0] → /home/pi/project/src/utils
# parents[1] → /home/pi/project/src
# parents[2] → /home/pi/project

# data part
DATA_DIR = PROJECT_ROOT / "data"
INPUT_FILE = DATA_DIR / "input.txt"
OUTPUT_FILE = DATA_DIR / "output.txt"
ACTIONS_FILE = DATA_DIR / "actions.txt"
MEMORY_FILE  = DATA_DIR / "memory.txt"
HISTORY_FILE = DATA_DIR / "history.jsonl"
REPLY_FILE   = DATA_DIR / "reply.txt"  # optional: human-friendly confirmations
RECORDINGS_DIR = DATA_DIR / "recordings"

HISTORY_KEEP = 5

# src part (待補)
SRC_DIR = PROJECT_ROOT / "src"

# whisper.cpp model path 
WHISPER_DIR = PROJECT_ROOT / "whisper.cpp"
WHISPER_MAIN = WHISPER_DIR / "build" / "bin" / "whisper-cli"
MODELS_DIR = WHISPER_DIR / "models" / "ggml-tiny.bin"
# 模型也可選 ggml-base.bin, ggml-small.bin 依需求新增

# 錄音配置 
DEVICE_PORT = "plughw:3,0"           # 樹莓派錄音接口 (在終端機 arecord -l)
RECORDING_DURATION = 8                # 錄音秒數
LANGUAGE = "auto"                    # whisper 語言代碼 (中英適用)
GEMINI_MODEL = "gemini-flash-latest"

# -------------------------
# Temperature constraints
# -------------------------
MIN_TEMP = 18.0
MAX_TEMP = 30.0
COMFORT_MIN = 22.0
COMFORT_MAX = 26.0

# -------------------------
# 7-seg GPIO mapping (BCM)  (from temp_7seg_fuzzy_memory.py)
# -------------------------
SEGMENTS = {'a': 2, 'b': 27, 'c': 18, 'd': 15, 'e': 14, 'f': 3, 'g': 23}
DIGIT_2 = 4
DIGIT_3 = 17
DIGITS = [DIGIT_2, DIGIT_3]  # left -> right (swap if needed)

# Common Anode segment patterns: 0=ON (LOW), 1=OFF (HIGH)
NUM_MAP = {
    '0': (0,0,0,0,0,0,1),
    '1': (1,0,0,1,1,1,1),
    '2': (0,0,1,0,0,1,0),
    '3': (0,0,0,0,1,1,0),
    '4': (1,0,0,1,1,0,0),
    '5': (0,1,0,0,1,0,0),
    '6': (0,1,0,0,0,0,0),
    '7': (0,0,0,1,1,1,1),
    '8': (0,0,0,0,0,0,0),
    '9': (0,0,0,0,1,0,0),
    ' ': (1,1,1,1,1,1,1),
}

# Digit enable polarity (from temp_7seg_fuzzy_memory.py)
# If your digits are inverted, swap these.
DIGIT_ON  = 1  # GPIO.HIGH
DIGIT_OFF = 0  # GPIO.LOW

# -------------------------
# LED / Fan GPIO mapping (BCM) (from controller_gemini_gpio.py)
# -------------------------
RELAY_FAN = 26

LED_RED    = 5   # kitchen
LED_GREEN  = 6   # living
LED_YELLOW = 13  # guest

# Relay trigger logic (most relay modules are LOW-level triggered)
RELAY_ON  = 0  # GPIO.LOW
RELAY_OFF = 1  # GPIO.HIGH

# LED trigger logic (typical LED: HIGH on, LOW off)
LED_ON  = 1  # GPIO.HIGH
LED_OFF = 0  # GPIO.LOW

# Canonical locations
LOC_KITCHEN = "KITCHEN"
LOC_LIVING  = "LIVING"
LOC_GUEST   = "GUEST"

LED_LOCATION_TO_PIN = {
    LOC_KITCHEN: LED_RED,
    LOC_LIVING:  LED_GREEN,
    LOC_GUEST:   LED_YELLOW,
}
