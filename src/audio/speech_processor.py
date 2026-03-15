"""Audio Layer - 耳朵 + 嘴巴（單一責任）

負責：
- speech_to_text()  : 錄音 → Whisper 轉文字
- text_to_speech()  : 文字 → TTS 播放
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

# === 正確 import（放在 src/audio/ 後可直接這樣寫）===
from src.utils.config import (
    DEVICE_PORT,
    RECORDING_DURATION,
    LANGUAGE,
    RECORDINGS_DIR,
)
from src.utils.tts import speak


class SpeechProcessor:
    """整合錄音與語音辨識/合成，提供乾淨的 I/O 介面。"""

    def __init__(self, device: str = DEVICE_PORT, default_duration: int = RECORDING_DURATION):
        self.device = device
        self.default_duration = default_duration
        Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)

    # ====================== 耳朵 ======================
    def speech_to_text(self, duration: Optional[int] = None, language: str = LANGUAGE) -> str:
        """錄音 → 轉文字 → 只回傳文字"""
        wav_path = self._record_audio(duration)
        if not wav_path:
            return ""
        text = self._transcribe(wav_path, language)
        print(f"👤 [你說]: {text}")
        return text.strip()

    def keyboard_input(self) -> str:
        """開發測試用：鍵盤輸入"""
        text = input("請輸入測試文字：").strip()
        print(f"👤 [測試輸入]: {text}")
        return text

    # ====================== 嘴巴 ======================
    def text_to_speech(self, text: str) -> None:
        """播放回覆"""
        if text:
            speak(text)

    # ====================== 私有輔助 ======================
    def _record_audio(self, duration: Optional[int] = None) -> str:
        """使用 arecord 錄音"""
        record_seconds = duration or self.default_duration
        output_path = Path(RECORDINGS_DIR) / "latest.wav"
        cmd = [
            "arecord", "-D", self.device, "-d", str(record_seconds),
            "-r", "16000", "-c", "1", "-f", "S16_LE", "-t", "wav", str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True)
            return str(output_path)
        except Exception as e:
            print(f"錄音失敗: {e}")
            return ""

    def _transcribe(self, wav_path: str, language: str = LANGUAGE) -> str:
        """呼叫 faster-whisper"""
        from src.utils.whisper_local import transcribe_latest_wav
        text = transcribe_latest_wav(input_wav=wav_path, language=language)
        return text if text != "[無辨識結果]" else ""


# ====================== 測試 ======================
if __name__ == "__main__":
    processor = SpeechProcessor()
    text = processor.keyboard_input()        # 先用鍵盤測試
    # text = processor.speech_to_text()      # 想測真實語音就改這行
    processor.text_to_speech(f"我聽到您說：{text}")