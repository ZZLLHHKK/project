from __future__ import annotations

import json
import os
import re
from typing import Any

import src.utils.config as config

_FENCE_RE_1 = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_RE_2 = re.compile(r"\s*```$", re.IGNORECASE)
_FRIENDLY_ERROR = "抱歉，我現在無法處理，請稍後再試。"


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    stripped = _FENCE_RE_1.sub("", stripped)
    stripped = _FENCE_RE_2.sub("", stripped)
    return stripped.strip()


def _try_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    load_dotenv(override=False)


def _get_client() -> Any:
    _try_load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("missing gemini api key")
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiParser:
    """Build prompt, call Gemini, and parse structured response."""

    def _build_prompt(self, user_input: str, state: Any, memory_agent: Any) -> str:
        current_state = state.get_state() if hasattr(state, "get_state") else {}
        recent_context = memory_agent.get_recent_context(limit=5)
        rules = memory_agent.load_rules()

        rules_lines = []
        for rule in rules:
            trigger = rule.get("trigger")
            meaning = rule.get("meaning")
            if trigger and meaning:
                rules_lines.append(f"- 當使用者說「{trigger}」時，代表「{meaning}」")

        rules_block = "\n".join(rules_lines) if rules_lines else "(no custom rules)"
        light = current_state.get("light", {})
        ambient_temp = current_state.get("ambient_temp")
        ambient_humidity = current_state.get("ambient_humidity")

        return f"""
You are a smart-home command parser.
Output JSON only.

Return exactly one JSON object with keys:
- reply: Traditional Chinese response string
- intent: one of [\"command\", \"query\", \"unclear\", \"error\"]
- actions: array of action objects

Action schema:
- {{"type": "SET_TEMP", "value": 26}}
- {{"type": "FAN", "state": "on"}}
- {{"type": "LED", "location": "KITCHEN", "state": "off"}}

Rules:
1. If the input is a question, reply directly and keep actions empty.
2. If the command is ambiguous, set intent to "unclear", ask a clarification question, and keep actions empty.
3. Temperature must stay within {int(config.MIN_TEMP)} to {int(config.MAX_TEMP)} Celsius.
4. Reply must never be empty.

Current state:
- temperature: {current_state.get('temperature', current_state.get('setpoint_temp', 25))}
- fan: {current_state.get('fan', current_state.get('fan_state', 'off'))}
- kitchen light: {light.get('KITCHEN', 'off')}
- living light: {light.get('LIVING', 'off')}
- guest light: {light.get('GUEST', 'off')}
- ambient_temp: {ambient_temp}
- ambient_humidity: {ambient_humidity}

Custom rules:
{rules_block}

Recent context:
{recent_context}

User input:
{user_input}
""".strip()

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        raw = _strip_code_fences(response_text)
        try:
            payload = json.loads(raw)
        except Exception:
            return {"reply": "抱歉，可以請您再說一次嗎？", "intent": "error", "actions": []}

        if not isinstance(payload, dict):
            return {"reply": _FRIENDLY_ERROR, "intent": "error", "actions": []}

        actions = payload.get("actions", [])
        if not isinstance(actions, list):
            actions = []

        cleaned_actions = [item for item in actions if isinstance(item, dict)]
        intent = str(payload.get("intent") or "command").strip().lower()
        if intent not in {"command", "query", "unclear", "error"}:
            intent = "command"

        reply = str(payload.get("reply") or "好的，已為您處理。")
        return {"reply": reply, "intent": intent, "actions": cleaned_actions}

    def parse(self, user_input: str, state: Any, memory_agent: Any) -> dict[str, Any]:
        if not (user_input or "").strip():
            return {"reply": "請告訴我你想做什麼。", "intent": "error", "actions": []}

        prompt = self._build_prompt(user_input, state, memory_agent)
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            return self._parse_response(response.text or "")
        except Exception:
            return {"reply": _FRIENDLY_ERROR, "intent": "error", "actions": []}


DEFAULT_GEMINI = GeminiParser()


def parse_with_gemini(user_input: str, state: Any, memory_agent: Any) -> dict[str, Any]:
    return DEFAULT_GEMINI.parse(user_input, state, memory_agent)


def parse(user_input: str, state: Any, memory_agent: Any) -> dict[str, Any]:
    return parse_with_gemini(user_input, state, memory_agent)

