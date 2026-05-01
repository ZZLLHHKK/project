from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FRIENDLY_ERROR = "抱歉，我現在無法處理，請稍後再試。"


@dataclass(slots=True)
class CommandResult:
    raw_reply: str
    error: str | None
    actions: list[dict[str, Any]]
    state: dict[str, Any] | None
    should_standby: bool
    should_shutdown: bool
    payload: dict[str, Any]


def execute_text_command(agent: Any, text: str, lang: str | None = None) -> CommandResult:
    try:
        payload = agent.handle(text, lang=lang)
    except Exception:
        payload = {"reply": FRIENDLY_ERROR, "actions_executed": [], "error": "agent_handle_failed"}

    raw_reply = str(payload.get("reply") or "")
    error = payload.get("error")
    actions = payload.get("actions_executed", [])
    if not isinstance(actions, list):
        actions = []
    print(f"[COMMAND SERVICE] actions before execute: {actions}")

    should_standby = any(isinstance(action, dict) and action.get("type") == "ENTER_STANDBY" for action in actions)
    should_shutdown = any(isinstance(action, dict) and action.get("type") == "SHUTDOWN" for action in actions)

    state = payload.get("state")
    if not isinstance(state, dict):
        state = None

    return CommandResult(
        raw_reply=raw_reply,
        error=str(error) if error is not None else None,
        actions=actions,
        state=state,
        should_standby=should_standby,
        should_shutdown=should_shutdown,
        payload=payload,
    )