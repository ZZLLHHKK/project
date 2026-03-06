import sys
from pathlib import Path

# 自動加專案根目錄到 sys.path
sys.path.insert(0, str(Path().resolve().parents[1]))  # parents[0] = project/ 根目錄
# parents[0] → /home/pi/project/src

import os
import time
from src.graph import app  # 引入編譯好的 LangGraph app
from src import setup_gemini_api, initialize_hardware, cleanup_hardware  # 從包初始化導入
from src.utils.wakeword import wait_for_wake_word
from src.utils.tts import speak

def main():
    """主函式"""
    print("智能家居語音控制系統")
    
    try:
        # 檢查 API
        gemini_available = setup_gemini_api()
        '''
        if gemini_available:
            print("✓ Gemini API 可用")
        else:
            print("⚠ 只使用快速解析器")
        '''
        
        # 初始化硬件
        if not initialize_hardware():
            print("硬件初始化失敗，退出")
            return
        
        # 運行一次 LangGraph 流程
        print("\n=== 智能家居語音控制系統啟動 ===")
        print("提示: 按 Ctrl+C 可以強制結束程式")
        
        while True:

            wakeword_detected = wait_for_wake_word(keyword="jarvis")
            
            if not wakeword_detected:
                print("喚醒詞引擎異常，結束系統")
                break
            
            # 語音回饋
            speak("嗯...哼？")
            time.sleep(0.2)

            # 初始狀態
            initial_state = {
                "input_text": "",
                "raw_actions": [],
                "validated_actions": [],
                "status": "start",
                "memory_rules": {},
                "history": [],
                "last_input_time": time.time(),
                "needs_clarification": False,
                "clarification_message": None,
                "llm_reply": None,
                "parse_source": None,
                "failure_count": 0,
                "error_message": None
            }
            
            # 運行 LangGraph 流程
            result = app.invoke(initial_state)
            
            print(f"處理狀態: {result.get('status', 'unknown')}")

            if result.get("llm_reply"):
                print("Gemini 回覆：")
                print(result.get("llm_reply"))

            if result.get("error_message"):
                print(f"錯誤訊息: {result.get('error_message')}")
            
            print("-" * 50)
            
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