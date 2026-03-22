"""Audio Layer - 耳朵 + 嘴巴

負責：
- speech_to_text()  : 錄音 → Whisper 轉文字
- text_to_speech()  : 文字 → Piper TTS 播放
"""

from __future__ import annotations

import sys
import subprocess
import os
import shutil
from pathlib import Path
from typing import Optional

# 確保專案根目錄在 sys.path 中（直接執行本檔時需要）
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

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
        self._reported_no_capture = False
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
    def describe_capture_path(self) -> str:
        """回傳目前命令語音輸入預計使用的錄音路徑。"""
        if os.getenv("WSL_DISTRO_NAME"):
            if shutil.which("ffmpeg") is not None:
                return "voice(ffmpeg+Pulse@WSL)"
            return "keyboard(fallback: ffmpeg missing on WSL)"

        if shutil.which("arecord") is None:
            return "keyboard(fallback: arecord missing)"

        try:
            proc = subprocess.run(
                ["arecord", "-l"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
                check=False,
            )
            out = (proc.stdout or "").lower()
            if "no soundcards found" in out:
                return "keyboard(fallback: no soundcards)"
        except Exception:
            return "keyboard(fallback: capture probe failed)"

        return f"voice(arecord:{self.device})"

    def _has_capture_device(self) -> bool:
        """檢查 Linux 端是否看得到錄音裝置。"""
        # WSL 常見沒有 ALSA soundcard，但可透過 Pulse 轉發錄音。
        if os.getenv("WSL_DISTRO_NAME"):
            return True

        try:
            proc = subprocess.run(
                ["arecord", "-l"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            print("❌ 找不到 arecord，請執行：sudo apt install alsa-utils")
            return False
        except Exception:
            return False

        out = (proc.stdout or "").lower()
        if "no soundcards found" in out:
            if not self._reported_no_capture:
                print("⚠️ 目前偵測不到麥克風裝置（arecord -l: no soundcards found）。")
                print("⚠️ 若在 WSL，請改用鍵盤輸入或設定麥克風轉發。")
                self._reported_no_capture = True
            return False
        return True

    def _record_audio(self, duration: Optional[int] = None) -> str:
        """使用 arecord 錄音，返回 wav 路徑"""
        if not self._has_capture_device():
            return ""

        record_seconds = duration or self.default_duration
        output_path = Path(RECORDINGS_DIR) / "latest.wav"

        # WSL 下優先使用 Pulse 錄音（ffmpeg），通常比 ALSA arecord 穩定。
        if os.getenv("WSL_DISTRO_NAME"):
            pulse_wav = self._record_audio_ffmpeg_pulse(output_path, record_seconds)
            if pulse_wav:
                return pulse_wav
            print("⚠️ WSL Pulse 錄音失敗，改試 arecord。")

        device_candidates = [self.device]
        if self.device != "default":
            device_candidates.append("default")

        def _cmd(device: str) -> list[str]:
            return [
                "arecord", "-D", device,
                "-d", str(record_seconds),
                "-r", "16000", "-c", "1", "-f", "S16_LE",
                "-t", "wav", str(output_path),
            ]

        try:
            for idx, device in enumerate(device_candidates):
                try:
                    subprocess.run(
                        _cmd(device),
                        check=True,
                        timeout=10,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if idx > 0:
                        print(f"ℹ️ 已改用備援錄音裝置: {device}")
                    return str(output_path)
                except subprocess.CalledProcessError:
                    continue

            print("❌ 錄音失敗，請檢查麥克風裝置或調整 DEVICE_PORT。")
            if output_path.exists():
                output_path.unlink()
            return ""
        except subprocess.CalledProcessError:
            print("❌ 錄音失敗，請檢查麥克風裝置")
            if output_path.exists():
                output_path.unlink()
            return ""
        except FileNotFoundError:
            print("❌ 找不到 arecord，請執行：sudo apt install alsa-utils")
            return ""

    def _record_audio_ffmpeg_pulse(self, output_path: Path, record_seconds: int) -> str:
        """WSL fallback: 使用 ffmpeg 從 Pulse source 錄音。"""
        if shutil.which("ffmpeg") is None:
            print("❌ 找不到 ffmpeg，無法使用 Pulse 錄音 fallback")
            return ""

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "pulse", "-i", "default",
            "-t", str(record_seconds), "-ac", "1", "-ar", "16000",
            str(output_path), "-y",
        ]
        try:
            subprocess.run(cmd, check=True, timeout=record_seconds + 6)
            return str(output_path)
        except Exception:
            if output_path.exists():
                output_path.unlink()
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
    #text = processor.keyboard_input()      # 先用鍵盤測試
    text = processor.speech_to_text()    # 改成這行即可測試真實語音
    processor.text_to_speech(f"我聽到您說：{text}")