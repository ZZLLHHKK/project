"""
Fast-path parsing & memory rule learning/application.

This module aims to avoid LLM calls when the user intent is explicit.
It also preserves the "memory" capability from temp_7seg_fuzzy_memory.py:
- Learn rules like: 當我說 X 代表 Y
- Store to memory.txt as: RULE: When user says 'X', it means 'Y'.
- Apply those rules by rewriting user text before parsing.
"""
from __future__ import annotations

import re
import math
from typing import Optional, Tuple, List, Dict, Any

import src.utils.config as config
from src.nodes.langgraph_split_files.actions_schema import ActionDict
from src.utils.file_io import read_text, load_history, save_history, push_history, format_history_for_prompt, load_rules, append_line_unique

# -------------------------
# Math helpers
# -------------------------
def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# -------------------------
# Memory learning rules
# -------------------------
LEARN_PATTERNS = [
    re.compile(r"^\s*當我說\s*(.+?)\s*(?:的時候|時|時候)?\s*[，,]?\s*代表\s*(.+?)\s*$"),
    re.compile(r"^\s*(?:以後|之後)\s*我說\s*(.+?)\s*(?:就|代表)\s*(.+?)\s*$"),
    re.compile(r"^\s*如果我說\s*(.+?)\s*[，,]?\s*(?:請|就)\s*(.+?)\s*$"),
]

def try_learn_rule(user_text: str) -> Optional[Dict[str, Any]]:
    """
    If user text looks like a "teaching" sentence, save it into memory.txt.
    Returns a dict describing what was saved, or None.
    """
    t = (user_text or "").strip()
    for pat in LEARN_PATTERNS:
        m = pat.match(t)
        if not m:
            continue
        trigger = m.group(1).strip().strip("「」\"'")
        meaning = m.group(2).strip().strip("「」\"'")
        if not trigger or not meaning:
            continue

        rule_line = f"RULE: When user says '{trigger}', it means '{meaning}'."
        append_line_unique(config.MEMORY_FILE, rule_line)
        out = {"intent": "learn_rule", "saved_rule": {"trigger": trigger, "meaning": meaning}}
        push_history(user_text, out)
        return out
    return None

def apply_memory_rules(user_text: str) -> str:
    """
    Rewrite user text using stored rules, from oldest to newest.
    Simple approach: substring replace trigger -> meaning.
    """
    text = user_text or ""
    for trigger, meaning in load_rules():
        if trigger and trigger in text:
            text = text.replace(trigger, meaning)
    return text

# -------------------------
# Fast local extraction
# -------------------------
NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:度|°|c|℃)?", re.IGNORECASE)

def extract_explicit_temp(user_text: str) -> Optional[float]:
    matches = NUM_RE.findall(user_text or "")
    if not matches:
        return None
    for s in matches:
        try:
            v = float(s)
        except Exception:
            continue
        # loose filter to avoid picking phone numbers etc.
        if 0.0 <= v <= 60.0:
            return v
    return None

# Chinese/English keyword sets
KW_ON  = ("開", "打開", "開啟", "on", "turn on", "open")
KW_OFF = ("關", "關掉", "關閉", "off", "turn off", "close")

def _contains_any(text: str, keywords) -> bool:
    t = (text or "").lower()
    for k in keywords:
        if k.lower() in t:
            return True
    return False

def parse_fastpath(user_text: str) -> Optional[List[ActionDict]]:
    """
    Returns a list of actions if we can parse without LLM, else None.

    This parser handles:
    - Explicit temperature number -> SET_TEMP
    - Fan on/off
    - Kitchen/Living/Guest lights on/off
    - All off commands
    """
    if not user_text or not user_text.strip():
        return None

    # 0) Apply memory rewrites first
    text = apply_memory_rules(user_text)

    # 1) Explicit temperature
    v = extract_explicit_temp(text)
    if v is not None:
        temp_f = clamp(float(v), config.MIN_TEMP, config.MAX_TEMP)
        temp_i = round_half_up(temp_f)
        temp_i = int(clamp(temp_i, int(config.MIN_TEMP), int(config.MAX_TEMP)))
        actions = [{"type": "SET_TEMP", "value": temp_i}]
        push_history(user_text, {"fastpath": True, "actions": actions})
        return actions

    t = text.lower()

    # 2) All off
    if ("全部" in t or "all" in t) and _contains_any(t, KW_OFF):
        actions: List[ActionDict] = [
            {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
            {"type": "LED", "location": config.LOC_LIVING,  "state": "off"},
            {"type": "LED", "location": config.LOC_GUEST,   "state": "off"},
            {"type": "FAN", "state": "off"},
        ]
        push_history(user_text, {"fastpath": True, "actions": actions})
        return actions

    # 3) Fan
    if ("風扇" in t) or ("fan" in t):
        if _contains_any(t, KW_ON) and not _contains_any(t, KW_OFF):
            actions = [{"type": "FAN", "state": "on"}]
            push_history(user_text, {"fastpath": True, "actions": actions})
            return actions
        if _contains_any(t, KW_OFF) and not _contains_any(t, KW_ON):
            actions = [{"type": "FAN", "state": "off"}]
            push_history(user_text, {"fastpath": True, "actions": actions})
            return actions
        # ambiguous (mentions both on/off) -> let LLM decide
        return None

    # 4) Lights by location
    loc_map = {
        config.LOC_KITCHEN: ("廚房", "kitchen"),
        config.LOC_LIVING:  ("客廳", "living"),
        config.LOC_GUEST:   ("客房", "guest"),
    }

    # 4a) Location mentioned without explicit "燈" (assume light)
    if any(k in t for keys in loc_map.values() for k in keys):
        if _contains_any(t, KW_ON) and not _contains_any(t, KW_OFF):
            actions_loc: List[ActionDict] = []
            for loc, keys in loc_map.items():
                if any(k in t for k in keys):
                    actions_loc.append({"type": "LED", "location": loc, "state": "on"})
            if actions_loc:
                push_history(user_text, {"fastpath": True, "actions": actions_loc})
                return actions_loc
        if _contains_any(t, KW_OFF) and not _contains_any(t, KW_ON):
            actions_loc = []
            for loc, keys in loc_map.items():
                if any(k in t for k in keys):
                    actions_loc.append({"type": "LED", "location": loc, "state": "off"})
            if actions_loc:
                push_history(user_text, {"fastpath": True, "actions": actions_loc})
                return actions_loc

    found_any = False
    actions_out: List[ActionDict] = []

    for loc, keys in loc_map.items():
        if any(k in t for k in keys) and ("燈" in t or "light" in t or "lamp" in t):
            found_any = True
            if _contains_any(t, KW_ON) and not _contains_any(t, KW_OFF):
                actions_out.append({"type": "LED", "location": loc, "state": "on"})
            elif _contains_any(t, KW_OFF) and not _contains_any(t, KW_ON):
                actions_out.append({"type": "LED", "location": loc, "state": "off"})
            else:
                # ambiguous: let LLM decide
                return None

    if found_any and actions_out:
        push_history(user_text, {"fastpath": True, "actions": actions_out})
        return actions_out

    # 4b) Light mentioned without location -> apply to all lights
    if ("燈" in t or "light" in t or "lamp" in t):
        if _contains_any(t, KW_ON) and not _contains_any(t, KW_OFF):
            actions_all: List[ActionDict] = [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "on"},
                {"type": "LED", "location": config.LOC_LIVING,  "state": "on"},
                {"type": "LED", "location": config.LOC_GUEST,   "state": "on"},
            ]
            push_history(user_text, {"fastpath": True, "actions": actions_all})
            return actions_all
        if _contains_any(t, KW_OFF) and not _contains_any(t, KW_ON):
            actions_all = [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
                {"type": "LED", "location": config.LOC_LIVING,  "state": "off"},
                {"type": "LED", "location": config.LOC_GUEST,   "state": "off"},
            ]
            push_history(user_text, {"fastpath": True, "actions": actions_all})
            return actions_all

    return None
