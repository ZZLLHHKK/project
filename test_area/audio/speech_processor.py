"""簡化版語音處理：錄音 -> Whisper 轉文字 -> 寫入 input.txt。"""
# langgraph node: run_once()  # 直接呼叫這個函式執行一次完整流程

from __future__ import annotations

import sys
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) #絕對路徑

from src.utils.config import (
    DEVICE_PORT,          #樹莓派usb麥克風接口
    INPUT_FILE,           #轉錄結果寫入的文字檔
    LANGUAGE,             #whisper語言設定
    MODELS_DIR,           #faster-whisper模型存放路徑
    RECORDINGS_DIR,       #錄音檔存放路徑
    RECORDING_DURATION,   #預設錄音秒數
)
from src.utils.file_io import write_text_file


class SpeechProcessor:
    """整合錄音與語音辨識，提供簡單可直接呼叫的方法。"""

    def __init__(self, device: str = DEVICE_PORT, default_duration: int = RECORDING_DURATION):
        self.device = device
        self.default_duration = default_duration
        Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)

    def keyboard_input(self) -> str:
        """鍵盤輸入測試用：讀入文字並寫到 input.txt。"""
        text = input("請輸入文字：").strip()
        if text:
            write_text_file(INPUT_FILE, text)
        return text

    def record_with_arecord(
        self,
        duration: int | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        """使用 arecord 錄音，成功回傳 wav 路徑，失敗回傳空字串。"""
        record_seconds = duration or self.default_duration
        output_path = Path(RECORDINGS_DIR) / "latest.wav"

        cmd = [
            "arecord",
            "-D",
            self.device,
            "-d",
            str(record_seconds),
            "-r",
            str(sample_rate),
            "-c",
            str(channels),
            "-f",
            "S16_LE",
            "-t",
            "wav",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, check=True)
            return str(output_path)
        except subprocess.CalledProcessError:
            if output_path.exists():
                os.remove(output_path)
            return ""
        except FileNotFoundError:
            print("找不到 arecord，請先安裝 alsa-utils")
            return ""

    def transcribe_audio(
        self,
        wav_path: str,
        language: str = LANGUAGE,
        model_name: str | None = None,
    ) -> str:
        """呼叫 whisper_local 做語音轉文字。"""
        if not wav_path:
            return ""

        text = self.transcribe_latest_wav(
            model_name=model_name or MODELS_DIR,
            language=language,
            input_wav=wav_path,
        ).strip()

        if text == "[無辨識結果]":
            return ""
        return text

    @staticmethod
    @lru_cache(maxsize=2)
    def _get_model(
        model_name_or_path: str,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
    ) -> WhisperModel:
        """快取載入 faster-whisper 模型，避免重複初始化。"""
        return WhisperModel(
            model_name_or_path,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            num_workers=1,
        )

    @staticmethod
    def _normalize_language(language: Optional[str]) -> Optional[str]:
        if language is None:
            return None
        normalized = language.strip().lower()
        if normalized in {"", "auto", "none"}:
            return None
        return normalized

    def transcribe_latest_wav(
        self,
        model_name: Optional[str] = None,
        language: str = "auto",
        threads: int = 4,
        input_wav: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 3,
        best_of: int = 3,
        vad_filter: bool = True,
    ) -> str:
        """使用 faster-whisper 轉錄 wav，回傳辨識文字。"""
        if input_wav is None:
            input_wav = str(Path(RECORDINGS_DIR) / "latest.wav")

        if not os.path.exists(input_wav):
            raise FileNotFoundError(f"找不到音檔：{input_wav}")

        if model_name is None:
            model_name = MODELS_DIR

        if os.path.isdir(model_name):
            print(f"使用本地模型路徑：{model_name}")

        model = self._get_model(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=threads,
        )

        normalized_language = self._normalize_language(language)

        try:
            segments, _info = model.transcribe(
                input_wav,
                beam_size=beam_size,
                best_of=best_of,
                language=normalized_language,
                vad_filter=vad_filter,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=True,
                word_timestamps=False,
            )

            text_parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
            text = " ".join(text_parts).strip()
            return text if text else "[無辨識結果]"
        except Exception as e:
            raise RuntimeError(f"轉錄過程錯誤：{str(e)}")

    def speech_to_text(self, duration: int | None = None, language: str = LANGUAGE) -> str:
        """完整流程：錄音 -> 轉文字，回傳辨識結果。"""
        wav_path = self.record_with_arecord(duration=duration)
        if not wav_path:
            return ""
        return self.transcribe_audio(wav_path=wav_path, language=language)

    def speech_to_input_file(self, duration: int | None = None, language: str = LANGUAGE) -> str:
        """完整流程：錄音 -> 轉文字 -> 寫入 input.txt。"""
        #text = self.speech_to_text(duration=duration, language=language)
        text = self.keyboard_input()  # 測試用，改成語音輸入後再測試轉錄結果是否正確寫入檔案, 上下註解拿掉，這行刪掉
        #if text:
            #write_text_file(INPUT_FILE, text)
        return text

def run_once(duration: int | None = None) -> str:
    """快速使用入口：執行一次語音輸入流程，回傳文字。"""
    processor = SpeechProcessor()
    return processor.speech_to_input_file(duration=duration)

# ==============測試區塊===============
if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("目前不是互動式終端，無法使用鍵盤 input()。請在 Terminal 直接執行此檔案。")
    else:
        try:
            text = run_once()
        except EOFError:
            print("未接收到鍵盤輸入（EOF）")

# 到speech_to_input_file()裡面測試轉錄結果是否正確寫入檔案，先改成keyboard_input()測試用，確定流程沒問題後再改回來測試語音輸入與轉錄功能。