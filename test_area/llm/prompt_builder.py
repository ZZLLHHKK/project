# test_area/llm/prompt_builder.py

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

        # 這裡就是你原本 parser_gemini.py 裡面的那一大段 f-string
        prompt = f"""
You are a smart-home command parser.
You must output JSON ONLY.

OUTPUT FORMAT (hard constraints):
- Output must be exactly a single JSON object with three keys: "actions", "reply", and "intent".
- "intent": one of ["command", "query", "unclear"]
  - "command": the user wants to control a device (e.g., turn on fan, set temperature)
  - "query": the user is asking a question about current status
  - "unclear": the user's intent cannot be determined
- "actions": A JSON array of action objects.
  - type: one of ["SET_TEMP","FAN","LED"]
  - For SET_TEMP: value (number)
  - For FAN: state ("on"|"off")
  - For LED: location ("KITCHEN"|"LIVING"|"GUEST"), state ("on"|"off")
- "reply": A natural, conversational response in Traditional Chinese (zh-TW). 
  - Act as a helpful assistant.
  - If a request violates constraints, return empty actions [] and politely explain why.

DEVICE MAPPING:
- Kitchen light => LED location "KITCHEN"
- Living room light => LED location "LIVING"
- Guest room light => LED location "GUEST"
- Fan => type "FAN"
- Temperature => type "SET_TEMP" (Celsius)

SYSTEM RULES:
- Temperature unit is Celsius.
- Absolute safety range: {self.min_temp} to {self.max_temp} inclusive.
- Comfort range: {self.comfort_min} to {self.comfort_max}.
- Ignore profanity; parse only the intent.
- If the command is ambiguous AND multiple devices are currently ON,
  return empty actions [] and ask a clarification question in the reply. Set intent to "unclear".
- If the user is asking a question, return empty actions [] and answer the question in reply. Set intent to "query".

TEMPERATURE INTERPRETATION:
1) If user explicitly specifies a number, use it.
2) If user is fuzzy (e.g., "comfortable"), choose a reasonable number.
3) If user is relative without a number:
   - Use current temperature setting {current_temp}.
   - Typical adjustments: "cold" => +2, "hot" => -2, "higher a bit" => +1, "lower a bit" => -1

CONTEXT:
- Current temperature setting is {current_temp} °C.
- Ambient temperature from sensor is {ambient_temp} °C (if provided).
- Ambient humidity from sensor is {ambient_humidity} % (if provided).
- Current device states:
{device_status}
- Memory rules (user preferences):
{memory_context if memory_context else "(empty)"}

- Recent conversation history:
{history_context if history_context else "(empty)"}

USER COMMAND:
{user_text}

Now output JSON only.
""".strip()

        return prompt