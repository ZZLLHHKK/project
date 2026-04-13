from __future__ import annotations

from typing import Any, Optional

from .memory_agent import MemoryAgent
from .parser.fastpath_parser import FastPathParser
from .parser.gemini_parser import GeminiParser
from .state_manager import StateManager

FRIENDLY_ERROR = "抱歉，我現在無法處理，請稍後再試。"


class ActionExecutionError(RuntimeError):
    """Compatibility placeholder for older call sites."""


class SmartHomeAgent:
    """Main orchestrator: fastpath first, Gemini fallback, then execute and persist."""

    def __init__(
        self,
        memory: Optional[MemoryAgent] = None,
        state: Optional[StateManager] = None,
        fastpath_parser: Optional[FastPathParser] = None,
        gemini_parser: Optional[GeminiParser] = None,
        device_controller: Any = None,
    ) -> None:
        self.memory = memory or MemoryAgent()
        self.state = state or StateManager()
        self.fastpath = fastpath_parser or FastPathParser()
        self.gemini = gemini_parser or GeminiParser()
        self.device_controller = device_controller

    def _friendly_fastpath_reply(self, actions: list[dict[str, Any]]) -> str:
        labels = {"KITCHEN": "廚房", "LIVING": "客廳", "GUEST": "客房"}
        parts: list[str] = []
        for action in actions:
            action_type = str(action.get("type", "")).upper()
            if action_type == "SET_TEMP":
                parts.append(f"溫度已設定為 {action.get('value')} 度")
            elif action_type == "FAN":
                state = "開啟" if str(action.get("state", "off")).lower() == "on" else "關閉"
                parts.append(f"風扇已{state}")
            elif action_type == "LED":
                location = labels.get(str(action.get("location", "")).upper(), "燈")
                state = "開啟" if str(action.get("state", "off")).lower() == "on" else "關閉"
                parts.append(f"{location}燈已{state}")
        return f"好的，{'，'.join(parts)}。" if parts else "好的，已為您處理。"

    def _execute_actions(self, actions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Optional[str]]:
        if not actions:
            return [], None
        if self.device_controller is None:
            executed = [dict(action, success=True) for action in actions]
            return executed, None

        results = self.device_controller.execute_actions(actions)
        failures = [item for item in results if not item.get("success", False)]
        if failures:
            return results, "device_execution_failed"
        return results, None

    def _build_result(
        self,
        reply: str,
        actions_executed: list[dict[str, Any]],
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "reply": reply,
            "actions_executed": actions_executed,
            "state": self.state.get_state(),
            "error": error,
        }

    def handle(self, user_input: str) -> dict[str, Any]:
        clean_input = (user_input or "").strip()
        if not clean_input:
            return self._build_result("請告訴我你想控制的設備或需求。", [], None)

        if any(keyword in clean_input for keyword in ("掰掰", "再見", "待機", "拜拜")):
            reply = "好的，我先休息囉，有需要請隨時叫我！"
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [{"type": "ENTER_STANDBY", "success": True}], None)

        if any(keyword in clean_input for keyword in ("關機", "關閉系統", "結束程式")):
            reply = "好的，系統關閉中，再見！"
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [{"type": "SHUTDOWN", "success": True}], None)

        if any(keyword in clean_input for keyword in ("清除記憶", "重置記憶", "清記憶")):
            self.memory.reset_conversation()
            self.state.reset_conversation()
            reply = "好的，已清除短期記憶。"
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        learned = self.fastpath.try_learn_rule(clean_input)
        if learned is not None:
            self.memory.save_rule(learned["trigger"], learned["meaning"])
            reply = f"好的，我記住了：當你說「{learned['trigger']}」時，代表「{learned['meaning']}」。"
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        rules = self.memory.load_rules()
        fast_actions = self.fastpath.parse(clean_input, rules=rules)
        if fast_actions:
            executed, exec_error = self._execute_actions(fast_actions)
            self.state.update_from_actions([item for item in executed if item.get("success")])
            reply = self._friendly_fastpath_reply(fast_actions)
            if exec_error:
                reply = f"{reply} 但有部分裝置沒有成功執行。"
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, executed, exec_error)

        gemini_result = self.gemini.parse(clean_input, self.state, self.memory)
        intent = gemini_result.get("intent")
        actions = gemini_result.get("actions", [])
        reply = str(gemini_result.get("reply") or FRIENDLY_ERROR)

        if intent == "unclear":
            self.state.needs_clarification = True
            self.state.clarification_message = reply
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        self.state.needs_clarification = False
        self.state.clarification_message = None

        if intent == "error":
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], "gemini_error")

        executed, exec_error = self._execute_actions(actions)
        self.state.update_from_actions([item for item in executed if item.get("success")])
        if exec_error:
            reply = f"{reply} 但有部分裝置沒有成功執行。"
        self.memory.add_interaction(clean_input, reply)
        return self._build_result(reply, executed, exec_error)

