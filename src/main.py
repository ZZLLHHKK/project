import os
import sys
import time
from src.graph import app  # 引入編譯好的 LangGraph app
from src import setup_gemini_api, initialize_hardware, cleanup_hardware  # 從包初始化導入

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
        print("說 '結束'、'停止' 或 '再見' 來結束對話")
        print("說話後系統會自動處理...")
        
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
            "clarification_message": None
        }
        
        print("\n等待語音輸入...")
        
        # 運行 LangGraph 流程
        result = app.invoke(initial_state)
        
        print(f"處理狀態: {result.get('status', 'unknown')}")
        
        if result.get("status") in ["end", "error"]:
            print("對話結束")
        
    except KeyboardInterrupt:
        print("\n用戶中斷")
    except Exception as e:
        print(f"系統錯誤: {e}")
    finally:
        # 確保清理
        cleanup_hardware()

if __name__ == "__main__":
    main()