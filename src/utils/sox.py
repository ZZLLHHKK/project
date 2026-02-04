# arecord的另一個備用方案 提供自動偵測靜音 尚未測試 2026/2/3
# src/utils/audio.py
import os
import subprocess
import time
from pathlib import Path
from src.utils.config import PROJECT_ROOT, DATA_DIR, RECORDINGS_DIR, INPUT_FILE, DEVICE_PORT, MODELS_DIR

RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# silence_threshold 的建議值：
# 環境很吵（風扇、空調聲）→ 調高到 3%～5%（避免背景噪音被當成說話）
# 環境很安靜 → 保持 1% 或調低到 0.5%（更精準偵測說話結束）
# 太高（>10%）→ 可能連說話聲都被當靜音，錄音直接結束
# 太低（<0.5%）→ 很難偵測到靜音，會一直錄到手動停止

def record_with_sox(
    output_path: Path = RECORDINGS_DIR / "latest.wav",
    silence_duration: float = 1.5,      # 靜音持續多久就停止（秒）
    silence_threshold: float = 1.0,     # 靜音門檻（音量百分比，1% = 很安靜）
    sample_rate: int = 16000,
    channels: int = 1,
    device: str = DEVICE_PORT           # 從 config 來的麥克風裝置
) -> str:
    """
    用 SoX 錄音，直到偵測到 silence_duration 秒的靜音才停止
    返回錄好的 WAV 檔案路徑，若失敗返回空字串
    """
    # 確保輸出目錄存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # SoX 指令：錄音 + 靜音偵測
    cmd = [
        "rec",                              # SoX 的錄音指令（等同 sox -t alsa ...）
        "-t", "alsa", device,               # 輸入裝置
        "-r", str(sample_rate),             # 取樣率 16kHz
        "-c", str(channels),                # 單聲道
        "-b", "16",                         # 16-bit
        "-e", "signed-integer",             # 格式
        str(output_path),                   # 輸出檔案
        "silence", "1", "0.1", f"{silence_threshold}%",   # 開始偵測：0.1秒內低於門檻就開始計時
        "1", str(silence_duration), f"{silence_threshold}%"  # 持續 silence_duration 秒靜音就停止
    ]

    print(f"開始錄音... (說話結束後靜音 {silence_duration} 秒自動停止，裝置：{device})")

    try:
        # 執行 SoX 錄音（會阻塞直到靜音停止）
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if output_path.exists() and output_path.stat().st_size > 1000:  # 確認檔案存在且有內容
            print(f"錄音完成，已儲存：{output_path}")
            return str(output_path)
        else:
            print("錄音檔太小或不存在，視為失敗")
            return ""
    except subprocess.CalledProcessError as e:
        print(f"SoX 錄音失敗：{e.stderr}")
        if output_path.exists():
            output_path.unlink()  # 刪除壞檔
        return ""
    except FileNotFoundError:
        print("SoX 未安裝，請執行：sudo apt install sox libsox-fmt-all")
        return ""
    
# analyze part
from src.utils.whisper_local import transcribe_latest_wav
from src.utils.file_io import write_text_file  

'''
def stt_pipeline(
    silence_duration: float = 1.5,
    silence_threshold: float = 1.0,
    device: str = DEVICE_PORT,
    model_name: str = MODELS_DIR,
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
    wav_path = record_with_sox(
        silence_duration=silence_duration,
        silence_threshold=silence_threshold,
        device=device
    )
    if not wav_path:
        #print("錄音失敗，無法繼續轉錄")
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
            #print("轉錄結果為空或無效")
            return ""

        # 步驟3：寫入 input.txt
        write_text_file(INPUT_FILE, text)
        # print(f"轉錄完成，已寫入 {INPUT_FILE}")
        # print(f"辨識文字：{text}")

        return text

    except Exception as e:
        print(f"轉錄階段失敗：{str(e)}")
        return ""
'''