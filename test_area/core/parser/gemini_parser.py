"""
Gemini-based fuzzy parsing for:
- Temperature control (explicit/fuzzy/relative)
- Fan on/off
- Kitchen/Living/Guest lights on/off

Keeps "fuzzy semantics" + "memory rules" features by injecting rules.json
and recent history.jsonl into the prompt.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from google import genai

# Allow direct execution: python test_area/core/parser/gemini_parser.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.utils.config as config
from src.nodes.langgraph_split_files.actions_schema import ActionDict
from src.nodes.langgraph_split_files.parser_fastpath import apply_memory_rules
from src.utils.file_io import read_text, format_history_for_prompt
from src.nodes.langgraph_split_files.validator import validate_actions

# The client automatically reads GEMINI_API_KEY from environment variables.
# client = genai.Client()  # 移到函式內初始化

_FENCE_RE_1 = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_RE_2 = re.compile(r"\s*```$", re.IGNORECASE)


def _try_load_dotenv() -> None:
    """Best-effort .env loading so GEMINI_API_KEY can be read from project env file."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    load_dotenv(override=False)

def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = _FENCE_RE_1.sub("", s)
    s = _FENCE_RE_2.sub("", s)
    return s.strip()

def _get_gemini_client() -> genai.Client:
    """延遲初始化 Gemini client，避免在模塊載入時就檢查 API key"""
    try:
        _try_load_dotenv()
        # Accept both names for compatibility with different SDK examples.
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "缺少 API KEY 環境變數！\n"
                "請設定環境變數：\n"
                "export GEMINI_API_KEY='你的API金鑰'\n"
                "或\n"
                "export GOOGLE_API_KEY='你的API金鑰'\n"
                "或在程式中設定：\n"
                "import os\n"
                "os.environ['GEMINI_API_KEY'] = '你的API金鑰'"
            )
        return genai.Client(api_key=api_key)
    except Exception as e:
        raise ValueError(f"初始化 Gemini client 失敗: {e}") from e


@dataclass(slots=True)
class PromptContext:
    rewritten_text: str
    rules_context: str
    history_context: str
    current_temp: int
    ambient_temp: Optional[int]
    ambient_humidity: Optional[int]


class PromptBuilder:
    """Only responsible for gathering context and building prompt text."""

    def __init__(
        self,
        memory_rule_applier: Callable[[str], str] = apply_memory_rules,
        rules_reader: Callable[[str], str] = read_text,
        history_formatter: Callable[[], str] = format_history_for_prompt,
    ) -> None:
        self.memory_rule_applier = memory_rule_applier
        self.rules_reader = rules_reader
        self.history_formatter = history_formatter

    def _bounded(self, text: str, limit: int = 2000) -> str:
        if len(text) <= limit:
            return text
        return text[-limit:]

    def build_context(
        self,
        user_text: str,
        current_temp: Optional[int],
        ambient_temp: Optional[int],
        ambient_humidity: Optional[int] = None,
    ) -> PromptContext:
        rewritten = self.memory_rule_applier(user_text)
        rules_context = self._bounded(self.rules_reader(config.RULES_FILE) or "")
        history_context = self._bounded(self.history_formatter() or "")
        cur = int(current_temp) if current_temp is not None else 25
        amb = int(ambient_temp) if ambient_temp is not None else None
        hum = int(ambient_humidity) if ambient_humidity is not None else None
        return PromptContext(
            rewritten_text=rewritten,
            rules_context=rules_context,
            history_context=history_context,
            current_temp=cur,
            ambient_temp=amb,
            ambient_humidity=hum,
        )

    def build_prompt(self, ctx: PromptContext) -> str:
            return f"""
You are a smart-home command parser.
You must output JSON ONLY.

OUTPUT FORMAT (hard constraints):
- Output must be exactly a single JSON object with two keys: "actions" and "reply".
- "actions": A JSON array of action objects.
    - type: one of ["SET_TEMP","FAN","LED"]
    - For SET_TEMP: value (number)
    - For FAN: state ("on"|"off"), optional duration (seconds integer)
    - For LED: location ("KITCHEN"|"LIVING"|"GUEST"), state ("on"|"off"), optional duration (seconds integer)
- "reply": A natural, conversational response in Traditional Chinese (zh-TW).
    - Act as a helpful assistant. (e.g., "好的，已經為您開啟客廳燈。")
    - Use commas (，) and periods (。) properly for text-to-speech pauses.
    - If a request violates constraints (e.g., temperature > {config.MAX_TEMP}), return empty actions [] and politely explain why in the reply.

DEVICE MAPPING:
- Kitchen light => LED location "KITCHEN"
- Living room light => LED location "LIVING"
- Guest room light => LED location "GUEST"
- Fan => type "FAN"
- Temperature => type "SET_TEMP" (Celsius)

SYSTEM RULES:
- Temperature unit is Celsius.
- Absolute safety range: {config.MIN_TEMP} to {config.MAX_TEMP} inclusive.
    If asked outside, clamp into range.
- Comfort range: {config.COMFORT_MIN} to {config.COMFORT_MAX}.
- Ignore profanity/filled words; parse only the intent.
- If the user mentions multiple devices, output multiple actions.
- If the command is unrelated, output [].

TEMPERATURE INTERPRETATION:
1) If user explicitly specifies a number, use it (then clamp).
2) If user is fuzzy (e.g., "comfortable"), choose a reasonable number within comfort range.
3) If user is relative without a number:
     - Use current temperature setting {ctx.current_temp}.
     - Typical adjustments:
         * "cold" => +2
         * "hot" => -2
         * "higher a bit" => +1
         * "lower a bit" => -1
     - Apply memory rules if they define custom meanings.
     - Then clamp.

CONTEXT:
- Current temperature setting is {ctx.current_temp} C.
- Ambient temperature from sensor is {ctx.ambient_temp} C (if provided).
- Ambient humidity from sensor is {ctx.ambient_humidity} % (if provided).
- Memory rules (user preferences) to apply:
{ctx.rules_context if ctx.rules_context else "(empty)"}

- Recent conversation history (most recent last):
{ctx.history_context if ctx.history_context else "(empty)"}

USER COMMAND:
{ctx.rewritten_text}

Now output JSON only.
""".strip()


class ResponseParser:
    """Only responsible for decoding/validating LLM response text."""

    def __init__(self, validator: Callable[[List[ActionDict]], List[ActionDict]] = validate_actions) -> None:
        self.validator = validator

    def parse(self, response_text: str) -> Tuple[List[ActionDict], str, Optional[str]]:
        raw = _strip_code_fences(response_text)
        try:
            data = json.loads(raw)
        except Exception:
            return [], "抱歉，可以請您再說一次嗎？", "json_parse_failed"

        if not isinstance(data, dict):
            return [], "解析格式錯誤。", "payload_not_object"

        raw_actions = data.get("actions", [])
        reply_text = data.get("reply", "好的，已為您處理。")

        actions: List[ActionDict] = []
        if isinstance(raw_actions, list):
            for item in raw_actions:
                if isinstance(item, dict):
                    actions.append(dict(item))

        validated = self.validator(actions)
        return validated, reply_text, None


class GeminiParser:
    """Facade parser: build prompt, call Gemini, parse and validate output."""

    def __init__(
        self,
        client_factory: Callable[[], genai.Client] = _get_gemini_client,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None:
        self.client_factory = client_factory
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.response_parser = response_parser or ResponseParser()

    def _call_gemini(self, prompt: str) -> str:
        client = self.client_factory()
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        return response.text or ""

    def parse(
        self,
        user_text: str,
        current_temp: Optional[int] = None,
        ambient_temp: Optional[int] = None,
        ambient_humidity: Optional[int] = None,
        return_reply: bool = False,
    ) -> Union[List[ActionDict], Tuple[List[ActionDict], Optional[str]]]:
        """Return validated actions, with optional assistant reply."""
        if not user_text or not user_text.strip():
            return ([], None) if return_reply else []

        ctx = self.prompt_builder.build_context(user_text, current_temp, ambient_temp, ambient_humidity)
        prompt = self.prompt_builder.build_prompt(ctx)

        try:
            llm_text = self._call_gemini(prompt)
        except Exception as e:
            if return_reply:
                return [], f"[gemini_error] {e}"
            return []

        actions, reply_text, _ = self.response_parser.parse(llm_text)
        if return_reply:
            return actions, reply_text
        return actions


_DEFAULT_GEMINI_PARSER = GeminiParser()


def parse_with_gemini(
    user_text: str,
    current_temp: Optional[int] = None,
    ambient_temp: Optional[int] = None,
    ambient_humidity: Optional[int] = None,
    return_reply: bool = False
) -> Union[List[ActionDict], Tuple[List[ActionDict], Optional[str]]]:
    """Backward-compatible function wrapper."""
    return _DEFAULT_GEMINI_PARSER.parse(
        user_text=user_text,
        current_temp=current_temp,
        ambient_temp=ambient_temp,
        ambient_humidity=ambient_humidity,
        return_reply=return_reply,
    )


if __name__ == "__main__":
    # 測試區域：直接執行本檔可做 smoke test。
    # 注意：此測試會真的呼叫 Gemini API，請先確認 .env 或環境變數有設定 GEMINI_API_KEY。
    print("=== GeminiParser Test Area ===")

    parser = GeminiParser()
    samples = [
        "把克聽燈打開",
        "溫度調到27度",
        "幫我關掉全部",
        "今天天期如何",
    ]

    for idx, text in enumerate(samples, start=1):
        print(f"\n[{idx}] input={text!r}")
        actions, reply = parser.parse(text, current_temp=25, ambient_temp=29, return_reply=True)
        print("actions:", actions)
        print("reply:", reply)