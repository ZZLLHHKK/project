

# 目標

* 分檔
* 每個檔案責任單一
* 每個檔案有一個核心 class
* SmartHomeAgent 當總控


這樣分層是清楚的：

* core = 大腦
* llm = 推理
* audio = 聲音
* devices = 硬體


#  main.py 應該長這樣

```python
from core.agent import SmartHomeAgent
from core.state_manager import StateManager
from core.memory_agent import MemoryAgent
from core.validator import ActionValidator
from llm.llm_engine import LLMEngine
from llm.prompt_builder import PromptBuilder
from audio.speech_processor import SpeechProcessor
from devices.device_controller import DeviceController

speech = SpeechProcessor()
memory = MemoryAgent()
state = StateManager()
validator = ActionValidator()
prompt_builder = PromptBuilder()
llm = LLMEngine(prompt_builder)
device = DeviceController()

agent = SmartHomeAgent(speech, llm, memory, state, validator, device)

agent.run_once()
```

這叫做：

> Dependency Injection

這是工程味道。

---

# 🔥 為什麼這樣設計很重要？

因為：

* 你隊友改 prompt 不會動到核心
* 你改 memory 不會動到 audio
* 未來換 LLM 只改 llm/
* 未來換 TTS 只改 audio/

這叫可維護性。

---

# 🧠 你現在該做的順序

1️⃣ 先建資料夾
2️⃣ 建空檔案
3️⃣ 寫 skeleton class
4️⃣ main.py 能跑（先假資料）
5️⃣ 再慢慢填細節

---

# 🚨 重要提醒

你現在不要追求：

* 很聰明
* 很複雜
* 很完整

你現在追求：

> 邊界清楚

這是你這次重構的核心。

---

很好 👍
我們來做一個**乾淨、工程等級的流程圖（Procedure Flow）**。

這是「實際執行一次語音互動」的完整箭頭流程。

我會分成：

1️⃣ 一般完整流程（含 LLM）
2️⃣ Hybrid Fast-path 分流版

---

# 🟢 版本一：完整標準流程（LLM Path）

```
[使用者說話]
        ↓
SpeechProcessor.speech_to_text()
        ↓
取得文字 text
        ↓
MemoryAgent.record_user_input(text)
        ↓
StateManager.get_state()
        ↓
MemoryAgent.get_context()
        ↓
LLMEngine.generate_plan(text, memory_context, device_state)
        ↓
LLM 回傳：
{
    actions: [...],
    reply: "..."
}
        ↓
ActionValidator.validate(actions)
        ↓
DeviceController.execute(valid_actions)
        ↓
StateManager.update(valid_actions)
        ↓
MemoryAgent.record_system_reply(reply)
        ↓
SpeechProcessor.text_to_speech(reply)
        ↓
[流程結束]
```

---

# 🔵 再幫你整理成模組分層版本

```
Audio Layer
    ↓
Agent Core (中樞控制)
    ↓
Memory / State
    ↓
LLM 推理
    ↓
Validator
    ↓
Device Layer
    ↓
Memory 更新
    ↓
Audio 回覆
```

---

# 🟣 版本二：Hybrid Router 分流版（推薦）

這是進階版（比較專業）。

```
[使用者說話]
        ↓
speech_to_text()
        ↓
Router.detect_intent(text)
        ↓
 ┌───────────────┬────────────────┐
 │               │                │
 │ Fast Path     │    LLM Path    │
 │ (rule-based)  │                │
 │               │                │
 ↓               ↓
產生 actions     呼叫 LLM
產生 reply       取得 actions + reply
 │               │
 └───────┬───────┘
         ↓
ActionValidator.validate()
         ↓
DeviceController.execute()
         ↓
StateManager.update()
         ↓
MemoryAgent.update()
         ↓
text_to_speech(reply)
         ↓
[結束]
```

---

# 🔥 用一句話講清楚整個 Procedure

```
語音 → 文字 → 分流 → 產生計畫 → 驗證 → 執行 → 更新狀態 → 記憶更新 → 語音回覆
```

