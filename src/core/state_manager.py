from __future__ import annotations
from typing import Any
from pathlib import Path
import json
import os


class StateManager:
    def __init__(self) -> None:
        """初始化變數內容(變數未來可擴充)"""
        self.conversation_active: bool = False
        self.awaiting_confirmation: bool = False
        self.last_intent: str | None = None
        self.device_states: dict[str, Any] = {}
        self.input_text: str = ""
        self.raw_actions: list = []
        self.validated_actions: list = []
        self.status: str = "start"
        self.memory_rules: dict = {}
        self.history: list = []
        self.last_input_time: float = 0.0
        self.needs_clarification: bool = False
        self.clarification_message: str | None = None
        self.llm_reply: str | None = None
        self.parse_source: str | None = None
        self.error_message: str | None = None
        self.ambient_temp: int | None = None
        self.setpoint_temp: int = 25
        self.auto_cool_enabled: bool = False
        self.fan_state: str = "off"
        self.led_states: dict = {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"}
        self.ambient_humidity: int | None = None

        # 設定儲存設備狀態的檔案路徑
        project_root = Path(__file__).resolve().parent.parent.parent
        self._state_dir = project_root / "data" / "memory" 
        self._state_file = self._state_dir / "device_state.json"
        self.load_state()

    def load_state(self) -> None:
        """從檔案讀取上次關機前的設備與溫度狀態"""
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.setpoint_temp = data.get("setpoint_temp", 25)
                    self.fan_state = data.get("fan_state", "off")
                    self.led_states = data.get("led_states", {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"})
            except Exception as e:
                print(f"讀取狀態檔失敗: {e}")

    def save_state(self) -> None:
        """將當前最新的狀態寫入檔案保存"""
        os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "setpoint_temp": self.setpoint_temp,
                    "fan_state": self.fan_state,
                    "led_states": self.led_states
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"寫入狀態檔失敗: {e}")

    def get_state(self) -> dict[str, Any]:
        # 回傳快照，避免外部直接修改內部狀態
        return {
            "conversation_active": self.conversation_active,
            "awaiting_confirmation": self.awaiting_confirmation,
            # ...existing code...
            "last_intent": self.last_intent,
            "device_states": dict(self.device_states),
            "input_text": self.input_text,
            "raw_actions": list(self.raw_actions),
            "validated_actions": list(self.validated_actions),
            "status": self.status,
            "memory_rules": dict(self.memory_rules),
            "history": list(self.history),
            "last_input_time": self.last_input_time,
            "needs_clarification": self.needs_clarification,
            "clarification_message": self.clarification_message,
            "llm_reply": self.llm_reply,
            "parse_source": self.parse_source,
            "error_message": self.error_message,
            "ambient_temp": self.ambient_temp,
            "setpoint_temp": self.setpoint_temp,
            "auto_cool_enabled": self.auto_cool_enabled,
            "fan_state": self.fan_state,
            "led_states": dict(self.led_states),
            "ambient_humidity": self.ambient_humidity,
        }
    
    def set_state(self, **kwargs: Any) -> None:
        needs_save = False
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # 如果改變的是這三個關鍵狀態，就標記需要存檔
                if key in ["setpoint_temp", "fan_state", "led_states"]:
                    needs_save = True
            else:
                print(f"警告：StateManager 沒有屬性 '{key}'，無法設定。")

        if needs_save:
            self.save_state()
    
    def reset_conversation(self) -> None:
        self.conversation_active = False
        self.awaiting_confirmation = False
        self.last_intent = None

    def update_device_state(self, device_name: str, state: Any) -> None:
        self.device_states[device_name] = state

    def get_device_state(self, device_name: str) -> Any:
        return self.device_states.get(device_name)
    
"""
class 說明
StateManager 負責管理對話狀態，只做：
存 state
讀 state
更新 state
"""

"""
class變數說明
1.conversation_active: 是否正在對話中 (T/F)

2.awaiting_confirmation: 是否正在等待使用者確認 (T/F)
eg:
AI: 確定要把溫度設為 28°C 嗎？
User: 好
這時候系統要知道：
"好"是確認

3.last_user_input: 最後一次使用者輸入的文字 (str)
eg:
"把客廳燈打開"

4.last_intent: 最後一次解析出的意圖 (str)
eg:
DEVICE_CONTROL
CHAT
QUERY

5.device_states: 各設備的狀態 (dict)
例如：
{
  "living_room_light": "on",
  "aircon_temp": 24
}
這樣 AI 才知道目前設備狀態。
"""