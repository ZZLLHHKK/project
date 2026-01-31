# src/utils/file_io.py
def write_text_file(path: str, content: str):
    """寫入文字檔（覆蓋模式）"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content + "\n")
        print(f"成功寫入檔案：{path}")
    except Exception as e:
        print(f"寫檔失敗：{e}")
    
def read_text_file(path: str) -> str:
    """
    讀取文字檔並返回內容
    如果失敗，返回空字串或拋出例外（依需求）
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()  # strip() 移除前後空白與換行
        return content
    except FileNotFoundError:
        print(f"檔案不存在：{path}")
        return ""
    except Exception as e:
        print(f"讀檔失敗：{e}")
        return ""
    
import json
from src.utils.config import INPUT_TXT_PATH, OUTPUT_TXT_PATH
from src.nodes.short_command import match_short_command

def write_output(path: str, command: dict):
    """把 short command 的 dict 寫成 JSON 檔"""
    try:
        json_str = json.dumps(command, ensure_ascii=False, indent=2)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(json_str + "\n")
        print(f"成功寫入 output.txt : {json_str}")
    except Exception as e:
        print(f"寫 output 失敗：{e}")