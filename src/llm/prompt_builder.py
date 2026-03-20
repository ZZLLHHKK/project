# src/llm/prompt_builder.py
# StateManager, MemoryAgent, SmartHomeAgent

class PromptBuilder:
    """
    翻譯官：負責將系統狀態、歷史記憶與使用者輸入，組合成 LLM 看得懂的 Prompt。
    這個類別不負責打 API，只負責產生字串。
    """
    
    def __init__(self):
        # 這裡可以放一些固定的系統設定，例如最大最小溫度
        self.min_temp = 18.0
        self.max_temp = 30.0
        self.comfort_min = 22.0
        self.comfort_max = 26.0

    def build_prompt(
        self, 
        user_text: str, 
        device_status: str, 
        current_temp: int, 
        memory_context: str, 
        history_context: str,
        ambient_temp: int = None,
        ambient_humidity: int = None
    ) -> str:
        """組裝完整的 Prompt 字串"""
        
        # 為了避免 Context 太長，限制記憶和歷史的長度 (移植自舊程式碼)
        if len(memory_context) > 2000:
            memory_context = memory_context[-2000:]
        if len(history_context) > 2000:
            history_context = history_context[-2000:]
        
        sensor_temp_info = f"{ambient_temp} °C" if ambient_temp is not None else f"感測器未連線 (因此請直接回答目前的冷氣設定溫度：{current_temp} °C)"
        sensor_hum_info = f"{ambient_humidity} %" if ambient_humidity is not None else "感測器未連線，無法得知濕度"

        # 這裡就是你原本 parser_gemini.py 裡面的那一大段 f-string
        prompt = f"""
You are a smart-home command parser.
You must output JSON ONLY.

OUTPUT FORMAT (hard constraints):
- EXACTLY one JSON object with keys: "actions", "reply", "intent".
- "intent": "command", "query", or "unclear".
- "actions": Array of action objects (SET_TEMP, FAN, LED).
- "reply": A natural, conversational response in Traditional Chinese (zh-TW). THIS MUST NOT BE EMPTY.

DEVICE MAPPING:
- Kitchen light (廚房燈) => LED "KITCHEN"
- Living room light (客廳燈) => LED "LIVING"
- Guest room light (客房燈) => LED "GUEST"
- Fan (風扇) => "FAN"
- Temperature (溫度) => "SET_TEMP"

SYSTEM RULES:
1. If the user asks a question (e.g., "現在幾度", "燈有開嗎"), intent is "query", actions is []. You MUST write the actual answer in the "reply" field based on CONTEXT.
2. NEVER output placeholder replies like "好的，已為您處理" for questions.
3. TYPO CORRECTION: You MUST intelligently guess and auto-correct homophones or typos based on pronunciation (e.g., "除防登" -> "廚房燈", "克聽" -> "客廳", "封扇" -> "風扇").

=== FEW-SHOT EXAMPLES (Strictly mimic this JSON structure and logic) ===
User: "現在溫度幾度？"
JSON: {{"actions": [], "reply": "目前的溫度設定是 {current_temp} 度。", "intent": "query"}}

User: "幫我開除防登"
JSON: {{"actions": [{{"type": "LED", "location": "KITCHEN", "state": "on"}}], "reply": "好的，已為您開啟廚房燈。", "intent": "command"}}

User: "克聽的燈幫我關掉"
JSON: {{"actions": [{{"type": "LED", "location": "LIVING", "state": "off"}}], "reply": "沒問題，已經關閉客廳的燈。", "intent": "command"}}

User: "現在濕度多少？"
JSON: {{"actions": [], "reply": "目前的濕度狀態是：{sensor_hum_info}。", "intent": "query"}}
========================================================================

CONTEXT:
- Current temperature setting: {current_temp} °C
- Ambient temperature: {sensor_temp_info}
- Ambient humidity: {sensor_hum_info}
- Device states: {device_status}
- Memory: {memory_context if memory_context else '(empty)'}
- History: {history_context if history_context else '(empty)'}

USER COMMAND:
{user_text}

Now output JSON only.
""".strip()

        return prompt