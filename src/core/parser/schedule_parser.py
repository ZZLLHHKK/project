from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from src.core.date_parser import DateParser
from src.core.parser.fastpath_parser import _normalize_number_words

_PERIOD_AM = ("上午", "早上", "早晨", "凌晨")
_PERIOD_PM = ("下午", "傍晚")
_PERIOD_NIGHT = ("晚上", "夜晚", "深夜", "夜間")
_PERIOD_NOON = ("中午", "正午")
_PERIOD_AM_EN = ("am", "a.m.", "morning")
_PERIOD_PM_EN = ("afternoon", "pm", "p.m.")
_PERIOD_NIGHT_EN = ("evening", "night", "tonight")
_PERIOD_NOON_EN = ("noon", "midday")

_SCHEDULE_SIGNALS = (
    "每天",
    "每日",
    "定時",
    "設定排程",
    "新增排程",
    "幫我",
    "幫忙",
    "記得",
    "到時候",
    "明天",
    "後天",
    "大後天",
    "every day",
    "daily",
    "schedule",
    "remind me",
    "set a reminder",
    "tomorrow",
    "day after",
)

_MANAGE_MAP: dict[str, tuple[str, ...]] = {
    "list": (
        "查看排程",
        "顯示排程",
        "排程列表",
        "有哪些排程",
        "目前排程",
        "我的排程",
        "查看行程",
        "顯示行程",
        "行程列表",
        "有哪些行程",
        "我的行程",
        "所有排程",
        "列出排程",
        "check the schedule",
        "check schedule",
        "list my schedules",
        "list schedules",
        "list schedule",
        "show schedule",
        "show schedules",
        "my schedules",
        "view schedule",
        "view schedules",
        "all schedules",
        "schedule list",
    ),
    "delete": ("刪除排程", "移除排程", "取消排程", "刪除行程", "移除行程", "取消行程", "delete schedule", "remove schedule", "cancel schedule"),
    "enable": ("啟用排程", "啟用行程", "enable schedule", "activate schedule"),
    "disable": (
        "停用排程",
        "關閉排程",
        "暫停排程",
        "停用行程",
        "關閉行程",
        "暫停行程",
        "disable schedule",
        "pause schedule",
        "deactivate schedule",
    ),
}

_DATE_QUERY_SIGNALS = ("查詢", "查看", "有哪些", "有什麼", "schedules for", "schedule for", "what's on")
_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})(?:號|日)?")

_ID_RE = re.compile(r"\b([a-f0-9]{8})\b")
_HHMM_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_HHMM_AMPM_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE)
_AMPM_RE = re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE)
_CHINESE_HOUR_RE = re.compile(r"(\d{1,2})\s*點")
_CHINESE_MIN_RE = re.compile(r"\d{1,2}\s*點\s*(\d{1,2})\s*分")
_CHINESE_HALF_RE = re.compile(r"\d{1,2}\s*點\s*半")


def _detect_period(text: str) -> str:
    lowered = text.lower()
    for w in _PERIOD_NOON + _PERIOD_NOON_EN:
        if w in text or w in lowered:
            return "noon"
    for w in _PERIOD_NIGHT + _PERIOD_NIGHT_EN:
        if w in text or w in lowered:
            return "night"
    for w in _PERIOD_PM + _PERIOD_PM_EN:
        if w in text or w in lowered:
            return "pm"
    for w in _PERIOD_AM + _PERIOD_AM_EN:
        if w in text or w in lowered:
            return "am"
    return ""


def _apply_ampm(hour: int, period: str) -> int:
    if period in ("pm", "night"):
        return hour + 12 if hour != 12 else hour
    if period == "am":
        return 0 if hour == 12 else hour
    if period == "noon":
        return 12
    return hour


def parse_time(text: str) -> Optional[tuple[int, int]]:
    # HH:MM + AM/PM (最優先，避免只取 HH:MM 忽略 PM)
    m = _HHMM_AMPM_RE.search(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        period = "pm" if m.group(3).lower().replace(".", "") in ("pm", "p") else "am"
        h = _apply_ampm(h, period)
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi

    # 純 HH:MM（24 小時制）
    m = _HHMM_RE.search(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi

    # 英文 "10 PM" / "8 AM" 格式
    m = _AMPM_RE.search(text)
    if m:
        h = int(m.group(1))
        period = "pm" if m.group(2).lower().replace(".", "") in ("pm", "p") else "am"
        h = _apply_ampm(h, period)
        if 0 <= h <= 23:
            return h, 0

    # 中文 X點 格式
    hour_m = _CHINESE_HOUR_RE.search(text)
    if not hour_m:
        return None

    hour = int(hour_m.group(1))
    minute = 0
    if _CHINESE_HALF_RE.search(text):
        minute = 30
    else:
        min_m = _CHINESE_MIN_RE.search(text)
        if min_m:
            minute = int(min_m.group(1))

    period = _detect_period(text)
    if period:
        hour = _apply_ampm(hour, period)
    elif hour < 13:
        return None

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def has_time_reference(text: str) -> bool:
    return bool(_HHMM_RE.search(text) or _CHINESE_HOUR_RE.search(text) or _AMPM_RE.search(text))


def has_period_only_no_hour(text: str) -> bool:
    """True when text contains period marker (morning/evening) but no explicit hour."""
    period = _detect_period(text)
    if not period:
        return False
    return not has_time_reference(text)


def _make_name(hour: int, minute: int, actions: list[dict[str, Any]], lang: str = "zh") -> str:
    if lang == "en":
        loc_label = {"LIVING": "living", "KITCHEN": "kitchen", "GUEST": "guest"}
        parts: list[str] = []
        for a in actions:
            t = str(a.get("type", "")).upper()
            if t == "FAN":
                parts.append("fan " + ("on" if a.get("state") == "on" else "off"))
            elif t == "LED":
                loc = loc_label.get(str(a.get("location", "")).upper(), "light")
                parts.append(f"{loc} light " + ("on" if a.get("state") == "on" else "off"))
            elif t == "SET_TEMP":
                parts.append(f"temp {a.get('value')}°C")
        label = ", ".join(parts) if parts else "schedule"
    else:
        loc_label_zh = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}
        parts = []
        for a in actions:
            t = str(a.get("type", "")).upper()
            if t == "FAN":
                parts.append("風扇" + ("開" if a.get("state") == "on" else "關"))
            elif t == "LED":
                loc = loc_label_zh.get(str(a.get("location", "")).upper(), "燈")
                parts.append(loc + "燈" + ("開" if a.get("state") == "on" else "關"))
            elif t == "SET_TEMP":
                parts.append(f"溫度設定 {a.get('value')}°C")
        label = "、".join(parts) if parts else "排程"
    return f"{hour:02d}:{minute:02d} {label}"


class ScheduleFastPathParser:
    """Fastpath parser for schedule add/manage commands."""

    def parse_add(self, text: str, lang: str = "zh") -> Optional[dict[str, Any]]:
        text = _normalize_number_words(text)
        # 只要有明確時間就視為 schedule add，不需 schedule signal
        if not has_time_reference(text):
            return None

        time_result = parse_time(text)
        if time_result is None:
            return None

        hour, minute = time_result

        from .fastpath_parser import FastPathParser

        actions = FastPathParser().parse(text)
        if not actions:
            return None

        dp = DateParser()
        parsed = dp.parse(text) or {}

        extra: dict[str, Any] = {}
        recurrence = str(parsed.get("recurrence") or "")
        if recurrence:
            extra["recurrence"] = recurrence
        else:
            extra["recurrence"] = "daily"

        for key in ("year", "month", "day", "weekday"):
            if key in parsed:
                extra[key] = parsed[key]

        name = _make_name(hour, minute, actions, lang=lang)
        return {"hour": hour, "minute": minute, "actions": actions, "name": name, **extra}

    def parse_list(self, text: str) -> Optional[dict[str, Any]]:
        lowered = text.lower().strip()
        # 支援中英文查詢排程與常見 schedule list 指令
        keywords = [
            "查詢排程", "列出排程", "有哪些排程", "排程列表",
            "list schedule", "list schedules", "show schedule", "show schedules",
            "schedules", "schedule list", "my schedules", "all schedules"
        ]
        # 完全符合或包含關鍵字皆可
        if any(kw == lowered or kw in lowered for kw in keywords):
            return {"op": "list"}
        return None

    def parse_delete(self, text: str) -> Optional[dict[str, Any]]:
        text = _normalize_number_words(text)
        lowered = text.lower()
        # ID 刪除（8 碼英數）
        m = re.search(r"刪除([a-z0-9]{8})", lowered)
        if m:
            return {"op": "delete", "id": m.group(1)}
        m = re.search(r"delete\s*([a-z0-9]{8})", lowered)
        if m:
            return {"op": "delete", "id": m.group(1)}
        # 時間刪除（如「刪除晚上10點的排程」）
        delete_kw = ("刪除", "移除", "取消", "delete", "remove", "cancel")
        if any(kw in lowered for kw in delete_kw) and has_time_reference(text):
            time_result = parse_time(text)
            if time_result is not None:
                return {"op": "delete_by_time", "hour": time_result[0], "minute": time_result[1]}
        return None

    def parse_toggle(self, text: str) -> Optional[dict[str, Any]]:
        lowered = text.lower()
        # 支援中英文啟用/停用排程，id 可為 8 碼英數
        m = re.search(r"啟用([a-z0-9]{8})", lowered)
        if m:
            return {"op": "enable", "id": m.group(1)}
        m = re.search(r"停用([a-z0-9]{8})", lowered)
        if m:
            return {"op": "disable", "id": m.group(1)}
        m = re.search(r"enable\s*([a-z0-9]{8})", lowered)
        if m:
            return {"op": "enable", "id": m.group(1)}
        m = re.search(r"disable\s*([a-z0-9]{8})", lowered)
        if m:
            return {"op": "disable", "id": m.group(1)}
        return None

    def parse_manage(self, text: str) -> Optional[dict[str, Any]]:
        text = _normalize_number_words(text)
        lowered = text.lower()
        if any(kw in lowered for kw in _DATE_QUERY_SIGNALS):
            date_m = _DATE_RE.search(text)
            if date_m:
                return {"op": "list_date", "month": int(date_m.group(1)), "day": int(date_m.group(2)), "id": None}
            if "今天" in text or "today" in lowered:
                now = datetime.now()
                return {"op": "list_date", "month": now.month, "day": now.day, "id": None}

        delete_keywords = ("刪除", "移除", "取消", "delete", "remove", "cancel")
        if any(kw in lowered for kw in delete_keywords):
            id_match = _ID_RE.search(lowered)
            if not id_match and has_time_reference(text):
                time_result = parse_time(text)
                if time_result is not None:
                    return {"op": "delete_by_time", "hour": time_result[0], "minute": time_result[1], "id": None}

        for op, keywords in _MANAGE_MAP.items():
            if any(kw in lowered for kw in keywords):
                id_match = _ID_RE.search(lowered)
                return {"op": op, "id": id_match.group(1) if id_match else None}
        return None
