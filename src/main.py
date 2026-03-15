# ================================================
# main.py - 專題最終入口點（2026/03/15 教授版）
# ================================================
# 這是整個系統的「大門」：使用 Dependency Injection
# 完全符合你 todolist.md 的理想架構

import sys
from pathlib import Path
from typing import List, Dict, Any

# ====================== 路徑設定 ======================
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 指向 project/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ====================== 匯入所有模組 ======================
# 目前在 src/ 結構（搬移後請把 src. 全部刪掉）
from src.audio.speech_processor import SpeechProcessor
from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.state_manager import StateManager
from src.core.parser import DEFAULT_PARSER          # 內建 FastPath + Gemini facade
from src.core.router import Router
from src.llm.llm_engine import LLMEngine
from src.llm.prompt_builder import PromptBuilder
from src.devices.device_controller import DeviceController

# ====================== 建立物件（Dependency Injection） ======================
print("🔧 正在初始化系統...")

speech = SpeechProcessor()                    # 耳朵 + 嘴巴
memory = MemoryAgent()                        # 短期 + 長期記憶
state = StateManager()                        # 全域狀態機
prompt_builder = PromptBuilder()
llm = LLMEngine(prompt_builder)               # LLM 推理引擎
device = DeviceController()                   # 硬體控制器（GPIO）

# 自訂 action_executor（橋接 DeviceController）
def action_executor(actions: List[Dict[str, Any]]) -> None:
    """把 LLM / fastpath 產生的 actions 真正執行到硬體"""
    for a in actions:
        t = a.get("type", "").upper()
        if t == "SET_TEMP":
            val = a.get("value", 25)
            device.set_temp(val)
            state.setpoint_temp = val
            print(f"🌡️ 溫度已設定為 {val}°C")
        elif t == "FAN":
            device.set_fan(a.get("state", "off"))
            state.fan_state = a.get("state", "off")
            print(f"🌀 風扇已 {a.get('state', 'off')}")
        elif t == "LED":
            loc = a.get("location", "KITCHEN")
            device.set_led(loc, a.get("state", "off"))
            state.led_states[loc] = a.get("state", "off")
            print(f"💡 {loc} 燈已 {a.get('state', 'off')}")


# 建立 LLM responder（使用 LLMEngine 的 adapter）
llm_responder = llm.get_adapter_responder(state)

# 建立總控 Agent（注入所有東西）
agent = SmartHomeAgent(
    router=Router(),
    parser=DEFAULT_PARSER,          # FastPath + Gemini 自動切換
    memory=memory,
    state=state,
    action_executor=action_executor,
    llm_responder=llm_responder,
)

print("✅ 系統初始化完成！")

# ====================== 硬體啟動 ======================
device.setup()          # GPIO、七段顯示器、DHT11 全部啟動

# ====================== 主循環 ======================
try:
    print("\n🎤 系統已啟動！請輸入文字測試（輸入 'exit' 結束）")
    print("   （之後想改成真語音，只要把 keyboard_input 改成 speech_to_text 即可）\n")

    while True:
        # === 開發模式：鍵盤輸入（超方便測試）===
        text = speech.keyboard_input()          # ← 改成 speech.speech_to_text() 就是真語音

        if text.lower() in ["exit", "quit", "結束"]:
            break

        # 交給 SmartHomeAgent 處理（這一行就是整個專題的核心！）
        result = agent.handle(text)

        # 顯示結果 + 語音回覆
        print(f"\n🤖 [AI 回覆]: {result.reply}")
        speech.text_to_speech(result.reply)     # Piper TTS 說出來

except KeyboardInterrupt:
    print("\n\n🛑 收到 Ctrl+C，正在關閉系統...")
except Exception as e:
    print(f"❌ 發生錯誤: {e}")
finally:
    # 一定要 cleanup！避免 GPIO 卡住
    device.cleanup()
    print("👋 系統已安全關閉。感謝使用！")