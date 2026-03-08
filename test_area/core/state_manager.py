from __future__ import annotations

from typing import Any


class StateManager:
    def __init__(self) -> None:
        """初始化變數內容(變數未來可擴充)"""
        self.conversation_active: bool = False
        self.awaiting_confirmation: bool = False
        self.last_user_input: str | None = None
        self.last_intent: str | None = None
        self.device_states: dict[str, Any] = {}

    def get_state(self) -> dict[str, Any]:
        # 回傳快照，避免外部直接修改內部狀態
        return {
            "conversation_active": self.conversation_active,
            "awaiting_confirmation": self.awaiting_confirmation,
            "last_user_input": self.last_user_input,
            "last_intent": self.last_intent,
            "device_states": dict(self.device_states),
        }
    
    def set_state(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                print(f"警告：StateManager 沒有屬性 '{key}'，無法設定。")
    
    def reset_conversation(self) -> None:
        self.conversation_active = False
        self.awaiting_confirmation = False
        self.last_user_input = None
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