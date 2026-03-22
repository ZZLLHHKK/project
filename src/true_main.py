import os
import ctypes
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple




# ==========================================
# 🔇 抑制 ALSA 無用警告訊息
# ==========================================
try:
    ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
        None, ctypes.c_char_p, ctypes.c_int,
        ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
    )

    def _alsa_error_handler(filename, line, function, err, fmt):
        pass  # 靜默忽略

    _c_alsa_error_handler = ERROR_HANDLER_FUNC(_alsa_error_handler)
    asound = ctypes.cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(_c_alsa_error_handler)
except Exception:
    pass  # 找不到 libasound 就跳過


# 先設定環境變數，避免某些模組在 import 時就讀取到錯誤設定
os.environ["DHT11_ENABLED"] = "1"
os.environ["MOCK_GPIO"] = "0"  # 如果你的 device_controller 有用到這個環境變數



PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.state_manager import StateManager
from src.core.router import Router
from src.core.parser import DEFAULT_PARSER
from src.llm.llm_engine import LLMEngine
from src.llm.prompt_builder import PromptBuilder
from src.devices.device_controller import DeviceController

try:
    from src.utils.wait_wakeword import wait_for_wake_word
    HAS_WAKEWORD_ENGINE = True
except Exception:
    wait_for_wake_word = None  # type: ignore
    HAS_WAKEWORD_ENGINE = False

# ==========================================
# 🎤 語音與音效模組設定
# ==========================================
try:
    import speech_recognition as sr
    HAS_AUDIO = True
except ImportError:
    sr = None  # type: ignore
    HAS_AUDIO = False
    print("⚠️ 未偵測到 speech_recognition 模組，將退回鍵盤輸入模式。")


def speak(text: str) -> None:
    """
    文字轉語音輸出。
    目前先以印出為主，之後可接上真正的 TTS。
    """
    print(f"\n🔊 AI 語音: {text}")
    # TODO: 實作真正的 TTS
    # 例如：
    # os.system(f'espeak -v zh "{text}"')


# 💡 修正點：統一使用 Any 或不指定型別，消滅 Pylance 的 Variable not allowed 警告
def listen(recognizer: Any, mic: Any, prompt_msg: str) -> str:
    
    """透過麥克風聆聽並轉換為文字"""

    if not HAS_AUDIO or recognizer is None or mic is None:
        return ""

    print(prompt_msg, end="", flush=True)
    with mic as source:
        # 自動適應環境噪音
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("\n⚙️ 語音辨識中...", end="", flush=True)
            text = recognizer.recognize_google(audio, language="zh-TW")
            print(f" [你說了: {text}]")
            return text
        except Exception: # 簡化錯誤處理，確保不閃退
            return ""


def print_dashboard(state: StateManager) -> None:
    print("\n" + "=" * 40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.setpoint_temp}°C (環境: {state.ambient_temp}°C)")
    print(f"💨 風扇狀態: {state.fan_state}")
    print(
        "💡 燈光狀態: "
        f"客廳({state.led_states.get('LIVING', 'off')}) | "
        f"廚房({state.led_states.get('KITCHEN', 'off')}) | "
        f"客房({state.led_states.get('GUEST', 'off')})"
    )
    print("=" * 40 + "\n")


def read_environment(device: DeviceController) -> Tuple[Optional[float], Optional[float]]:
    """
    嘗試讀取環境溫濕度。
    若裝置未實作或讀取失敗，回傳 (None, None)。
    """
    try:
        data = device.get_environment_data()
        if isinstance(data, tuple) and len(data) == 2:
            return data[0], data[1]
        return None, None
    except AttributeError:
        return None, None
    except Exception as e:
        print(f"⚠️ 環境資料讀取失敗: {e}")
        return None, None


def main() -> None:
    print("🔧 正在初始化實體硬體與語音系統...")

    state = StateManager()
    memory = MemoryAgent()
    router = Router()

    # 初始化 LLM
    prompt_builder = PromptBuilder()
    llm = LLMEngine(prompt_builder=prompt_builder)

    device: Optional[DeviceController] = None

    try:
        # 初始化實體硬體控制器
        device = DeviceController()
        device.setup()

        # 讓硬體同步上次的狀態
        device.set_temp(state.setpoint_temp)
        device.set_fan(state.fan_state)
        for loc, st in state.led_states.items():
            device.set_led(loc, st)

        # 動作執行器（真實操作 GPIO + 儲存狀態）
        def action_executor(actions: List[Dict[str, Any]]) -> None:
            if not actions:
                return

            for a in actions:
                if not isinstance(a, dict):
                    continue

                action_type = a.get("type")

                if action_type == "LED":
                    loc = a.get("location", "LIVING")
                    st = a.get("state", "off")
                    device.set_led(loc, st)

                    current_leds = state.led_states.copy()
                    current_leds[loc] = st
                    state.set_state(led_states=current_leds)
                    print(f"  [實體硬體] 💡 {loc} 燈已切換為 {st}")

                elif action_type == "FAN":
                    st = a.get("state", "off")
                    device.set_fan(st)
                    state.set_state(fan_state=st)
                    print(f"  [實體硬體] 💨 風扇已切換為 {st}")

                elif action_type == "SET_TEMP":
                    val = a.get("value", 25)
                    device.set_temp(val)
                    state.set_state(setpoint_temp=val)
                    print(f"  [實體硬體] 🌡️ 冷氣設定為 {val}°C")

        llm_responder = llm.get_adapter_responder(state, action_executor=action_executor)

        # 組合 Agent
        agent = SmartHomeAgent(
            router=router,
            parser=DEFAULT_PARSER,
            memory=memory,
            state=state,
            action_executor=action_executor,
            llm_responder=llm_responder,
        )

        # 準備語音模組
        recognizer = None
        mic = None
        if HAS_AUDIO:
            try:
                recognizer = sr.Recognizer()
                mic = sr.Microphone(sample_rate=16000)
                print("✅ 語音模組載入成功！")
            except Exception as e:
                print(f"❌ 麥克風初始化失敗，將退回鍵盤輸入模式: {e}")
                recognizer = None
                mic = None

        print("✅ 系統準備就緒！")
        speak("系統已經啟動，隨時可以叫我。")
        print_dashboard(state)

        is_standby = True
        use_wakeword_engine = HAS_WAKEWORD_ENGINE
        error_count = 0
        MAX_ERRORS = 5

        while True:
            try:
                # 取得實體環境溫濕度
                env_temp, env_hum = read_environment(device)
                if env_temp is not None:
                    state.ambient_temp = env_temp
                if env_hum is not None:
                    state.ambient_humidity = env_hum

                # --- 收音與輸入階段 ---
                if HAS_AUDIO and recognizer and mic:
                    if is_standby:
                        if use_wakeword_engine and wait_for_wake_word is not None:
                            print("\n[🟡 待機中] 麥克風喚醒詞監聽中 (HI MY PI)... ", end="", flush=True)
                            detected = wait_for_wake_word()
                            if detected:
                                print("[已偵測到喚醒詞]")
                                user_input = "hi my pi"
                            else:
                                use_wakeword_engine = False
                                print("\n⚠️ 喚醒詞引擎不可用，改用一般語音辨識喚醒。")
                                user_input = listen(recognizer, mic, "\n[🟡 待機中] 等待喚醒詞 (HI MY PI)... ")
                        else:
                            user_input = listen(recognizer, mic, "\n[🟡 待機中] 等待喚醒詞 (HI MY PI)... ")
                    else:
                        user_input = listen(recognizer, mic, "\n[🟢 聆聽中] 🗣️ 請說指令 (說 '掰掰' 待機)... ")
                else:
                    prompt = "\n[🟡 待機中] 請輸入喚醒詞: " if is_standby else "\n[🟢 聆聽中] 請輸入指令: "
                    user_input = input(prompt)

                clean_input = (user_input or "").strip()

                if not clean_input:
                    continue

                if clean_input.lower() in ["exit", "quit"]:
                    speak("系統關閉中，再見。")
                    break

                # --- 模式 A：待機模式 ---
                if is_standby:
                    wake_words = ["hi my pi", "嗨", "管家", "my pi", "my pie"]
                    if any(w in clean_input.lower() for w in wake_words):
                        is_standby = False
                        speak("我在，請說！")
                    continue

                # --- 模式 B：運作模式 ---
                print(f"\n🧠 Agent 思考中...")

                result = agent.handle(
                    clean_input,
                    current_temp=state.setpoint_temp,
                    ambient_temp=state.ambient_temp,
                )

                print(f"🤖 [意圖]: {result.intent.value} | [路由]: {result.route_type.value}")

                if result.error:
                    speak(result.error)
                else:
                    speak(result.reply)

                # 檢查是否發出待機指令
                should_standby = False
                for action in getattr(result, "actions", []):
                    if isinstance(action, dict) and action.get("type") == "ENTER_STANDBY":
                        should_standby = True
                        break

                print_dashboard(state)

                if should_standby:
                    is_standby = True
                    print("💤 === 系統進入待機模式 ===")

                error_count = 0

            except KeyboardInterrupt:
                speak("強制中斷，系統關閉中。")
                break
            except Exception as e:
                error_count += 1
                print(f"\n❌ 發生未預期錯誤: {e}")

                if error_count >= MAX_ERRORS:
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