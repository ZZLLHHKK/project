import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 先設定環境變數，避免某些模組在 import 時就讀取到錯誤設定
os.environ["DHT11_ENABLED"] = "1"
os.environ["MOCK_GPIO"] = "0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audio.speech_processor import SpeechProcessor
from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.parser import DEFAULT_PARSER
from src.core.router import Router
from src.core.state_manager import StateManager
from src.devices.device_controller import DeviceController
from src.llm.llm_engine import LLMEngine
from src.llm.prompt_builder import PromptBuilder

try:
    from src.utils.wait_wakeword import wait_for_wake_word

    HAS_WAKEWORD_ENGINE = True
except Exception:
    wait_for_wake_word = None  # type: ignore
    HAS_WAKEWORD_ENGINE = False


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


def is_wake_word(text: str) -> bool:
    clean = (text or "").strip().lower()
    wake_words = ["hi my pi", "嗨", "管家", "my pi", "my pie"]
    return any(word in clean for word in wake_words)


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


def collect_text_input(speech: SpeechProcessor, is_standby: bool) -> str:
    """
    主要輸入來源：SpeechProcessor（arecord + whisper）。
    若語音失敗，回退到鍵盤輸入，避免主流程卡死。
    """
    if is_standby:
        print("\n[🟡 待機中] 請說喚醒詞...", flush=True)
        text = speech.speech_to_text(duration=2)
        if text:
            return text
        return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip()

    print("\n[🟢 聆聽中] 🗣️ 請說指令...", flush=True)
    text = speech.speech_to_text()
    if text:
        return text
    return input("[🟢 聆聽中] 請輸入指令（或 exit 離開）: ").strip()


def main() -> None:
    print("🔧 正在初始化實體硬體與語音系統...")

    state = StateManager()
    memory = MemoryAgent()
    router = Router()
    speech = SpeechProcessor()

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
        speech.text_to_speech("系統已經啟動，隨時可以叫我。")
        print_dashboard(state)

        is_standby = True
        use_wakeword_engine = HAS_WAKEWORD_ENGINE
        error_count = 0
        max_errors = 5

        while True:
            try:
                env_temp, env_hum = read_environment(device)
                if env_temp is not None:
                    state.ambient_temp = env_temp
                if env_hum is not None:
                    state.ambient_humidity = env_hum

                if is_standby and use_wakeword_engine and wait_for_wake_word is not None:
                    print("\n[🟡 待機中] 麥克風喚醒詞監聽中 (HI MY PI)... ", end="", flush=True)
                    detected = wait_for_wake_word()
                    if detected:
                        print("[已偵測到喚醒詞]")
                        user_input = "hi my pi"
                    else:
                        use_wakeword_engine = False
                        print("\n⚠️ 喚醒詞引擎不可用，改用語音辨識流程。")
                        user_input = collect_text_input(speech, is_standby=True)
                else:
                    user_input = collect_text_input(speech, is_standby=is_standby)

                clean_input = (user_input or "").strip()
                if not clean_input:
                    continue

                if clean_input.lower() in ["exit", "quit"]:
                    speech.text_to_speech("系統關閉中，再見。")
                    break

                if is_standby:
                    if is_wake_word(clean_input):
                        is_standby = False
                        speech.text_to_speech("我在，請說！")
                    continue

                print("\n🧠 Agent 思考中...")
                result = agent.handle(
                    clean_input,
                    current_temp=state.setpoint_temp,
                    current_temp=state.setpoint_temp,
                    ambient_temp=state.ambient_temp,
                )

                print(f"🤖 [意圖]: {result.intent.value} | [路由]: {result.route_type.value}")
                if result.error:
                    speech.text_to_speech(result.error)
                else:
                    speech.text_to_speech(result.reply)

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
                speech.text_to_speech("強制中斷，系統關閉中。")
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