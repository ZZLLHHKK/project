import time

from src.graph import app  # 引入編譯好的 LangGraph app
from src import setup_gemini_api, initialize_hardware, cleanup_hardware  # 從包初始化導入
from src.utils.wait_wakeword import wait_for_wake_word
from src.utils.tts import speak

def main():
    """主函式"""
    print("=== 智能家居語音控制系統啟動 ===")
    
    try:
        # 檢查 API
        setup_gemini_api()
        '''
        if gemini_available:
            print("✓ Gemini API 可用")
        else:
            print("⚠ 只使用快速解析器")
        '''
        
        # 初始化硬件
        if not initialize_hardware():
            print("硬體初始化失敗")
            return
        
        # 初始狀態
        initial_state= {

            "input_text": "",
            "raw_actions": [],
            "validated_actions": [],
            "status": "start",
            "memory_rules": {},
            "history": [], # 這樣對話紀錄才會累加
            "last_input_time": time.time(),
            "needs_clarification": False,
            "clarification_message": None,
            "llm_reply": None,
            "parse_source": None,
            "failure_count": 0,    # 這裡歸零，後面才會累加
            "error_message": None,
            "ambient_temp": None,
            "setpoint_temp": 25,   # 預設溫度
            "auto_cool_enabled": False,
            "fan_state": "off",
            "led_states": {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"},
            "ambient_humidity": None
        }

        while True:

            wakeword_detected = wait_for_wake_word()
            
            if not wakeword_detected:
                print("喚醒詞引擎中斷")
                break
            
            # 語音回饋
            speak("我在")

            # 運行 LangGraph 流程
            result = app.invoke(initial_state)

            # 保留設備狀態到下一輪
            initial_state["setpoint_temp"] = result.get("setpoint_temp", 25)
            initial_state["auto_cool_enabled"] = result.get("auto_cool_enabled", False)
            initial_state["ambient_temp"] = result.get("ambient_temp")
            initial_state["fan_state"] = result.get("fan_state", "off")
            initial_state["led_states"] = result.get("led_states", {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"})
            initial_state["ambient_humidity"] = result.get("ambient_humidity")

            print(f"處理狀態: {result.get('status', 'unknown')}")

            if result.get("llm_reply"):
                print("Gemini 回覆：")
                print(result.get("llm_reply"))

            if result.get("error_message"):
                print(f"錯誤訊息: {result.get('error_message')}")
            
    except KeyboardInterrupt:
        print("\n用戶中斷")
    except Exception as e:
        print(f"系統錯誤: {e}")
    finally:
        # 確保清理
        cleanup_hardware()
        print("系統安全關閉")

if __name__ == "__main__":
    main()