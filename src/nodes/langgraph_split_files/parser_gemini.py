"""
Gemini-based fuzzy parsing for:
- Temperature control (explicit/fuzzy/relative)
- Fan on/off
- Kitchen/Living/Guest lights on/off

Keeps "fuzzy semantics" + "memory rules" features by injecting memory.txt
and recent history.jsonl into the prompt.
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple, Union

from google import genai

import src.utils.config as config
from src.nodes.langgraph_split_files.actions_schema import ActionDict
from src.nodes.langgraph_split_files.parser_fastpath import apply_memory_rules
from src.utils.file_io import read_text, format_history_for_prompt
from src.nodes.langgraph_split_files.validator import validate_actions

# The client automatically reads GEMINI_API_KEY from environment variables.
# client = genai.Client()  # 移到函式內初始化

_FENCE_RE_1 = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_RE_2 = re.compile(r"\s*```$", re.IGNORECASE)

def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = _FENCE_RE_1.sub("", s)
    s = _FENCE_RE_2.sub("", s)
    return s.strip()

def _get_gemini_client():
    """延遲初始化 Gemini client，避免在模塊載入時就檢查 API key"""
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError(
                "缺少 GEMINI_API_KEY 環境變數！\n"
                "請設定環境變數：\n"
                "export GEMINI_API_KEY='你的API金鑰'\n"
                "或在程式中設定：\n"
                "import os\n"
                "os.environ['GEMINI_API_KEY'] = '你的API金鑰'"
            )
        return genai.Client(api_key=api_key)
    except Exception as e:
        raise ValueError(f"初始化 Gemini client 失敗: {e}") from e

def parse_with_gemini(
    user_text: str,
    current_temp: Optional[int] = None,
    return_reply: bool = False
) -> Union[List[ActionDict], Tuple[List[ActionDict], Optional[str]]]:
    """
    Returns a validated list of ActionDict.

    current_temp is used to interpret relative temperature commands ("hot/cold a bit").
    """
    if not user_text or not user_text.strip():
        return ([], None) if return_reply else []

    # Apply memory rewrites first (so user-defined shortcuts affect the prompt too)
    rewritten = apply_memory_rules(user_text)

    memory_context = read_text(config.MEMORY_FILE)
    history_context = format_history_for_prompt()
    cur = int(current_temp) if current_temp is not None else 25

    # keep bounded
    if len(memory_context) > 2000:
        memory_context = memory_context[-2000:]
    if len(history_context) > 2000:
        history_context = history_context[-2000:]

    prompt = f"""
You are a smart-home command parser.
You must output JSON ONLY.

OUTPUT FORMAT (hard constraints):
- Output must be exactly a single JSON array.
- Each element is an action object with:
  - type: one of ["SET_TEMP","FAN","LED"]
  - For SET_TEMP: value (number)
  - For FAN: state ("on"|"off"), optional duration (seconds integer)
  - For LED: location ("KITCHEN"|"LIVING"|"GUEST"), state ("on"|"off"), optional duration (seconds integer)

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
   - Use current temperature setting {cur}.
   - Typical adjustments:
     * "cold" => +2
     * "hot" => -2
     * "higher a bit" => +1
     * "lower a bit" => -1
   - Apply memory rules if they define custom meanings.
   - Then clamp.

CONTEXT:
- Current temperature setting is {cur} °C.
- Memory rules (user preferences) to apply:
{memory_context if memory_context else "(empty)"}

- Recent conversation history (most recent last):
{history_context if history_context else "(empty)"}

USER COMMAND:
{rewritten}

Now output JSON only.
""".strip()

    # 延遲初始化 client
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        reply_text = response.text or ""
    except Exception as e:
        if return_reply:
            return [], f"[gemini_error] {e}"
        return []

    raw = _strip_code_fences(reply_text)

    # Parse JSON
    try:
        data = json.loads(raw)
    except Exception:
        # Fail-closed
        return ([], raw) if return_reply else []

    if not isinstance(data, list):
        return ([], raw) if return_reply else []

    actions: List[ActionDict] = []
    for item in data:
        if isinstance(item, dict):
            actions.append(dict(item))

    # Validate & normalize
    validated = validate_actions(actions)
    if return_reply:
        return validated, raw
    return validated
