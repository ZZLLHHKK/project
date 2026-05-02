from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from src.core.date_parser import DateParser

_PERIOD_AM = ("上午", "早上", "早晨", "凌晨")
_PERIOD_PM = ("下午", "傍晚")
_PERIOD_NIGHT = ("晚上", "夜晚", "深夜", "夜間")
_PERIOD_NOON = ("中午", "正午")

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
_CHINESE_HOUR_RE = re.compile(r"(\d{1,2})\s*點")
_CHINESE_MIN_RE = re.compile(r"\d{1,2}\s*點\s*(\d{1,2})\s*分")
_CHINESE_HALF_RE = re.compile(r"\d{1,2}\s*點\s*半")


def _detect_period(text: str) -> str:
    for w in _PERIOD_NOON:
        if w in text:
            return "noon"
    for w in _PERIOD_NIGHT:
        if w in text:
            return "night"
    for w in _PERIOD_PM:
        if w in text:
            return "pm"
    for w in _PERIOD_AM:
        if w in text:
            return "am"
    return ""


def parse_time(text: str) -> Optional[tuple[int, int]]:
    m = _HHMM_RE.search(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi

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

    if period == "noon":
        hour = 12
    elif period in ("pm", "night"):
        if hour != 12:
            hour += 12
    elif period == "am":
        if hour == 12:
            hour = 0
    else:
        if hour < 13:
            return None

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def has_time_reference(text: str) -> bool:
    return bool(_HHMM_RE.search(text) or _CHINESE_HOUR_RE.search(text))


def has_period_only_no_hour(text: str) -> bool:
    """True when text contains period marker (morning/evening) but no explicit hour."""
    period = _detect_period(text)
    if not period:
        return False
    return not has_time_reference(text)


def _make_name(hour: int, minute: int, actions: list[dict[str, Any]]) -> str:
    loc_label = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}
    parts: list[str] = []
    for a in actions:
        t = str(a.get("type", "")).upper()
        if t == "FAN":
            parts.append("風扇" + ("開" if a.get("state") == "on" else "關"))
        elif t == "LED":
            loc = loc_label.get(str(a.get("location", "")).upper(), "燈")
            parts.append(loc + "燈" + ("開" if a.get("state") == "on" else "關"))
        elif t == "SET_TEMP":
            parts.append(f"溫度設定 {a.get('value')}°C")
    label = "、".join(parts) if parts else "排程"
    return f"{hour:02d}:{minute:02d} {label}"


class ScheduleFastPathParser:
    """Fastpath parser for schedule add/manage commands."""

    def parse_add(self, text: str) -> Optional[dict[str, Any]]:
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

        name = _make_name(hour, minute, actions)
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
