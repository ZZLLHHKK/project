# src/utils/tts.py
import subprocess
import os
from src.utils.config import PIPER_EXE, TTS_MODEL

def speak(text: str) -> None:
    """
    使用 Piper TTS 將文字轉為語音並播放。
    具備開發模式：若找不到引擎，僅印出文字。
    """
    if not text:
        return
        
    text = text.strip()
    print(f"\n[PI 回覆]: {text}\n")
    
    # 防呆機制：檢查 Piper 執行檔是否存在 (避免在沒有環境的電腦上報錯)
    if not os.path.exists(PIPER_EXE):
        print("[系統提示] 未偵測到 Piper 引擎，已略過實際語音播放。")
        return
        
    if not os.path.exists(TTS_MODEL):
        print("[系統提示] 未偵測到語音模型，請確認是否執行過 setup.sh。")
        return

    # 組合 Piper 與 aplay 播放指令 (適用於 Linux/樹莓派環境)
    command = f'echo "{text}" | {PIPER_EXE} --model {TTS_MODEL} --output-raw | aplay -r 22050 -f S16_LE -t raw -'

    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"播放語音失敗: {e}")