import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 在 import 其他模組前先決定執行模式，避免硬體設定在載入期就被鎖死。
RUNTIME_MODE = os.environ.get("RUNTIME_MODE", "hardware").strip().lower()
if RUNTIME_MODE == "desktop":
    os.environ.setdefault("DHT11_ENABLED", "0")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("WAKEWORD_ENABLED", "0")
    os.environ.setdefault("TTS_ENABLED", "1")
else:
    os.environ.setdefault("DHT11_ENABLED", "1")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("WAKEWORD_ENABLED", "1")
    os.environ.setdefault("TTS_ENABLED", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.audio.speech_processor import SpeechProcessor
except Exception:
    SpeechProcessor = None  # type: ignore[assignment]

from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.parser import DEFAULT_PARSER
from src.core.router import Router
from src.core.state_manager import StateManager
from src.devices.device_controller import DeviceController
from src.llm.llm_engine import LLMEngine
from src.llm.prompt_builder import PromptBuilder


def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "off", "no")


class ConsoleSpeech:
    """Desktop fallback for speech input/output when audio engines are disabled."""

    def speech_to_text(self, duration: int = 5) -> str:
        return ""

    def text_to_speech(self, text: str) -> None:
        print(f"🔊 [文字語音模擬]: {text}")


def say(speech: Any, text: str, tts_enabled: bool) -> None:
    if tts_enabled and hasattr(speech, "text_to_speech"):
        try:
            speech.text_to_speech(text)
            return
        except Exception as e:
            print(f"⚠️ TTS 播放失敗，改為文字輸出: {e}")
    print(f"🔊 [回覆]: {text}")



def print_dashboard(state: StateManager) -> None:
    print("\n" + "=" * 40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.setpoint_temp}°C (環境: {state.ambient_temp}°C)")
    print(f"💧 當前環境濕度: {state.ambient_humidity}%")
    print(f"💨 風扇狀態: {state.fan_state}")
    print(
        "💡 燈光狀態: "
        f"客廳({state.led_states.get('LIVING', 'off')}) | "
        f"廚房({state.led_states.get('KITCHEN', 'off')}) | "
        f"客房({state.led_states.get('GUEST', 'off')})"
    )
    print("=" * 40 + "\n")


def read_environment(device: DeviceController) -> Tuple[Optional[int], Optional[int]]:
    """從硬體讀取溫濕度；若失敗則回傳 (None, None)。"""
    temp: Optional[int] = None
    humidity: Optional[int] = None

    try:
        temp = device.get_temp()
    except Exception as e:
        print(f"⚠️ 環境溫度讀取失敗: {e}")

    try:
        humidity = device.get_humidity()
    except Exception as e:
        print(f"⚠️ 環境濕度讀取失敗: {e}")

    return temp, humidity


# 喚醒詞引擎
if _env_flag("WAKEWORD_ENABLED", RUNTIME_MODE != "desktop"):
    try:
        from src.utils.wait_wakeword import wait_for_wake_word

        HAS_WAKEWORD_ENGINE = True
    except Exception:
        wait_for_wake_word = None  # type: ignore
        HAS_WAKEWORD_ENGINE = False
else:
    wait_for_wake_word = None  # type: ignore
    HAS_WAKEWORD_ENGINE = False


def is_wake_word(text: str) -> bool:
    clean = (text or "").strip().lower()
    wake_words = ["hi my pi", "my pi", "my pie", "hi", "開機", "在嗎", "醒來", "嗨"]
    return any(word in clean for word in wake_words)


def collect_text_input(speech: Any, is_standby: bool, use_speech: bool = True) -> Tuple[str, bool]:
    """
    主要輸入來源：SpeechProcessor（arecord + whisper）。
    use_speech=False 時直接走鍵盤，不嘗試語音辨識。
    回傳 (text, speech_ok)。speech_ok=False 代表麥克風流程失敗，主流程應降級。
    """
    if is_standby:
        if use_speech:
            print("\n[🟡 待機中] 請說喚醒詞...", flush=True)
            try:
                text = speech.speech_to_text(duration=2)
                if text:
                    return text, True
            except Exception as e:
                print(f"⚠️ 語音辨識失敗: {e}")
                return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), False
        return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), True

    if use_speech:
        print("\n[🟢 聆聽中] 🗣️ 請說指令...", flush=True)
        try:
            text = speech.speech_to_text(duration=getattr(speech, "default_duration", 5))
            if text:
                return text, True
        except Exception as e:
            print(f"⚠️ 語音辨識失敗: {e}")
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



def build_action_executor(device: DeviceController, state: StateManager):
    def action_executor(actions: List[Dict[str, Any]]) -> None:
        if not actions:
            return

        for action in actions:
            if not isinstance(action, dict):
                continue

            action_type = action.get("type")

            if action_type == "LED":
                loc = str(action.get("location", "LIVING")).upper()
                st = str(action.get("state", "off")).lower()
                device.set_led(loc, st)

                new_led_states = dict(state.led_states)
                new_led_states[loc] = st
                state.set_state(led_states=new_led_states)
                print(f"  [實體硬體] 💡 {loc} 燈已切換為 {st}")

            elif action_type == "FAN":
                st = str(action.get("state", "off")).lower()
                device.set_fan(st)
                state.set_state(fan_state=st)
                print(f"  [實體硬體] 💨 風扇已切換為 {st}")

            elif action_type == "SET_TEMP":
                val = int(action.get("value", 25))
                device.set_temp(val)
                state.set_state(setpoint_temp=val)
                print(f"  [實體硬體] 🌡️ 冷氣設定為 {val}°C")

    return action_executor


def main() -> None:
    runtime_mode = os.environ.get("RUNTIME_MODE", "hardware").strip().lower()
    speech_enabled = _env_flag("SPEECH_ENABLED", runtime_mode != "desktop")
    wakeword_enabled = _env_flag("WAKEWORD_ENABLED", runtime_mode != "desktop")
    tts_enabled = _env_flag("TTS_ENABLED", runtime_mode != "desktop")
    sensors_enabled = _env_flag("DHT11_ENABLED", runtime_mode != "desktop")

    print(f"🔧 正在初始化系統... mode={runtime_mode}")
    if runtime_mode == "desktop":
        print("🖥️ 桌面模式：鍵盤喚醒詞 + 語音命令 + Piper TTS。")
    else:
        print("🍓 樹莓派模式：使用實體 GPIO 與感測器。")

    state = StateManager()
    memory = MemoryAgent()
    router = Router()

    if runtime_mode == "desktop":
        state.ambient_temp = int(os.environ.get("DESKTOP_AMBIENT_TEMP", state.ambient_temp or 26))
        state.ambient_humidity = int(os.environ.get("DESKTOP_AMBIENT_HUMIDITY", state.ambient_humidity or 60))

    speech: Any = ConsoleSpeech()
    if SpeechProcessor is not None and (speech_enabled or tts_enabled):
        try:
            speech = SpeechProcessor()
        except Exception as e:
            print(f"⚠️ 語音系統初始化失敗，改用文字模式: {e}")
            speech_enabled = False
            wakeword_enabled = False
            tts_enabled = False
    elif speech_enabled or tts_enabled:
        print("⚠️ SpeechProcessor 不可用，已切換為文字模式。")
        speech_enabled = False
        wakeword_enabled = False
        tts_enabled = False

    prompt_builder = PromptBuilder()
    llm = LLMEngine(prompt_builder=prompt_builder)

    device: Optional[DeviceController] = None

    try:
        device = DeviceController()
        device.setup()

        # 讓硬體同步上次狀態
        device.set_temp(state.setpoint_temp)
        device.set_fan(state.fan_state)
        for loc, st in state.led_states.items():
            device.set_led(loc, st)

        action_executor = build_action_executor(device, state)
        llm_responder = llm.get_adapter_responder(state, action_executor=action_executor)

        agent = SmartHomeAgent(
            router=router,
            parser=DEFAULT_PARSER,
            memory=memory,
            state=state,
            action_executor=action_executor,
            llm_responder=llm_responder,
        )

        print("✅ 系統準備就緒！")
        say(speech, "系統已經啟動，隨時可以叫我。", tts_enabled)
        print_dashboard(state)
        print_controls()

        is_standby = True
        has_wakeword_engine = HAS_WAKEWORD_ENGINE and wakeword_enabled and speech_enabled
        use_command_speech_input = speech_enabled
        command_record_seconds = int(os.environ.get("COMMAND_RECORD_SECONDS", "5"))
        command_record_seconds = max(1, min(15, command_record_seconds))

        if hasattr(speech, "default_duration"):
            try:
                speech.default_duration = command_record_seconds
            except Exception:
                pass

        capture_status = detect_capture_status(speech)
        print(f"[啟動狀態] standby_input=keyboard, command_input={'voice' if use_command_speech_input else 'keyboard'}, capture={capture_status}, rec={command_record_seconds}s")

        error_count = 0
        max_errors = 3

        while True:
            try:
                if sensors_enabled:
                    env_temp, env_hum = read_environment(device)
                    if env_temp is not None:
                        state.ambient_temp = env_temp
                    if env_hum is not None:
                        state.ambient_humidity = env_hum

                if is_standby and has_wakeword_engine and wait_for_wake_word is not None:
                    print("\n[🟡 待機中] 麥克風喚醒詞監聽中 (HI MY PI)... ", end="", flush=True)
                    detected = wait_for_wake_word()
                    if detected:
                        print("[已偵測到喚醒詞]")
                        user_input = "hi my pi"
                    else:
                        has_wakeword_engine = False
                        print("\n⚠️ 喚醒詞引擎不可用，改用鍵盤輸入模式。")
                        user_input, _ = collect_text_input(speech, is_standby=True, use_speech=False)
                elif is_standby:
                    # 未使用喚醒詞引擎時，待機階段固定走鍵盤喚醒詞。
                    user_input, _ = collect_text_input(speech, is_standby=True, use_speech=False)
                else:
                    user_input, speech_ok = collect_text_input(
                        speech,
                        is_standby=is_standby,
                        use_speech=use_command_speech_input,
                    )
                    if not speech_ok and use_command_speech_input:
                        use_command_speech_input = False
                        print("⚠️ 命令語音辨識失敗，已自動降級為鍵盤輸入模式。")

                clean_input = (user_input or "").strip()
                if not clean_input:
                    continue

                # 互動控制指令：可在執行中切換輸入模式與錄音長度
                lower_input = clean_input.lower()
                if lower_input.startswith("/"):
                    if lower_input == "/help":
                        print_controls()
                        continue
                    if lower_input == "/k":
                        use_command_speech_input = False
                        print("⌨️ 命令輸入已快速切換為鍵盤模式。")
                        continue
                    if lower_input == "/v":
                        use_command_speech_input = True
                        print("🎙️ 命令輸入已快速切換為語音模式。")
                        continue
                    if lower_input in ("/exit", "/quit"):
                        say(speech, "系統關閉中，再見。", tts_enabled)
                        break
                    if lower_input == "/voice":
                        current_voice = os.environ.get("TTS_MODEL_PATH", "(default) data/models/voice.onnx")
                        print(f"[語音模型] {current_voice}")
                        continue
                    if lower_input.startswith("/voice "):
                        model_path = clean_input.split(maxsplit=1)[1].strip()
                        if not model_path:
                            print("⚠️ 用法: /voice /path/to/model.onnx")
                            continue
                        p = Path(model_path)
                        if not p.exists():
                            print(f"⚠️ 找不到模型檔: {model_path}")
                            continue
                        if p.suffix.lower() != ".onnx":
                            print("⚠️ 模型副檔名需為 .onnx")
                            continue
                        os.environ["TTS_MODEL_PATH"] = str(p)
                        print(f"🗣️ 已切換語音模型: {p}")
                        continue
                    if lower_input == "/status":
                        mode_text = "voice" if use_command_speech_input else "keyboard"
                        llm_status = getattr(llm, "service_mode", "unknown")
                        capture_status = detect_capture_status(speech)
                        print(f"[狀態] standby={is_standby}, command_input={mode_text}, capture={capture_status}, rec={command_record_seconds}s, llm={llm_status}")
                        continue
                    if lower_input == "/standby":
                        is_standby = True
                        print("💤 已切換到待機模式。")
                        continue
                    if lower_input.startswith("/mode "):
                        target = lower_input.split(maxsplit=1)[1].strip()
                        if target == "voice":
                            use_command_speech_input = True
                            print("🎙️ 命令輸入已切換為語音模式。")
                        elif target == "keyboard":
                            use_command_speech_input = False
                            print("⌨️ 命令輸入已切換為鍵盤模式。")
                        else:
                            print("⚠️ 用法: /mode voice 或 /mode keyboard")
                        continue
                    if lower_input.startswith("/rec "):
                        raw = lower_input.split(maxsplit=1)[1].strip()
                        try:
                            sec = int(raw)
                            sec = max(1, min(15, sec))
                            command_record_seconds = sec
                            if hasattr(speech, "default_duration"):
                                speech.default_duration = command_record_seconds
                            print(f"⏱️ 命令錄音秒數已設定為 {command_record_seconds}s")
                        except Exception:
                            print("⚠️ 用法: /rec 3（秒數範圍 1~15）")
                        continue
                    print("⚠️ 未知控制指令，輸入 /help 查看可用指令。")
                    continue

                if clean_input.lower() in ["exit", "quit"]:
                    say(speech, "系統關閉中，再見。", tts_enabled)
                    break

                if is_standby:
                    if is_wake_word(clean_input):
                        is_standby = False
                        say(speech, "我在，請說！", tts_enabled)
                    continue

                print("\n🧠 Agent 思考中...")
                result = agent.handle(
                    clean_input,
                    current_temp=state.setpoint_temp,
                    ambient_temp=state.ambient_temp,
                )

                print(f"🤖 [意圖]: {result.intent.value} | [路由]: {result.route_type.value}")
                if result.error:
                    print(f"⚠️ [錯誤]: {result.error}")
                    say(speech, result.error, tts_enabled)
                else:
                    print(f"🔊 [語音回覆]: {result.reply}")
                    say(speech, result.reply, tts_enabled)

                should_standby = any(
                    isinstance(action, dict) and action.get("type") == "ENTER_STANDBY"
                    for action in getattr(result, "actions", [])
                )

                print_dashboard(state)
                if should_standby:
                    is_standby = True
                    print("💤 === 系統進入待機模式 ===")

                error_count = 0

            except KeyboardInterrupt:
                say(speech, "強制中斷，系統關閉中。", tts_enabled)
                break
            except Exception as e:
                error_count += 1
                print(f"\n❌ 發生未預期錯誤: {e}")
                if error_count >= max_errors:
                    print("❌ 錯誤過多，系統停止。")
                    break
                time.sleep(1)

    finally:
        if device is not None:
            try:
                device.cleanup()
            except Exception as e:
                print(f"⚠️ 清理硬體時發生錯誤: {e}")


if __name__ == "__main__":
    main()