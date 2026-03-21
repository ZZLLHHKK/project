import sys
import os
from pathlib import Path

# 關閉 DHT11 的硬體讀取，避免在無樹莓派環境下報錯或卡住
os.environ["DHT11_ENABLED"] = "0" 

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 引入核心模組
from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.state_manager import StateManager
from src.core.router import Router
from src.core.parser import DEFAULT_PARSER
from src.llm.llm_engine import LLMEngine
from src.llm.prompt_builder import PromptBuilder
from src.devices.device_controller import DeviceController

def print_dashboard(state: StateManager):
    """印出當前虛擬硬體的狀態面板"""
    print("\n" + "="*40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.setpoint_temp}°C")
    print(f"💨 風扇狀態: {state.fan_state}")
    print(f"💡 燈光狀態: 客廳({state.led_states.get('LIVING', 'off')}) | 廚房({state.led_states.get('KITCHEN', 'off')}) | 客房({state.led_states.get('GUEST', 'off')})")
    print("="*40 + "\n")

def main():
    print("🔧 正在初始化無硬體模擬系統...")

    # 1. 初始化狀態與記憶
    state = StateManager()
    # 為了模擬，我們手動塞入一些假環境數據
    state.ambient_temp = 26
    state.ambient_humidity = 60
    
    memory = MemoryAgent()
    router = Router()

    # 2. 初始化 LLM
    prompt_builder = PromptBuilder()
    llm = LLMEngine(prompt_builder=prompt_builder)
    

    # 3. 初始化虛擬硬體控制器 (會自動使用 MockGPIO)
    device = DeviceController()
    device.setup()  

    # 根據讀到的 state，將硬體同步恢復到上次的狀態
    device.set_temp(state.setpoint_temp)
    device.set_fan(state.fan_state)
    for loc, st in state.led_states.items():
        device.set_led(loc, st)

    # 4. 定義動作執行器 (更新狀態機與虛擬硬體)
    def action_executor(actions: list) -> None:
        if not actions:
            return
        for a in actions:
            action_type = a.get("type")
            if action_type == "LED":
                loc = a.get("location", "LIVING")
                st = a.get("state", "off")
                device.set_led(loc, st)
                
                # [修正]: 使用 set_state 才能觸發 state_manager 的 JSON 存檔機制
                current_leds = state.led_states.copy()
                current_leds[loc] = st
                state.set_state(led_states=current_leds)
                
                print(f"  [硬體執行] 💡 {loc} 燈已切換為 {st}")
            elif action_type == "FAN":
                st = a.get("state", "off")
                device.set_fan(st)
                state.set_state(fan_state=st)
                print(f"  [硬體執行] 💨 風扇已切換為 {st}")
            elif action_type == "SET_TEMP":
                val = a.get("value", 25)
                device.set_temp(val)
                state.set_state(setpoint_temp=val)
                print(f"  [硬體執行] 🌡️ 溫度已設定為 {val}°C")
        
    llm_responder = llm.get_adapter_responder(state, action_executor=action_executor)

    # 5. 組合 Agent 大腦
    agent = SmartHomeAgent(
        router=router,
        parser=DEFAULT_PARSER,
        memory=memory,
        state=state,
        action_executor=action_executor,
        llm_responder=llm_responder,
    )

    print("✅ 系統初始化完成！進入文字測試模式。")
    print_dashboard(state)

    # 新增：待機狀態變數，預設啟動時為待機狀態
    is_standby = True
    print("💡 提示：輸入 'HI MY PI' 來喚醒系統，輸入 '掰掰' 讓系統進入待機。")

    # 6. 互動主迴圈
    while True:
        try:
            # 根據不同狀態，顯示不同的輸入提示 (模擬未來麥克風收音狀態)
            if is_standby:
                user_input = input("\n[🟡 待機中...] 正在等待喚醒詞 (輸入 'exit' 退出): ")
            else:
                user_input = input("\n[🟢 聆聽中...] 🗣️ 請輸入您的指令 (輸入 '掰掰' 待機，或 'exit' 退出): ")

            if user_input.lower() in ['exit', 'quit']:
                print("👋 系統關閉中...")
                break
            
            clean_input = user_input.strip()
            if not clean_input:
                continue

            # ==========================================
            # 模式 A：待機模式 (只對喚醒詞有反應)
            # ==========================================
            if is_standby:
                if "HI MY PI" in clean_input.upper():
                    is_standby = False
                    print("\n✨ AI：我在！請告訴我需要幫忙什麼？")
                # 如果講別的，就不理會 (直接回到迴圈開頭等待下一次輸入)
                continue

            # ==========================================
            # 模式 B：運作模式 (交給大腦處理)
            # ==========================================
            print(f"\n🧠 Agent 思考中...")
            
            # 呼叫 Agent 處理一輪
            result = agent.handle(clean_input)
            
            # 印出結果
            print(f"🤖 [意圖]: {result.intent.value} | [路由]: {result.route_type.value}")
            print(f"🔊 [語音回覆]: {result.reply}")
            
            if result.error:
                print(f"⚠️ [錯誤]: {result.error}")

            # 檢查 Agent 是否發出待機指令 (對應 agent.py 中的 ENTER_STANDBY 動作)
            should_standby = False
            for action in result.actions:
                if action.get("type") == "ENTER_STANDBY":
                    should_standby = True
                    break

            # 顯示更新後的狀態面板
            print_dashboard(state)

            # 執行待機切換
            if should_standby:
                is_standby = True
                print("💤 === 系統已切換至待機模式 ===")

        except KeyboardInterrupt:
            print("\n👋 強制中斷，系統關閉中...")
            break
        except Exception as e:
            print(f"\n❌ 發生未預期錯誤: {e}")

    device.cleanup()

if __name__ == "__main__":
    main()