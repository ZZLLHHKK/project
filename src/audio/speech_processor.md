# SpeechProcessor 重構說明

**日期**：2026/03/14  
**狀態**：已搬至 `src/audio/speech_processor.py` 並測試通過  
**目標**：完全符合同學在 `todo.md` 要求的「Audio Layer 單一責任 + Dependency Injection」

---

## 重構前後最終對比

| 項目                | 舊版本（原本放在 src/ 根目錄）                | 新版本（最終版，放在 src/audio/）                        |
| ------------------- | --------------------------------------------- | -------------------------------------------------------- |
| **核心責任**        | 錄音 + 轉文字 + **寫 input.txt** + run_once() | **只負責耳朵 + 嘴巴**（speech_to_text + text_to_speech） |
| **檔案寫入**        | `speech_to_input_file()` 直接寫 `input.txt`   | **完全移除寫檔**（交給 MemoryAgent）                     |
| **import 方式**     | sys.path 硬插 + 混亂相對路徑                  | 乾淨的絕對引入 `from src.utils...`                       |
| **God Object 程度** | 300+ 行，混雜測試、寫檔、run_once             | **< 90 行**，純音訊 I/O                                  |
| **公開 API**        | 4 個方法（含 run_once）                       | **只暴露 2 個方法**（speech_to_text / text_to_speech）   |
| **測試方式**        | 要手動註解切換鍵盤/語音                       | `keyboard_input()` 專門給開發，正式用 `speech_to_text()` |
| **執行指令**        | `python speech_processor.py`（會出錯）        | `python -m src.audio.speech_processor`（正確方式）       |

---

## 這次重構到底改了什麼？（重點條列）

### 1. 最重要改變（解決耦合）

- **完全刪除** `speech_to_input_file()` 和 `write_text_file(INPUT_FILE, text)`
- **理由**：音訊層不該碰檔案，這是 MemoryAgent 的責任

### 2. 新增「嘴巴」功能

```python
def text_to_speech(self, text: str) -> None:
    speak(text)   # 整合原有 tts.py
```
