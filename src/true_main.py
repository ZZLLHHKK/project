import os
import sys
from pathlib import Path
from typing import Any

RUNTIME_MODE = os.environ.get("RUNTIME_MODE", "hardware").strip().lower()
if RUNTIME_MODE == "desktop":
    os.environ.setdefault("DHT11_ENABLED", "0")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("TTS_ENABLED", "1")
else:
    os.environ.setdefault("DHT11_ENABLED", "1")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("TTS_ENABLED", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.audio.speech_processor import SpeechProcessor
except Exception:
    SpeechProcessor = None  # type: ignore[assignment]

from src.runtime import build_runtime
from src.services.console_session import ConsoleSessionService, ConsoleSpeech


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "off", "no")


def run_console_app() -> None:
    runtime_mode = os.environ.get("RUNTIME_MODE", "hardware").strip().lower()
    speech_enabled = _env_flag("SPEECH_ENABLED", runtime_mode != "desktop")
    tts_enabled = _env_flag("TTS_ENABLED", runtime_mode != "desktop")
    sensors_enabled = _env_flag("DHT11_ENABLED", runtime_mode != "desktop")

    print(f"🔧 正在初始化系統... mode={runtime_mode}")
    print("🖥️ 桌面模式：語音命令 + Piper TTS。" if runtime_mode == "desktop" else "🍓 樹莓派模式：使用實體 GPIO 與感測器。")

    runtime = build_runtime(mode=runtime_mode, with_device=True, setup_device=True)
    state = runtime.state

    speech: Any = ConsoleSpeech()
    if SpeechProcessor is not None and (speech_enabled or tts_enabled):
        try:
            speech = SpeechProcessor()
        except Exception as exc:
            print(f"⚠️ 語音系統初始化失敗，改用文字模式: {exc}")
            speech_enabled = False
            tts_enabled = False
    elif speech_enabled or tts_enabled:
        print("⚠️ SpeechProcessor 不可用，已切換為文字模式。")
        speech_enabled = False
        tts_enabled = False

    device = runtime.device
    scheduler = getattr(runtime.agent, "scheduler", None)

    try:
        if device is None:
            raise RuntimeError("runtime device is not initialized")
        service = ConsoleSessionService(
            state=state,
            agent=runtime.agent,
            speech=speech,
            device=device,
            speech_enabled=speech_enabled,
            tts_enabled=tts_enabled,
            sensors_enabled=sensors_enabled,
            scheduler=scheduler,
        )
        service.run()
    finally:
        if device is not None:
            try:
                device.cleanup()
            except Exception as exc:
                print(f"⚠️ 清理硬體時發生錯誤: {exc}")


def main() -> None:
    run_console_app()


if __name__ == "__main__":
    main()
