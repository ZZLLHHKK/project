# test_area/llm/llm_engine.py

import os
import re
from typing import Dict, Any
from google import genai

class LLMEngine:
    """
    通訊官：負責與 Google Gemini API 連線並解析 JSON。
    """
    
    def __init__(self, prompt_builder):
        self.prompt_builder = prompt_builder
        self._fence_re_1 = re.compile(r"^`{3}(?:json)?\s*", re.IGNORECASE)
        self._fence_re_2 = re.compile(r"\s*`{3}$", re.IGNORECASE)

    def get_adapter_responder(self, state_manager):
        """
        適配器模式 (Adapter Pattern)：
        將複雜的 generate_plan 封裝成 Agent 想要的簡單格式 (str, str) -> str。
        """
        def responder(user_input: str, memory_context: str) -> str:
            # 1. 從 state_manager 抓取實時環境數據
            state = state_manager.get_state()
            
            # 2. 呼叫大腦引擎進行推理
            result = self.generate_plan(
                user_text=user_input,
                device_status=str(state.get("led_states")), 
                current_temp=state.get("setpoint_temp"),
                memory_context="", 
                history_context=memory_context,
                ambient_temp=state.get("ambient_temp"),
                ambient_humidity=state.get("ambient_humidity")
            )
            
            # 3. 副作用處理：將 LLM 產生的動作回存至狀態機
            state_manager.set_state(raw_actions=result["actions"])
            
            # 4. 回傳總控官需要的純文字內容
            return result["reply"]
        
        return responder

    def _get_gemini_client(self):
        # ... (其餘程式碼保持不變)
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("系統找不到 GEMINI_API_KEY 環境變數！")
        return genai.Client(api_key=api_key)

    def _strip_code_fences(self, s: str) -> str:
        s = (s or "").strip()
        s = self._fence_re_1.sub("", s)
        s = self._fence_re_2.sub("", s)
        return s.strip()

    def generate_plan(self, user_text, device_status, current_temp, memory_context, history_context, ambient_temp=None, ambient_humidity=None) -> Dict[str, Any]:
        # ... (其餘程式碼與之前相同)
        prompt = self.prompt_builder.build_prompt(
            user_text=user_text,
            device_status=device_status,
            current_temp=current_temp,
            memory_context=memory_context,
            history_context=history_context,
            ambient_temp=ambient_temp,
            ambient_humidity=ambient_humidity
        )
        # (API 呼叫與 JSON 解析邏輯...)
        # (此處省略以節省篇幅)
        return {"actions": [], "reply": "...", "intent": "..."}