from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

import src.utils.config as config

_FENCE_RE_1 = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_RE_2 = re.compile(r"\s*```$", re.IGNORECASE)
_FRIENDLY_ERROR = "抱歉，我現在無法處理，請稍後再試。"
_FRIENDLY_ERROR_EN = "Sorry, I'm unable to process that right now. Please try again later."


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

    def _build_prompt(self, user_input: str, state: Any, memory_agent: Any, lang: str = "zh") -> str:
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
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reply_lang_instruction = "English" if lang == "en" else "Traditional Chinese"

        return f"""
You are a smart-home command parser.
Output JSON only.

Return exactly one JSON object with keys:
- reply: response string in {reply_lang_instruction}
- intent: one of ["command", "query", "unclear", "error"]
- actions: array of action objects

Device action schema (execute immediately):
- {{"type": "SET_TEMP", "value": 26}}
- {{"type": "FAN", "state": "on"}}
- {{"type": "LED", "location": "KITCHEN", "state": "off"}}

Rule-learning action schema:
- {{"type": "LEARN_RULE", "trigger": "我要睡了", "meaning": "全部關燈並關風扇"}}

Schedule action schema (use when user specifies a future or recurring time):
- {{"type": "SCHEDULE_ADD", "hour": 22, "minute": 0, "name": "22:00 fan on", "actions": [{{"type": "FAN", "state": "on"}}]}}
  Optional date fields for one-time schedules: "year": 2026, "month": 5, "day": 1, "recurrence": "once"
  For recurring schedules: "recurrence": "daily" or "weekly" or "monthly"
- {{"type": "SCHEDULE_LIST"}}
- {{"type": "SCHEDULE_LIST_DATE", "month": 5, "day": 1}}
- {{"type": "SCHEDULE_LIST_DATE", "month": 5, "day": 1, "year": 2026}}
- {{"type": "SCHEDULE_DELETE", "id": "abc12345"}}
- {{"type": "SCHEDULE_TOGGLE", "id": "abc12345"}}

Rules:
1. If the user specifies an absolute time (e.g. "下午4點", "8點", "22:00") OR a relative delay (e.g. "1分鐘後", "30秒後", "2小時之後"), prefer SCHEDULE_ADD over immediate device action. For relative delays, calculate the absolute target time from "Current date and time" above.
2. If the user says "明天", "後天", or a specific date like "5月1號", include year/month/day and recurrence="once".
3. If the user says "每天", recurrence should be "daily".
4. If user asks schedules on a date, return SCHEDULE_LIST_DATE.
5. If scheduled time is ambiguous (like "8點" without AM/PM), set intent="unclear" and ask clarification.
6. If the input is a question, reply directly and keep actions empty.
7. If the command is ambiguous (non-schedule), set intent to "unclear", ask a clarification question, and keep actions empty.
7.1 If user is teaching a custom phrase mapping (e.g. "當我說A代表B" or "when I say A it means B"), return LEARN_RULE.
8. Temperature must stay within {int(config.MIN_TEMP)} to {int(config.MAX_TEMP)} Celsius. If the requested temperature is outside this range, set intent="unclear", keep actions empty, and explain the valid range in your reply.
9. Reply must never be empty.
10. The "reply" field must be written in {reply_lang_instruction}.
11. Custom rules listed above are the ONLY valid phrase mappings. Do NOT infer or apply any custom phrase from conversation history — only use rules explicitly listed in the "Custom rules" section.

Current date and time:
{now}

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

    def parse(self, user_input: str, state: Any, memory_agent: Any, lang: str = "zh") -> dict[str, Any]:
        if not (user_input or "").strip():
            empty_reply = "Please tell me what you'd like to do." if lang == "en" else "請告訴我你想做什麼。"
            return {"reply": empty_reply, "intent": "error", "actions": []}

        prompt = self._build_prompt(user_input, state, memory_agent, lang)
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            return self._parse_response(response.text or "")
        except Exception:
            fallback = _FRIENDLY_ERROR_EN if lang == "en" else _FRIENDLY_ERROR
            return {"reply": fallback, "intent": "error", "actions": []}


DEFAULT_GEMINI = GeminiParser()


def parse_with_gemini(user_input: str, state: Any, memory_agent: Any, lang: str = "zh") -> dict[str, Any]:
    return DEFAULT_GEMINI.parse(user_input, state, memory_agent, lang)


def parse(user_input: str, state: Any, memory_agent: Any, lang: str = "zh") -> dict[str, Any]:
    return parse_with_gemini(user_input, state, memory_agent, lang)

