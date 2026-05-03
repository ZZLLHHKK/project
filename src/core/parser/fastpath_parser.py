from __future__ import annotations

import math
import re
from typing import Any, Optional

import src.utils.config as config

LEARN_PATTERNS = [
    # 中文句型
    re.compile(r"^\s*當我說\s*(.+?)\s*(?:的時候|時|時候)?\s*[，,]?\s*代表\s*(.+?)\s*$"),
    re.compile(r"^\s*(?:以後|之後)\s*我說\s*(.+?)\s*(?:就是|就|代表)\s*(.+?)\s*$"),
    re.compile(r"^\s*我說\s*(.+?)\s*(?:的)?意思是\s*(.+?)\s*$"),
    re.compile(r"^\s*(.+?)\s*代表\s*(.+?)\s*$"),
    re.compile(r"^\s*如果我說\s*(.+?)\s*[，,]?\s*(?:請|就)\s*(.+?)\s*$"),
    # 英文句型
    re.compile(r"^\s*when(?:ever)?\s+I\s+say\s+[\"']?(.+?)[\"']?\s*,?\s*(?:it\s+)?means?\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*if\s+I\s+say\s+[\"']?(.+?)[\"']?\s*,?\s*(?:please\s+|it\s+means?\s+)(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*from\s+now\s+on\s+[\"']?(.+?)[\"']?\s+(?:means?|stands?\s+for)\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*[\"']?(.+?)[\"']?\s+stands?\s+for\s+[\"']?(.+?)[\"']?\s*$", re.IGNORECASE),
]

LEARN_GROUP_1 = ("當我說", "以後我說", "之後我說", "如果我說",
                  "when I say", "whenever I say", "if I say", "from now on")
LEARN_GROUP_2 = ("代表", "意思是", "等於", "就是", "就",
                  "means", "stands for")

TEMP_KEYWORDS = (
    "溫度",
    "溫控",
    "冷氣",
    "空調",
    "度",
    "℃",
    "調到",
    "設定",
    "temperature",
    "degrees",
    "ac",
    "air conditioner",
    "set temp",
    "set temperature",
    "thermostat",
)
NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:度|°|c|℃)?", re.IGNORECASE)
_TEMP_WITH_UNIT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:度|°|℃)", re.IGNORECASE)
_TIME_NUM_RE = re.compile(r"\d+\s*(?:點|時|分|秒)")
_QUESTION_TAIL_RE = re.compile(r"[嗎？?]\s*$")
_QUESTION_WORDS = ("是否", "有沒有", "對嗎", "是嗎", "嗎", "how many", "what is", "what's")
# 相對時間句（如「1分鐘之後」「30秒後」）交給 Gemini 處理成排程
_RELATIVE_TIME_RE = re.compile(
    r"(?:"
    r"\d+\s*(?:分鐘|秒鐘|秒|小時|分)\s*(?:後|之後)"
    r"|in\s+\d+\s*(?:minutes?|seconds?|hours?|mins?|secs?|hrs?)"
    r"|\d+\s*(?:minutes?|seconds?|hours?|mins?|secs?|hrs?)\s*(?:later|from\s+now)"
    r")",
    re.IGNORECASE,
)

KW_ON = ("開", "打開", "開啟", "on", "turn on", "open", "start")
KW_OFF = ("關", "關掉", "關閉", "off", "turn off", "close", "stop")
LOC_MAP = {
    config.LOC_KITCHEN: ("廚房", "kitchen"),
    config.LOC_LIVING: ("客廳", "living", "living room"),
    config.LOC_GUEST: ("客房", "guest", "guest room"),
}


def _action_key(action: dict[str, Any]) -> str:
    t = str(action.get("type", "")).upper()
    if t == "LED":
        return f"LED_{action.get('location', '').upper()}"
    return t


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _clamp_temperature(value: float) -> int:
    rounded = int(math.floor(value + 0.5))
    return int(max(config.MIN_TEMP, min(config.MAX_TEMP, rounded)))


class FastPathParser:
    """Rule-based parser for explicit commands and user-taught aliases."""

    def _extract_rule_by_groups(self, text: str) -> Optional[dict[str, str]]:
        first_match: Optional[tuple[int, str]] = None
        for marker in LEARN_GROUP_1:
            idx = text.find(marker)
            if idx >= 0 and (first_match is None or idx < first_match[0]):
                first_match = (idx, marker)

        if first_match is None:
            return None

        start = first_match[0] + len(first_match[1])
        tail = text[start:]

        second_match: Optional[tuple[int, str]] = None
        for marker in LEARN_GROUP_2:
            idx = tail.find(marker)
            if idx >= 0 and (second_match is None or idx < second_match[0]):
                second_match = (idx, marker)

        if second_match is None:
            return None

        split_idx, split_marker = second_match
        trigger = tail[:split_idx].strip().strip("，,：:。;； ")
        trigger = re.sub(r"(?:的時候|時候|時)$", "", trigger).strip()

        meaning = tail[split_idx + len(split_marker):].strip().strip("，,：:。;； ")
        meaning = re.sub(r"^(?:請|就)\s*", "", meaning).strip()

        trigger = trigger.strip("「」\"'")
        meaning = meaning.strip("「」\"'")

        if not trigger or not meaning:
            return None
        return {"trigger": trigger, "meaning": meaning}

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
        return self._extract_rule_by_groups(text)

    def apply_rules(self, user_text: str, rules: list[dict[str, str]]) -> str:
        text = user_text or ""
        normalized_rules = sorted(
            rules,
            key=lambda item: len(str(item.get("trigger", "")).strip()),
            reverse=True,
        )
        for rule in normalized_rules:
            trigger = str(rule.get("trigger", "")).strip()
            meaning = str(rule.get("meaning", "")).strip()
            if trigger and meaning:
                if re.fullmatch(r"[\w\s\-]+", trigger, flags=re.UNICODE):
                    pattern = re.compile(rf"(?<!\w){re.escape(trigger)}(?!\w)", flags=re.UNICODE)
                    text = pattern.sub(meaning, text)
                else:
                    text = text.replace(trigger, meaning)
        return text

    def _parse_temperature(self, text: str) -> Optional[list[dict[str, Any]]]:
        lowered = text.lower()
        if not any(keyword in lowered for keyword in TEMP_KEYWORDS):
            return None

        for raw in _TEMP_WITH_UNIT_RE.findall(text):
            try:
                value = float(raw)
            except Exception:
                continue
            if config.MIN_TEMP <= value <= config.MAX_TEMP:
                return [{"type": "SET_TEMP", "value": _clamp_temperature(value)}]
            if 0 <= value <= 60:
                return None  # out of valid range — let Gemini explain

        clean = _TIME_NUM_RE.sub("", text)
        for raw in NUM_RE.findall(clean):
            try:
                value = float(raw)
            except Exception:
                continue
            if config.MIN_TEMP <= value <= config.MAX_TEMP:
                return [{"type": "SET_TEMP", "value": _clamp_temperature(value)}]
            if 15 <= value <= 45:
                return None  # out of valid range — let Gemini explain
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
        # 含有特定設備詞時交給各自的 parser，避免「全部關燈」連風扇也關
        has_light = "燈" in text or "light" in lowered or "lights" in lowered
        has_fan = "風扇" in text or "fan" in lowered
        if has_light or has_fan:
            return None
        return [
            {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
            {"type": "LED", "location": config.LOC_LIVING, "state": "off"},
            {"type": "LED", "location": config.LOC_GUEST, "state": "off"},
            {"type": "FAN", "state": "off"},
        ]

    def _parse_lights(self, text: str) -> Optional[list[dict[str, Any]]]:
        lowered = text.lower()
        has_light_word = "燈" in text or "light" in lowered or "lights" in lowered or "lamp" in lowered

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

        # 疑問句不應被當成指令執行
        if _QUESTION_TAIL_RE.search(rewritten) or any(w in rewritten.lower() for w in _QUESTION_WORDS):
            return None

        # 相對時間句（「1分鐘後」「30秒之後」）交給 Gemini 排程處理
        if _RELATIVE_TIME_RE.search(rewritten):
            return None

        # 「全部關掉」類指令優先，避免與其他 parser 疊加產生重複動作
        all_off = self._parse_all_off(rewritten)
        if all_off:
            return all_off

        # 收集所有 parser 結果，支援多設備複合指令（如「開風扇並設溫度28度」）
        combined: list[dict[str, Any]] = []
        seen: set[str] = set()
        for parser in (self._parse_temperature, self._parse_fan, self._parse_lights):
            actions = parser(rewritten)
            if not actions:
                continue
            for action in actions:
                key = _action_key(action)
                if key not in seen:
                    combined.append(action)
                    seen.add(key)

        return combined if combined else None


DEFAULT_FASTPATH = FastPathParser()


def try_learn_rule(user_text: str) -> Optional[dict[str, str]]:
    return DEFAULT_FASTPATH.try_learn_rule(user_text)


def parse_fastpath(user_text: str, rules: Optional[list[dict[str, str]]] = None) -> Optional[list[dict[str, Any]]]:
    return DEFAULT_FASTPATH.parse(user_text, rules=rules)


def parse(user_text: str, rules: Optional[list[dict[str, str]]] = None) -> Optional[list[dict[str, Any]]]:
    return parse_fastpath(user_text, rules=rules)

