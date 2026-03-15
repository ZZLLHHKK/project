import os
import json
import re
from typing import Dict, Any
from google import genai
import src.utils.config as config 

class LLMEngine:
    """
    通訊官：負責與 Google Gemini API 進行實體連線，收發訊息，並嚴格解析 JSON。
    """
    
    def __init__(self, prompt_builder):
        # 依賴注入：接收外部傳入的翻譯官
        self.prompt_builder = prompt_builder
        
        # 正規表達式：用來清理 Markdown 的程式碼區塊標記
        # 使用 `{3}` 來代替連續三個反引號，避免介面渲染錯誤
        self._fence_re_1 = re.compile(r"^`{3}(?:json)?\s*", re.IGNORECASE)
        self._fence_re_2 = re.compile(r"\s*`{3}$", re.IGNORECASE)

    def _get_gemini_client(self):
        """延遲初始化，確保只在真正要連線時才檢查 API Key"""
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("系統找不到 GEMINI_API_KEY 環境變數！")
        return genai.Client(api_key=api_key)

    def _strip_code_fences(self, s: str) -> str:
        """安全移除字串頭尾的程式碼區塊標記"""
        s = (s or "").strip()
        s = self._fence_re_1.sub("", s)
        s = self._fence_re_2.sub("", s)
        return s.strip()

    def generate_plan(
        self, 
        user_text: str, 
        device_status: str, 
        current_temp: int, 
        memory_context: str, 
        history_context: str,
        ambient_temp: int = None,
        ambient_humidity: int = None
    ) -> Dict[str, Any]:
        """
        核心流程：組裝 Prompt -> 呼叫 API -> 清理字串 -> 安全解析 JSON
        """
        # 1. 請翻譯官產生最終的 Prompt
        prompt = self.prompt_builder.build_prompt(
            user_text=user_text,
            device_status=device_status,
            current_temp=current_temp,
            memory_context=memory_context,
            history_context=history_context,
            ambient_temp=ambient_temp,
            ambient_humidity=ambient_humidity
        )

        # 2. 聯絡 Gemini API
        try:
            client = self._get_gemini_client()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            reply_text = response.text or ""
            
        except Exception as e:
            # 網路斷線或 Key 錯誤的防護
            print(f"[LLMEngine 錯誤] API 連線失敗: {e}")
            return {
                "actions": [], 
                "reply": "抱歉，大腦連線似乎出了點問題，請檢查網路或 API 設定。", 
                "intent": "error"
            }

        # 3. 清理字串
        raw_json = self._strip_code_fences(reply_text)
        
        # 4. 嚴格的安全解析 (Strict JSON Parsing)
        try:
            data = json.loads(raw_json)
            
            # 防呆 1：確保最外層是字典
            if not isinstance(data, dict):
                raise ValueError("LLM 回傳的 JSON 最外層不是物件 (Dict)")
                
            # 防呆 2：確保 actions 一定是陣列 (List)，就算 LLM 忘記給，也要預設為空陣列
            actions = data.get("actions", [])
            if not isinstance(actions, list):
                print(f"[LLMEngine 警告] actions 格式錯誤，強制轉為空陣列。收到: {actions}")
                actions = []
                
            return {
                "actions": actions,
                "reply": str(data.get("reply", "好的，已為您處理。")), # 確保是字串
                "intent": str(data.get("intent", "command"))          # 確保是字串
            }
            
        except Exception as e:
            # 防呆 3：當 JSON 括號漏掉、逗號寫錯時的終極防護
            print(f"\n[LLMEngine 嚴重錯誤] JSON 解析失敗！")
            print(f"錯誤原因: {e}")
            print(f"Gemini 原始亂碼: \n{raw_json}\n")
            
            return {
                "actions": [], 
                "reply": "抱歉，我剛剛思考的時候有點混亂，可以請您換個說法再說一次嗎？", 
                "intent": "unclear"
            }