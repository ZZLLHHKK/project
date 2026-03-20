from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Any, Callable, Optional

# Allow direct execution: python src/core/agent.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

try:
	from .memory_agent import MemoryAgent
	from .router import Intent, RouteType, Router, is_system_reset_command
	from .state_manager import StateManager
	from .parser import DEFAULT_PARSER, ParserFacade
except ImportError:
	from src.core.memory_agent import MemoryAgent
	from src.core.router import Intent, RouteType, Router, is_system_reset_command
	from src.core.state_manager import StateManager
	from src.core.parser import DEFAULT_PARSER, ParserFacade


@dataclass(slots=True)
class AgentResult:
	"""Unified output payload for one user turn."""

	reply: str
	actions: list[dict[str, Any]]
	route_type: RouteType
	intent: Intent
	error: Optional[str] = None


class SmartHomeAgent:
	"""Application orchestrator for one-turn processing.

	Responsibilities:
	1) Route user input (fast command vs llm route)
	2) Parse command actions (fastpath + gemini fallback)
	3) Execute actions through injected executor
	4) Maintain state + memory
	"""

	def __init__(
		self,
		router: Optional[Router] = None,
		parser: Optional[ParserFacade] = None,
		memory: Optional[MemoryAgent] = None,
		state: Optional[StateManager] = None,
		action_executor: Optional[Callable[[list[dict[str, Any]]], None]] = None,
		llm_responder: Optional[Callable[[str, str], str]] = None,
	) -> None:
		self.router = router or Router()
		self.parser = parser or DEFAULT_PARSER
		self.memory = memory or MemoryAgent()
		self.state = state or StateManager()

		# action_executor(actions) -> side effects (GPIO/API/etc.)
		self.action_executor = action_executor or self._noop_action_executor
		# llm_responder(user_input, memory_context) -> natural language reply
		self.llm_responder = llm_responder or self._default_llm_responder

	def _noop_action_executor(self, actions: list[dict[str, Any]]) -> None:
		"""Default executor for development stage (no hardware side effects)."""
		_ = actions

	def _default_llm_responder(self, user_input: str, memory_context: str) -> str:
		"""Fallback responder before integrating real llm_engine."""
		_ = memory_context
		return f"我收到你的訊息：{user_input}。目前尚未接入正式 LLM 回覆模組。"

	def _handle_system_intent(self, user_input: str) -> Optional[AgentResult]:
		if is_system_reset_command(user_input):
			self.memory.clear_memory()
			self.state.reset_conversation()
			reply = "好的，已清除短期記憶並重置對話狀態。"
			return AgentResult(
				reply=reply,
				actions=[],
				route_type=RouteType.FAST_COMMAND,
				intent=Intent.SYSTEM,
			)
		return None

	def _save_turn(self, user_input: str, reply: str) -> None:
		self.memory.save_interaction(user_input, reply)

	def handle(self, user_input: str, current_temp: Optional[int] = None, ambient_temp: Optional[int] = None) -> AgentResult:
		"""Process one user input and return a unified AgentResult."""
		clean_input = (user_input or "").strip()
		if not clean_input:
			reply = "請告訴我你想控制的設備或需求。"
			out = AgentResult(
				reply=reply,
				actions=[],
				route_type=RouteType.LLM,
				intent=Intent.UNKNOWN,
			)
			self._save_turn(clean_input, reply)
			return out

		decision = self.router.route(clean_input)
		# 如果沒有傳入新值，就沿用 state 目前保留的數值
		new_setpoint = current_temp if current_temp is not None else self.state.setpoint_temp
		new_ambient = ambient_temp if ambient_temp is not None else self.state.ambient_temp
		
		self.state.set_state(
			conversation_active=True,
			input_text=clean_input,
			last_intent=decision.intent.value,
			status="start",
			needs_clarification=False,
			ambient_temp=new_ambient,
			setpoint_temp=new_setpoint,
		)

		# System commands can be handled directly without parser/llm.
		if decision.intent == Intent.SYSTEM:
			system_result = self._handle_system_intent(clean_input)
			if system_result is not None:
				self._save_turn(clean_input, system_result.reply)
				return system_result

		# Rule-teaching commands are handled by fastpath learner directly.
		learned = self.parser.fastpath.learn_rule(clean_input)
		if learned is not None:
			reply = "好的，我已經記住這條規則。"
			self.state.set_state(
				status="executed",
				llm_reply=reply,
			)
			result = AgentResult(
				reply=reply,
				actions=[],
				route_type=RouteType.FAST_COMMAND,
				intent=Intent.SYSTEM,
			)
			self._save_turn(clean_input, result.reply)
			return result

		question_keywords = ["嗎", "呢", "狀態", "有沒有", "是不是", "確認", "幾度", "?", "？"]
		is_question = any(q in clean_input for q in question_keywords)
		if not is_question:
			fast_actions = self.parser.fastpath.parse(clean_input)
			if fast_actions:
				self.action_executor(fast_actions)
				reply = "好的，已為你處理。"

				self.state.set_state(
					raw_actions=fast_actions,
					validated_actions=fast_actions,
					status="executed",
					llm_reply=reply,
				)

				for action in fast_actions:
					action_type = str(action.get("type", ""))
					if action_type == "SET_TEMP":
						self.state.setpoint_temp = action.get("value")
					elif action_type == "FAN":
						self.state.fan_state = action.get("state")
					elif action_type == "LED":
						loc = str(action.get("location", "UNKNOWN")).upper()
						self.state.led_states[loc] = action.get("state")

				result = AgentResult(
					reply=reply,
					actions=fast_actions,
					route_type=RouteType.FAST_COMMAND,
					intent=Intent.DEVICE_CONTROL,
				)
				self._save_turn(clean_input, result.reply)
				return result
		else:
			print(f"偵測到疑問句 '{clean_input}'，跳過 FastPath，準備交給 LLM...")
		memory_context = self.memory.get_context(limit=5)
		llm_reply = self.llm_responder(clean_input, memory_context)
		self.state.set_state(
			status="llm_reply",
			llm_reply=llm_reply,
		)
		result = AgentResult(
			reply=llm_reply,
			actions=[],
			route_type=decision.route_type,
			intent=decision.intent,
		)
		self._save_turn(clean_input, result.reply)
		return result


if __name__ == "__main__":
	# 測試區域：先用 no-op action executor 與預設 llm responder 跑整體流程。
	agent = SmartHomeAgent()

	test_inputs = [
		"幫我開客廳燈",
		"溫度調到 26 度",
		"你好",
		"清除記憶",
		"幫我關風扇",
	]

	print("=== SmartHomeAgent Test Area ===")
	for text in test_inputs:
		out = agent.handle(text, current_temp=25, ambient_temp=29)
		print(f"\ninput={text!r}")
		print("intent:", out.intent.value)
		print("route:", out.route_type.value)
		print("actions:", out.actions)
		print("reply:", out.reply)


# ===================== SmartHomeAgent 完整流程與功能說明 =====================
#
# 這個檔案的角色：
# - 它是「總控協調器 (orchestrator)」，負責串接 Router / Parser / Memory / State。
# - 它不負責具體硬體控制細節，也不負責 LLM 模型細節。
#
# 主要 class 與責任：
# 1) AgentResult
#    - 統一每一輪回傳格式。
#    - 欄位包含：reply、actions、route_type、intent、error。
#
# 2) SmartHomeAgent
#    - 負責整體流程控制。
#    - 透過依賴注入接收 router / parser / memory / state / executor / llm_responder。
#
# SmartHomeAgent.handle(...) 一輪完整流程：
# Step 1: 清理輸入
# - 將 user_input 做 strip。
# - 若為空字串，直接回覆提示訊息，並寫入 memory。
#
# Step 2: 路由判斷
# - 呼叫 router.route(clean_input) 得到 intent 與 route_type。
# - 同步更新 state：conversation_active、last_user_input、last_intent。
#
# Step 3: SYSTEM 指令快速處理
# - 若 intent 是 SYSTEM，交給 _handle_system_intent。
# - 目前支援「清除記憶/reset」：會清 short-term memory 並重置對話狀態。
#
# Step 4: FAST_COMMAND 路徑
# - 呼叫 parser.parse(..., return_reply=True)：
#   parser 內部流程是 fastpath -> gemini fallback。
# - 取得 actions 後，交給 action_executor(actions) 執行。
# - 若 parser 沒給 reply，使用預設 reply。
# - 根據 actions 更新 state.device_states：
#   SET_TEMP -> temperature
#   FAN      -> fan
#   LED      -> light_{location}
# - 將本輪結果寫入 memory。
#
# Step 5: LLM 路徑
# - 取得 memory_context = memory.get_context(limit=5)。
# - 呼叫 llm_responder(user_input, memory_context) 產生回覆。
# - 將回覆寫入 memory，actions 為空。
#
# 注入點（方便後續替換）：
# - action_executor: 之後可接 device_controller.py 真實硬體控制。
# - llm_responder: 之後可接 llm_engine.py 正式 LLM 對話。
#
# 為何這樣設計：
# - 高內聚：agent 專注流程協調。
# - 低耦合：硬體與 LLM 可獨立替換。
# - 好測試：可用 mock executor / mock llm_responder 做單元測試。
# - 可擴充：未來加上 confirmation、tool calling、multi-device transaction 比較容易。
