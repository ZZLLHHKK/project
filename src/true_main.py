import sys
import os
from pathlib import Path
import time

# 🚨 解開硬體封印！啟用實體 DHT11 與 GPIO
os.environ["DHT11_ENABLED"] = "1" 
os.environ["MOCK_GPIO"] = "0" # 如果你的 device_controller 有設定這個環境變數的話

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

# ==========================================
# 🎤 語音與音效模組設定
# ==========================================
try:
    import speech_recognition as sr
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print("⚠️ 未偵測到 speech_recognition 模組，將退回鍵盤輸入模式。")

def speak(text: str):
    """
    文字轉語音 (TTS) 輸出到喇叭。
    這裡先印出文字，並提供幾種常見的 TTS 實作建議供你日後擴充。
    """
    print(f"\n🔊 AI 語音: {text}")
    # TODO: 實作真實喇叭發音
    # 方法 1 (Mac/Linux 原生): os.system(f'espeak -v zh "{text}"')
    # 方法 2 (gTTS - 需網路): 
    #   tts = gTTS(text=text, lang='zh-tw')
    #   tts.save("reply.mp3")
    #   os.system("mpg321 reply.mp3")

def listen(recognizer: sr.Recognizer, mic: sr.Microphone, prompt_msg: str) -> str:
    """透過麥克風聆聽並轉換為文字"""
    print(prompt_msg, end="", flush=True)
    with mic as source:
        # 自動適應環境噪音 (很重要，避免一直收到雜音)
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            # 聽取聲音，設定 timeout 避免程式死當
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("\n⚙️ 語音辨識中...", end="", flush=True)
            # 使用 Google 的免費 STT 服務 (需網路)
            text = recognizer.recognize_google(audio, language='zh-TW')
            print(f" [你說了: {text}]")
            return text
        except sr.WaitTimeoutError:
            return ""  # 沒聽到聲音
        except sr.UnknownValueError:
            return ""  # 聽不懂
        except sr.RequestError as e:
            print(f"\n❌ 語音服務連線失敗: {e}")
            return ""

def print_dashboard(state: StateManager):
    print("\n" + "="*40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.setpoint_temp}°C (環境: {state.ambient_temp}°C)")
    print(f"💨 風扇狀態: {state.fan_state}")
    print(f"💡 燈光狀態: 客廳({state.led_states.get('LIVING', 'off')}) | 廚房({state.led_states.get('KITCHEN', 'off')}) | 客房({state.led_states.get('GUEST', 'off')})")
    print("="*40 + "\n")

def main():
    print("🔧 正在初始化實體硬體與語音系統...")

    state = StateManager()
    memory = MemoryAgent()
    router = Router()

    # 初始化 LLM
    prompt_builder = PromptBuilder()
    llm = LLMEngine(prompt_builder=prompt_builder)

    # 初始化實體硬體控制器 (此時應該會去抓真實的 GPIO 腳位了)
    device = DeviceController()
    device.setup()  

    # 讓硬體同步上次的狀態
    device.set_temp(state.setpoint_temp)
    device.set_fan(state.fan_state)
    for loc, st in state.led_states.items():
        device.set_led(loc, st)

    # 動作執行器 (真實操作 GPIO + 儲存狀態)
    def action_executor(actions: list) -> None:
        if not actions:
            return
        for a in actions:
            action_type = a.get("type")
            if action_type == "LED":
                loc = a.get("location", "LIVING")
                st = a.get("state", "off")
                device.set_led(loc, st) # 真實電流送出！
                
                current_leds = state.led_states.copy()
                current_leds[loc] = st
                state.set_state(led_states=current_leds)
                print(f"  [實體硬體] 💡 {loc} 燈已切換為 {st}")
                
            elif action_type == "FAN":
                st = a.get("state", "off")
                device.set_fan(st) # 真實風扇啟動！
                state.set_state(fan_state=st)
                print(f"  [實體硬體] 💨 風扇已切換為 {st}")
                
            elif action_type == "SET_TEMP":
                val = a.get("value", 25)
                device.set_temp(val)
                state.set_state(setpoint_temp=val)
                print(f"  [實體硬體] 🌡️ 冷氣設定為 {val}°C")
        
    llm_responder = llm.get_adapter_responder(state, action_executor=action_executor)

    # 組合 Agent 大腦
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
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        print("✅ 語音模組載入成功！")

    print("✅ 系統準備就緒！")
    speak("系統已經啟動，隨時可以叫我。")
    print_dashboard(state)

    is_standby = True
    
    # 主迴圈
    while True:
        try:
            # 取得實體環境溫濕度 (如果你有實作讀取 DHT11 的函數的話)
            try:
                # 假設你的 device 有 get_environment_data 方法
                env_temp, env_hum = device.get_environment_data() 
                state.ambient_temp = env_temp
                state.ambient_humidity = env_hum
            except AttributeError:
                # 如果沒有這個函數就維持假資料
                pass 

            # --- 收音與輸入階段 ---
            if HAS_AUDIO:
                if is_standby:
                    user_input = listen(recognizer, mic, "\n[🟡 待機中] 等待喚醒詞 (HI MY PI)... ")
                else:
                    user_input = listen(recognizer, mic, "\n[🟢 聆聽中] 🗣️ 請說指令 (說 '掰掰' 待機)... ")
            else:
                # 如果沒麥克風，退回鍵盤測試
                prompt = "\n[🟡 待機中] 請輸入喚醒詞: " if is_standby else "\n[🟢 聆聽中] 請輸入指令: "
                user_input = input(prompt)

            clean_input = (user_input or "").strip()
            
            # 如果什麼都沒聽到/沒輸入，就繼續迴圈
            if not clean_input:
                continue

            if clean_input.lower() in ['exit', 'quit']:
                speak("系統關閉中，再見。")
                break

            # --- 模式 A：待機模式 (尋找喚醒詞) ---
            if is_standby:
                # 為了避免語音辨識有時候把 hi my pi 辨識成 high my pie 之類的，
                # 這裡的判斷可以寫寬鬆一點，或是直接加上中文喚醒詞。
                wake_words = ["hi my pi", "嗨", "管家", "my pi", "my pie"]
                if any(w in clean_input.lower() for w in wake_words):
                    is_standby = False
                    speak("我在，請說！")
                continue

            # --- 模式 B：運作模式 (交給大腦處理) ---
            print(f"\n🧠 Agent 思考中...")
            
            # 將實體讀取到的溫度傳入大腦
            result = agent.handle(clean_input, current_temp=state.setpoint_temp, ambient_temp=state.ambient_temp)
            
            print(f"🤖 [意圖]: {result.intent.value} | [路由]: {result.route_type.value}")
            
            if result.error:
                speak(result.error)
            else:
                speak(result.reply)

            # 檢查是否發出待機指令
            should_standby = False
            for action in result.actions:
                if action.get("type") == "ENTER_STANDBY":
                    should_standby = True
                    break

            print_dashboard(state)

            if should_standby:
                is_standby = True
                print("💤 === 系統進入待機模式 ===")

        except KeyboardInterrupt:
            speak("強制中斷，系統關閉中。")
            break
        except Exception as e:
            print(f"\n❌ 發生未預期錯誤: {e}")
            time.sleep(1) # 避免錯誤導致迴圈暴走

    device.cleanup()

if __name__ == "__main__":
    main()