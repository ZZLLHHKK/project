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
import threading
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

    def record_wav_file(
        self,
        output_path: str | Path,
        duration: Optional[int] = None,
        allow_manual_stop: bool = False,
    ) -> str:
        """只做錄音，不做 STT，並將檔案另存到指定路徑。"""
        wav_path = self._record_audio(
            duration=duration,
            allow_manual_stop=allow_manual_stop,
        )
        if not wav_path:
            return ""

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wav_path, target)
        return str(target)

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

    def _record_audio(self, duration: Optional[int] = None, allow_manual_stop: bool = False) -> str:
        """錄音入口：優先使用 arecord+VAD，WSL/桌面則回退到 ffmpeg 固定秒數錄音。"""
        if os.getenv("WSL_DISTRO_NAME") and shutil.which("ffmpeg") is not None:
            return self._record_audio_ffmpeg(duration=duration, allow_manual_stop=allow_manual_stop)

        if shutil.which("arecord") is None and shutil.which("ffmpeg") is not None:
            return self._record_audio_ffmpeg(duration=duration, allow_manual_stop=allow_manual_stop)

        wav_path = self._record_audio_arecord_vad(duration=duration)
        if wav_path:
            return wav_path

        # arecord 失敗時最後嘗試 ffmpeg（若可用）
        if shutil.which("ffmpeg") is not None:
            return self._record_audio_ffmpeg(duration=duration, allow_manual_stop=allow_manual_stop)
        return ""

    def _record_audio_ffmpeg(self, duration: Optional[int] = None, allow_manual_stop: bool = False) -> str:
        """桌面/WSL 友善錄音：用 ffmpeg 依固定秒數錄音。"""
        max_seconds = int(duration or self.default_duration)
        output_path = Path(RECORDINGS_DIR) / "latest.wav"

        # WSL + PulseAudio 路徑：使用 default 輸入即可。
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "pulse",
            "-i",
            "default",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-t",
            str(max_seconds),
            str(output_path),
        ]

        try:
            print(f"⏺️ 錄音中（ffmpeg，最長 {max_seconds}s）...")
            if allow_manual_stop:
                print("⏹️  錄音中按 Enter 可提前結束")
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )

                def _wait_for_enter_to_stop() -> None:
                    try:
                        _ = sys.stdin.readline()
                        if proc.poll() is None and proc.stdin is not None:
                            proc.stdin.write("q\n")
                            proc.stdin.flush()
                    except Exception:
                        return

                stopper = threading.Thread(target=_wait_for_enter_to_stop, daemon=True)
                stopper.start()
                proc.wait()
                if proc.returncode not in (0, 255):
                    return ""
            else:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if output_path.exists() and output_path.stat().st_size > 1024:
                print(f"⏱️ 錄音完成（ffmpeg，{max_seconds}s）")
                return str(output_path)
            return ""
        except Exception:
            return ""

    def _record_audio_arecord_vad(self, duration: Optional[int] = None) -> str:
        """arecord pipe + 能量 VAD：說完就停，最多等 max_duration 秒。"""
        import numpy as np
        import wave

        max_seconds = duration or self.default_duration
        RATE = 16000
        CHUNK = 1600          # 0.1 秒
        BYTES_PER_CHUNK = CHUNK * 2  
        ENERGY_THRESH = 500
        SILENCE_CHUNKS = 10   # 靜音超過 1.0 秒就停
        MIN_SPEECH_CHUNKS = 2

        cmd = [
            "arecord", "-D", self.device,
            "-r", str(RATE), "-c", "1", "-f", "S16_LE",
            "-t", "raw",      # 不寫檔，raw PCM 輸出到 stdout
        ]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("❌ 找不到 arecord")
            return ""

        frames = []
        silence_count = 0
        speech_count = 0

        try:
            for _ in range(int(max_seconds * RATE / CHUNK)):
                data = proc.stdout.read(BYTES_PER_CHUNK)
                if not data or len(data) < BYTES_PER_CHUNK:
                    break
                frames.append(data)
                samples = np.frombuffer(data, dtype=np.int16)
                energy = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

                if energy > ENERGY_THRESH:
                    speech_count += 1
                    silence_count = 0
                elif speech_count > 0:
                    silence_count += 1
                    if silence_count >= SILENCE_CHUNKS and speech_count >= MIN_SPEECH_CHUNKS:
                        break
        finally:
            proc.terminate()
            proc.wait()

        if speech_count < MIN_SPEECH_CHUNKS:
            return ""

        output_path = Path(RECORDINGS_DIR) / "latest.wav"
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))

        print(f"⏱️ VAD 錄音完成（{len(frames) * CHUNK / RATE:.1f}s / 最多 {max_seconds}s）")
        return str(output_path)
    
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