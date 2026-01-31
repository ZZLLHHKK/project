# src/utils/audio.py recording part
import os
import subprocess
import time
from pathlib import Path
from src.utils.config import INPUT_TXT_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

def record_with_arecord(
    duration: int = 8,                  # 秒數
    device: str = "plughw:3,0",         # 改成你的裝置，從 arecord -l 看
    sample_rate: int = 16000,
    channels: int = 1
) -> str:
    """
    用 arecord 錄音，存成 wav, 返回檔案路徑
    """

    filename = "latest.wav"
    output_path = RECORDINGS_DIR / filename

    cmd = [
        "arecord",
        "-D", device,
        "-d", str(duration),
        "-r", str(sample_rate),
        "-c", str(channels),
        "-f", "S16_LE",
        "-t", "wav",
        str(output_path)
    ]

    print(f"開始錄音 {duration} 秒... 裝置：{device}")
    print("說話中...（結束後自動存檔）")

    try:
        subprocess.run(cmd, check=True)
        print(f"錄音完成，已儲存：{output_path}")
        return str(output_path)
    except subprocess.CalledProcessError as e:
        print(f"錄音失敗：{e}")
        if os.path.exists(output_path):
            os.remove(output_path)  # 刪除壞檔
        return ""
    except FileNotFoundError:
        print("arecord 指令不存在，請確認 ALSA 已安裝(sudo apt install alsa-utils)")
        return ""

# analyze part
from src.utils.whisper_local import transcribe_latest_wav
from src.utils.file_io import write_text_file  

# INPUT_TXT_PATH = str(PROJECT_ROOT / "data" / "input.txt")

def stt_pipeline(
    duration: int = 8,
    device: str = "plughw:3,0",
    model_name: str = "ggml-tiny.bin",
    language: str = "auto"
) -> str:
    """
    完整語音轉文字流程：
    1. 錄音 → latest.wav
    2. whisper.cpp 轉錄
    3. 寫入 input.txt(覆蓋)
    返回辨識文字
    """
    # 步驟1：錄音（會覆蓋 latest.wav）
    wav_path = record_with_arecord(duration=duration, device=device)
    if not wav_path:
        print("錄音失敗，無法繼續轉錄")
        return ""

    # 步驟2：轉錄
    try:
        text = transcribe_latest_wav(
            model_name=model_name,
            language=language,
            input_wav=wav_path
        )
        text = text.strip()
        if not text or text == "[無辨識結果]":
            print("轉錄結果為空或無效")
            return ""

        # 步驟3：寫入 input.txt
        write_text_file(INPUT_TXT_PATH, text)
        print(f"轉錄完成，已寫入 {INPUT_TXT_PATH}")
        print(f"辨識文字：{text}")

        return text

    except Exception as e:
        print(f"轉錄階段失敗：{str(e)}")
        return ""