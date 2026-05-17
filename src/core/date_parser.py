"""Natural-language date/time parser for schedule features."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional


class DateParser:
    """Parse date/time expressions from Chinese text."""

    def __init__(self) -> None:
        self.now = datetime.now()
        self.today = self.now.date()

    def parse(self, text: str) -> Optional[dict]:
        """Parse datetime intent from text.

        Returns partial fields when only time/recurrence is present.
        """
        if not text:
            return None

        text = text.strip()
        result: dict = {}

        recurrence = self._parse_recurrence(text)
        if recurrence:
            result.update(recurrence)

        time_part = self._parse_time(text)
        if time_part:
            result.update(time_part)
        elif not recurrence:
            return None

        if not recurrence:
            date_part = self._parse_date(text)
            if date_part:
                result.update(date_part)

        return result or None

    def _parse_recurrence(self, text: str) -> Optional[dict]:
        if "每天" in text or "每日" in text:
            return {"recurrence": "daily"}

        weekly = re.search(r"每週([一二三四五六日])", text)
        if weekly:
            return {"recurrence": "weekly", "weekday": self._day_name_to_weekday(weekly.group(1))}

        if "每月" in text:
            day_match = re.search(r"每月(\d{1,2})(?:號)?", text)
            if day_match:
                day = int(day_match.group(1))
                if 1 <= day <= 31:
                    return {"recurrence": "monthly", "day": day}

        return None

    def _parse_date(self, text: str) -> Optional[dict]:
        if "今天" in text:
            d = self.today
            return {"year": d.year, "month": d.month, "day": d.day, "recurrence": "once"}

        if "明天" in text:
            d = self.today + timedelta(days=1)
            return {"year": d.year, "month": d.month, "day": d.day, "recurrence": "once"}

        if "後天" in text:
            d = self.today + timedelta(days=2)
            return {"year": d.year, "month": d.month, "day": d.day, "recurrence": "once"}

        date_patterns = [
            r"(\d{1,2})月(\d{1,2})(?:號|日)?",
            r"(\d{1,2})[/\-](\d{1,2})",
        ]

        month_map = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "十一": 11,
            "十二": 12,
        }

        for cn_month, num_month in month_map.items():
            if f"{cn_month}月" in text:
                m = re.search(rf"{cn_month}月(\d{{1,2}})(?:號|日)?", text)
                if m:
                    day = int(m.group(1))
                    if 1 <= day <= 31:
                        return {
                            "year": self.now.year,
                            "month": num_month,
                            "day": day,
                            "recurrence": "once",
                        }

        for pattern in date_patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            month = int(m.group(1))
            day = int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return {
                    "year": self.now.year,
                    "month": month,
                    "day": day,
                    "recurrence": "once",
                }

        next_week = re.search(r"下週([一二三四五六日])", text)
        if next_week:
            weekday = self._day_name_to_weekday(next_week.group(1))
            days_ahead = weekday - self.now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target = self.today + timedelta(days=days_ahead)
            return {
                "year": target.year,
                "month": target.month,
                "day": target.day,
                "recurrence": "once",
            }

        return None

    def _parse_time(self, text: str) -> Optional[dict]:
        patterns = [
            r"(\d{1,2}):(\d{2}):(\d{2})",
            r"(\d{1,2}):(\d{2})",
            r"(\d{1,2})點(\d{2})分(\d{2})秒",
            r"(\d{1,2})點(\d{2})分",
            r"(\d{1,2})點",
        ]

        for pattern in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            groups = m.groups()
            hour = int(groups[0])
            minute = int(groups[1]) if len(groups) > 1 else 0
            second = int(groups[2]) if len(groups) > 2 else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                return {"hour": hour, "minute": minute, "second": second}
        return None

    def _day_name_to_weekday(self, day_name: str) -> int:
        day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
        return day_map.get(day_name, 0)


def parse_date(text: str) -> Optional[dict]:
    """Convenience wrapper."""
    return DateParser().parse(text)
