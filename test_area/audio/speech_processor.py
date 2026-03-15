"""Audio Layer - 耳朵 + 嘴巴

負責：
- speech_to_text()  : 錄音 → Whisper 轉文字
- text_to_speech()  : 文字 → Piper TTS 播放
"""

from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional

# 從新架構的 utils 引入配置與 TTS（未來移到 audio/ 後可改相對 import）
from src.utils.config import (
    DEVICE_PORT,
    RECORDING_DURATION,
    LANGUAGE,
    RECORDINGS_DIR,
)
from src.utils.tts import speak  # ← 嘴巴功能直接使用現有 TTS


class SpeechProcessor:
    """整合錄音、語音辨識、語音合成的完整音訊處理器。"""

    def __init__(self, device: str = DEVICE_PORT, default_duration: int = RECORDING_DURATION):
        self.device = device
        self.default_duration = default_duration
        Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)

    # ====================== 耳朵（輸入） ======================
    def speech_to_text(self, duration: Optional[int] = None, language: str = LANGUAGE) -> str:
        """完整流程：錄音 → Whisper 轉文字 → 只回傳文字（不寫檔）"""
        wav_path = self._record_audio(duration)
        if not wav_path:
            return ""

        text = self._transcribe(wav_path, language)
        print(f"👤 [你說]: {text}")   # 給使用者即時回饋
        return text.strip()

    def keyboard_input(self) -> str:
        """開發測試用：鍵盤輸入（正式環境請註解掉）"""
        text = input("請輸入測試文字：").strip()
        print(f"👤 [測試輸入]: {text}")
        return text

    # ====================== 嘴巴（輸出） ======================
    def text_to_speech(self, text: str) -> None:
        """播放回覆（整合原本 tts.py 的 speak）"""
        if not text:
            return
        speak(text)  # 直接呼叫現有 TTS 邏輯

    # ====================== 私有輔助方法 ======================
    def _record_audio(self, duration: Optional[int] = None) -> str:
        """使用 arecord 錄音，返回 wav 路徑"""
        record_seconds = duration or self.default_duration
        output_path = Path(RECORDINGS_DIR) / "latest.wav"

        cmd = [
            "arecord", "-D", self.device,
            "-d", str(record_seconds),
            "-r", "16000", "-c", "1", "-f", "S16_LE",
            "-t", "wav", str(output_path)
        ]

        try:
            subprocess.run(cmd, check=True, timeout=10)
            return str(output_path)
        except subprocess.CalledProcessError:
            print("❌ 錄音失敗，請檢查麥克風裝置")
            if output_path.exists():
                output_path.unlink()
            return ""
        except FileNotFoundError:
            print("❌ 找不到 arecord，請執行：sudo apt install alsa-utils")
            return ""

    def _transcribe(self, wav_path: str, language: str = LANGUAGE) -> str:
        """呼叫 faster-whisper 轉錄"""
        from src.utils.whisper_local import transcribe_latest_wav  # 避免循環 import

        text = transcribe_latest_wav(
            input_wav=wav_path,
            language=language,
            model_name=None  # 使用 config 中的 MODELS_DIR
        )
        return text if text != "[無辨識結果]" else ""


# ====================== 測試區塊 ======================
if __name__ == "__main__":
    processor = SpeechProcessor()
    text = processor.keyboard_input()      # 先用鍵盤測試
    # text = processor.speech_to_text()    # 改成這行即可測試真實語音
    processor.text_to_speech(f"我聽到您說：{text}")