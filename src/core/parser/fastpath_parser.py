from __future__ import annotations

import math
import re
from typing import Any, Optional

import src.utils.config as config

LEARN_PATTERNS = [
    re.compile(r"^\s*當我說\s*(.+?)\s*(?:的時候|時|時候)?\s*[，,]?\s*代表\s*(.+?)\s*$"),
    re.compile(r"^\s*(?:以後|之後)\s*我說\s*(.+?)\s*(?:就|代表)\s*(.+?)\s*$"),
    re.compile(r"^\s*如果我說\s*(.+?)\s*[，,]?\s*(?:請|就)\s*(.+?)\s*$"),
]

TEMP_KEYWORDS = ("溫度", "溫控", "冷氣", "空調", "度", "℃", "調到", "設定")
NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:度|°|c|℃)?", re.IGNORECASE)

KW_ON = ("開", "打開", "開啟", "on", "turn on")
KW_OFF = ("關", "關掉", "關閉", "off", "turn off")
LOC_MAP = {
    config.LOC_KITCHEN: ("廚房", "kitchen"),
    config.LOC_LIVING: ("客廳", "living"),
    config.LOC_GUEST: ("客房", "guest"),
}


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _clamp_temperature(value: float) -> int:
    rounded = int(math.floor(value + 0.5))
    return int(max(config.MIN_TEMP, min(config.MAX_TEMP, rounded)))


class FastPathParser:
    """Rule-based parser for explicit commands and user-taught aliases."""

    def try_learn_rule(self, user_text: str) -> Optional[dict[str, str]]:
        text = (user_text or "").strip()
        for pattern in LEARN_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            trigger = match.group(1).strip().strip("「」\"'")
            meaning = match.group(2).strip().strip("「」\"'")
            if trigger and meaning:
                return {"trigger": trigger, "meaning": meaning}
        return None

    def apply_rules(self, user_text: str, rules: list[dict[str, str]]) -> str:
        text = user_text or ""
        for rule in rules:
            trigger = str(rule.get("trigger", "")).strip()
            meaning = str(rule.get("meaning", "")).strip()
            if trigger and meaning:
                text = text.replace(trigger, meaning)
        return text

    def _parse_temperature(self, text: str) -> Optional[list[dict[str, Any]]]:
        if not any(keyword in text for keyword in TEMP_KEYWORDS):
            return None
        for raw in NUM_RE.findall(text):
            try:
                value = float(raw)
            except Exception:
                continue
            if 0 <= value <= 60:
                return [{"type": "SET_TEMP", "value": _clamp_temperature(value)}]
        return None

    def _parse_fan(self, text: str) -> Optional[list[dict[str, Any]]]:
        if "風扇" not in text and "fan" not in text.lower():
            return None
        if _contains_any(text, KW_ON) and not _contains_any(text, KW_OFF):
            return [{"type": "FAN", "state": "on"}]
        if _contains_any(text, KW_OFF) and not _contains_any(text, KW_ON):
            return [{"type": "FAN", "state": "off"}]
        return None

    def _parse_all_off(self, text: str) -> Optional[list[dict[str, Any]]]:
        lowered = text.lower()
        if not (("全部" in text or "all" in lowered) and _contains_any(text, KW_OFF)):
            return None
        return [
            {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
            {"type": "LED", "location": config.LOC_LIVING, "state": "off"},
            {"type": "LED", "location": config.LOC_GUEST, "state": "off"},
            {"type": "FAN", "state": "off"},
        ]

    def _parse_lights(self, text: str) -> Optional[list[dict[str, Any]]]:
        lowered = text.lower()
        has_light_word = "燈" in text or "light" in lowered or "lamp" in lowered

        results: list[dict[str, Any]] = []
        for location, aliases in LOC_MAP.items():
            if any(alias in text or alias in lowered for alias in aliases):
                if _contains_any(text, KW_ON) and not _contains_any(text, KW_OFF):
                    results.append({"type": "LED", "location": location, "state": "on"})
                elif _contains_any(text, KW_OFF) and not _contains_any(text, KW_ON):
                    results.append({"type": "LED", "location": location, "state": "off"})

        if results:
            return results

        if not has_light_word:
            return None

        if _contains_any(text, KW_ON) and not _contains_any(text, KW_OFF):
            return [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "on"},
                {"type": "LED", "location": config.LOC_LIVING, "state": "on"},
                {"type": "LED", "location": config.LOC_GUEST, "state": "on"},
            ]
        if _contains_any(text, KW_OFF) and not _contains_any(text, KW_ON):
            return [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
                {"type": "LED", "location": config.LOC_LIVING, "state": "off"},
                {"type": "LED", "location": config.LOC_GUEST, "state": "off"},
            ]
        return None

    def parse(self, user_text: str, rules: Optional[list[dict[str, str]]] = None) -> Optional[list[dict[str, Any]]]:
        text = (user_text or "").strip()
        if not text:
            return None

        rewritten = self.apply_rules(text, rules or [])

        for parser in (self._parse_temperature, self._parse_all_off, self._parse_fan, self._parse_lights):
            actions = parser(rewritten)
            if actions:
                return actions
        return None


DEFAULT_FASTPATH = FastPathParser()


def try_learn_rule(user_text: str) -> Optional[dict[str, str]]:
    return DEFAULT_FASTPATH.try_learn_rule(user_text)


def parse_fastpath(user_text: str, rules: Optional[list[dict[str, str]]] = None) -> Optional[list[dict[str, Any]]]:
    return DEFAULT_FASTPATH.parse(user_text, rules=rules)


def parse(user_text: str, rules: Optional[list[dict[str, str]]] = None) -> Optional[list[dict[str, Any]]]:
    return parse_fastpath(user_text, rules=rules)

