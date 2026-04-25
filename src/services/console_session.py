from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from src.core.state_manager import StateManager
from src.devices.device_controller import DeviceController
from src.services.command_service import execute_text_command


class ConsoleSpeech:
    def speech_to_text(self, duration: int = 5) -> str:
        return ""

    def text_to_speech(self, text: str) -> None:
        print(f"[TTS] {text}")


def say(speech: Any, text: str, tts_enabled: bool) -> None:
    if tts_enabled and hasattr(speech, "text_to_speech"):
        try:
            speech.text_to_speech(text)
            return
        except Exception as exc:
            print(f"⚠️ TTS 播放失敗，改為文字輸出: {exc}")
    print(f"🔊 [回覆]: {text}")


def print_dashboard(state: StateManager) -> None:
    print("\n" + "=" * 40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.temperature}°C (環境: {state.ambient_temp}°C)")
    print(f"💧 當前環境濕度: {state.ambient_humidity}%")
    print(f"💨 風扇狀態: {state.fan}")
    print(
        "💡 燈光狀態: "
        f"客廳({state.light.get('LIVING', 'off')}) | "
        f"廚房({state.light.get('KITCHEN', 'off')}) | "
        f"客房({state.light.get('GUEST', 'off')})"
    )
    if state.needs_clarification and state.clarification_message:
        print(f"❓ 待澄清: {state.clarification_message}")
    print("=" * 40 + "\n")


def read_environment(device: DeviceController) -> Tuple[Optional[int], Optional[int]]:
    temp: Optional[int] = None
    humidity: Optional[int] = None
    try:
        temp = device.get_temp()
    except Exception as exc:
        print(f"⚠️ 環境溫度讀取失敗: {exc}")
    try:
        humidity = device.get_humidity()
    except Exception as exc:
        print(f"⚠️ 環境濕度讀取失敗: {exc}")
    return temp, humidity


def is_wake_word(text: str) -> bool:
    clean = (text or "").strip().lower()
    wake_words = ["hi my pi", "my pi", "my pie", "hi", "開機", "在嗎", "醒來", "嗨"]
    return any(word in clean for word in wake_words)


def collect_text_input(speech: Any, is_standby: bool, use_speech: bool = True) -> Tuple[str, bool]:
    if is_standby:
        if use_speech:
            print("\n[🟡 待機中] 請說喚醒詞...", flush=True)
            try:
                text = speech.speech_to_text(duration=2)
                if text:
                    return text, True
            except Exception as exc:
                print(f"⚠️ 語音辨識失敗: {exc}")
                return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), False
        return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), True

    if use_speech:
        print("\n[🟢 聆聽中] 🗣️ 請說指令...", flush=True)
        try:
            text = speech.speech_to_text(duration=getattr(speech, "default_duration", 5))
            if text:
                return text, True
        except Exception as exc:
            print(f"⚠️ 語音辨識失敗: {exc}")
            return input("[🟢 聆聽中] 請輸入指令（或 exit 離開）: ").strip(), False
    return input("[🟢 聆聽中] 請輸入指令（或 exit 離開）: ").strip(), True


def print_controls() -> None:
    print("\n[控制指令]")
    print("  /help               顯示控制指令")
    print("  /k                  快速切到鍵盤命令輸入")
    print("  /v                  快速切到語音命令輸入")
    print("  /mode voice         命令輸入改為語音")
    print("  /mode keyboard      命令輸入改為鍵盤")
    print("  /rec <秒數>         設定語音錄音秒數（1~15）")
    print("  /voice              顯示目前語音模型")
    print("  /voice <模型路徑>   切換 Piper 語音模型 (.onnx)")
    print("  /status             顯示目前輸入模式與錄音秒數")
    print("  /standby            立即進入待機")
    print("  /exit               結束程式")


def detect_capture_status(speech: Any) -> str:
    if hasattr(speech, "describe_capture_path"):
        try:
            return str(speech.describe_capture_path())
        except Exception:
            return "unknown"
    return "keyboard(console)"


class ConsoleSessionService:
    def __init__(
        self,
        *,
        state: StateManager,
        agent: Any,
        speech: Any,
        device: DeviceController,
        speech_enabled: bool,
        wakeword_enabled: bool,
        tts_enabled: bool,
        sensors_enabled: bool,
        wait_for_wake_word: Callable[[], bool] | None,
        has_wakeword_engine: bool,
    ) -> None:
        self.state = state
        self.agent = agent
        self.speech = speech
        self.device = device
        self.speech_enabled = speech_enabled
        self.wakeword_enabled = wakeword_enabled
        self.tts_enabled = tts_enabled
        self.sensors_enabled = sensors_enabled
        self.wait_for_wake_word = wait_for_wake_word
        self.has_wakeword_engine = has_wakeword_engine

        self.is_standby = True
        self.use_command_speech_input = speech_enabled
        self.command_record_seconds = max(1, min(15, int(os.environ.get("COMMAND_RECORD_SECONDS", "5"))))
        if hasattr(self.speech, "default_duration"):
            try:
                self.speech.default_duration = self.command_record_seconds
            except Exception:
                pass

    def run(self) -> None:
        print("✅ 系統準備就緒！")
        say(self.speech, "系統已經啟動，隨時可以叫我。", self.tts_enabled)
        print_dashboard(self.state)
        print_controls()

        active_wakeword_engine = self.has_wakeword_engine and self.wakeword_enabled and self.speech_enabled
        capture_status = detect_capture_status(self.speech)
        print(
            f"[啟動狀態] standby_input=keyboard, "
            f"command_input={'voice' if self.use_command_speech_input else 'keyboard'}, "
            f"capture={capture_status}, rec={self.command_record_seconds}s"
        )

        error_count = 0
        max_errors = 3

        while True:
            try:
                if self.sensors_enabled:
                    self._update_environment()

                user_input, active_wakeword_engine = self._collect_input(active_wakeword_engine)
                clean_input = (user_input or "").strip()
                if not clean_input:
                    continue

                if self._handle_control_command(clean_input):
                    if clean_input.lower() in ("/exit", "/quit"):
                        break
                    continue

                if clean_input.lower() in ["exit", "quit"]:
                    say(self.speech, "系統關閉中，再見。", self.tts_enabled)
                    break

                if self.is_standby:
                    if is_wake_word(clean_input):
                        self.is_standby = False
                        say(self.speech, "我在，請說！", self.tts_enabled)
                    continue

                if self._handle_agent_turn(clean_input):
                    break

                error_count = 0

            except KeyboardInterrupt:
                say(self.speech, "強制中斷，系統關閉中。", self.tts_enabled)
                break
            except Exception as exc:
                error_count += 1
                print(f"\n❌ 發生未預期錯誤: {exc}")
                if error_count >= max_errors:
                    print("❌ 錯誤過多，系統停止。")
                    break
                time.sleep(1)

    def _update_environment(self) -> None:
        env_temp, env_hum = read_environment(self.device)
        if env_temp is not None:
            self.state.ambient_temp = env_temp
        if env_hum is not None:
            self.state.ambient_humidity = env_hum

    def _collect_input(self, active_wakeword_engine: bool) -> tuple[str, bool]:
        if self.is_standby and active_wakeword_engine and self.wait_for_wake_word is not None:
            print("\n[🟡 待機中] 麥克風喚醒詞監聽中 (HI MY PI)... ", end="", flush=True)
            detected = self.wait_for_wake_word()
            if detected:
                print("[已偵測到喚醒詞]")
                return "hi my pi", active_wakeword_engine

            active_wakeword_engine = False
            print("\n⚠️ 喚醒詞引擎不可用，改用鍵盤輸入模式。")
            user_input, _ = collect_text_input(self.speech, is_standby=True, use_speech=False)
            return user_input, active_wakeword_engine

        if self.is_standby:
            user_input, _ = collect_text_input(self.speech, is_standby=True, use_speech=False)
            return user_input, active_wakeword_engine

        user_input, speech_ok = collect_text_input(
            self.speech,
            is_standby=self.is_standby,
            use_speech=self.use_command_speech_input,
        )
        if not speech_ok and self.use_command_speech_input:
            self.use_command_speech_input = False
            print("⚠️ 命令語音辨識失敗，已自動降級為鍵盤輸入模式。")
        return user_input, active_wakeword_engine

    def _handle_control_command(self, clean_input: str) -> bool:
        lower_input = clean_input.lower()
        if not lower_input.startswith("/"):
            return False

        if lower_input == "/help":
            print_controls()
            return True
        if lower_input == "/k":
            self.use_command_speech_input = False
            print("⌨️ 命令輸入已快速切換為鍵盤模式。")
            return True
        if lower_input == "/v":
            self.use_command_speech_input = True
            print("🎙️ 命令輸入已快速切換為語音模式。")
            return True
        if lower_input in ("/exit", "/quit"):
            say(self.speech, "系統關閉中，再見。", self.tts_enabled)
            return True
        if lower_input == "/voice":
            current_voice = os.environ.get("TTS_MODEL_PATH", "(default) data/models/voice.onnx")
            print(f"[語音模型] {current_voice}")
            return True
        if lower_input.startswith("/voice "):
            model_path = clean_input.split(maxsplit=1)[1].strip()
            if not model_path:
                print("⚠️ 用法: /voice /path/to/model.onnx")
                return True
            path = Path(model_path)
            if not path.exists():
                print(f"⚠️ 找不到模型檔: {model_path}")
                return True
            if path.suffix.lower() != ".onnx":
                print("⚠️ 模型副檔名需為 .onnx")
                return True
            os.environ["TTS_MODEL_PATH"] = str(path)
            print(f"🗣️ 已切換語音模型: {path}")
            return True
        if lower_input == "/status":
            mode_text = "voice" if self.use_command_speech_input else "keyboard"
            capture_status = detect_capture_status(self.speech)
            print(f"[狀態] standby={self.is_standby}, command_input={mode_text}, capture={capture_status}, rec={self.command_record_seconds}s")
            return True
        if lower_input == "/standby":
            self.is_standby = True
            print("💤 已切換到待機模式。")
            return True
        if lower_input.startswith("/mode "):
            target = lower_input.split(maxsplit=1)[1].strip()
            if target == "voice":
                self.use_command_speech_input = True
                print("🎙️ 命令輸入已切換為語音模式。")
            elif target == "keyboard":
                self.use_command_speech_input = False
                print("⌨️ 命令輸入已切換為鍵盤模式。")
            else:
                print("⚠️ 用法: /mode voice 或 /mode keyboard")
            return True
        if lower_input.startswith("/rec "):
            raw = lower_input.split(maxsplit=1)[1].strip()
            try:
                seconds = int(raw)
                self.command_record_seconds = max(1, min(15, seconds))
                if hasattr(self.speech, "default_duration"):
                    self.speech.default_duration = self.command_record_seconds
                print(f"⏱️ 命令錄音秒數已設定為 {self.command_record_seconds}s")
            except Exception:
                print("⚠️ 用法: /rec 3（秒數範圍 1~15）")
            return True

        print("⚠️ 未知控制指令，輸入 /help 查看可用指令。")
        return True

    def _handle_agent_turn(self, clean_input: str) -> bool:
        print("\n🧠 Agent 思考中...")
        result = execute_text_command(self.agent, clean_input)

        if result.error:
            print(f"⚠️ [系統錯誤碼]: {result.error}")
        print(f"🔊 [語音回覆]: {result.raw_reply}")
        say(self.speech, result.raw_reply, self.tts_enabled)

        if result.should_shutdown:
            return True

        print_dashboard(self.state)
        if result.should_standby:
            self.is_standby = True
            print("💤 === 系統進入待機模式 ===")
        return False