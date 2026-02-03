import os
import sys
from dotenv import load_dotenv
from src.nodes.langgraph_split_files.hardware_led import setup as led_setup, cleanup as led_cleanup
from src.nodes.langgraph_split_files.hardware_fan import setup as fan_setup, cleanup as fan_cleanup
from src.nodes.langgraph_split_files.hardware_7seg import SevenSegDisplay

# 載入環境變數
load_dotenv()

# 全局變數
disp = None

# 檢查並設定 Gemini API Key
def setup_gemini_api():
    """檢查並設定 Gemini API Key"""
    # 檢查可能的 API key 變數名稱
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("警告: 沒有找到 GEMINI_API_KEY 或 GOOGLE_API_KEY 環境變數")
        print("請在 .env 文件中設置：")
        print("GEMINI_API_KEY=你的API金鑰")
        print("或者 GOOGLE_API_KEY=你的API金鑰")
        print("或者直接在程式中設定：")
        api_key = input("請輸入你的 Gemini API Key (或按 Enter 跳過): ").strip()
        if api_key:
            os.environ['GEMINI_API_KEY'] = api_key
            print("API Key 已設定")
        else:
            print("將只使用快速解析器，跳過 Gemini LLM")
            return False
    else:
        # 確保 GEMINI_API_KEY 被設置（以防使用的是 GOOGLE_API_KEY）
        os.environ['GEMINI_API_KEY'] = api_key
        print("✓ API Key 已從環境變數載入")
    return True

def initialize_hardware():
    """初始化所有硬件"""
    global disp
    try:
        # 7段顯示器
        disp = SevenSegDisplay()
        disp.setup()
        disp.start()

        # 風扇
        fan_setup()

        # LED
        led_setup()

        print("✓ 硬件初始化完成")
        return True
    except Exception as e:
        print(f"✗ 硬件初始化失敗: {e}")
        return False

def cleanup_hardware():
    """清理硬件"""
    global disp
    try:
        if disp:
            disp.cleanup()
        led_cleanup()
        fan_cleanup()
        print("✓ 硬件清理完成")
    except Exception as e:
        print(f"✗ 硬件清理錯誤: {e}")