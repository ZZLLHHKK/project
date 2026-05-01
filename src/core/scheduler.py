from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional



class ScheduleManager:
    """Manage time-based automation rules with thread safety."""

    MAX_SCHEDULES = 5

    def get_due_schedules(self, current_time):
        def _to_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        with self._lock:
            rules = self._read()
            due = []
            today = current_time.strftime('%Y-%m-%d')
            current_slot = current_time.strftime('%Y-%m-%d %H:%M')
            for rule in rules:
                if not rule.get('enabled', True):
                    continue
                hour, minute = rule.get('hour'), rule.get('minute')
                if hour == current_time.hour and minute == current_time.minute:
                    year = _to_int(rule.get('year'))
                    month = _to_int(rule.get('month'))
                    day = _to_int(rule.get('day'))
                    if year and year != current_time.year:
                        continue
                    if month and month != current_time.month:
                        continue
                    if day and day != current_time.day:
                        continue

                    last_executed = str(rule.get('last_executed') or '')
                    if last_executed == today:
                        continue

                    last = str(rule.get('last_triggered') or '')
                    if not last or last[:16] != current_slot:
                        due.append(rule)
            return due

    def mark_schedule_executed(self, schedule_id, exec_time):
        with self._lock:
            rules = self._read()
            for rule in rules:
                if rule.get('id') == schedule_id:
                    rule['last_executed'] = exec_time.strftime('%Y-%m-%d')
                    rule['last_triggered'] = exec_time.strftime('%Y-%m-%d %H:%M:%S')
            self._write(rules)

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self._path = project_root / "data" / "memory" / "schedules.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not hasattr(self, "_lock"):
            self._lock = threading.RLock()
        try:
            self.max_schedules = max(1, int(os.environ.get("MAX_SCHEDULES", str(self.MAX_SCHEDULES))))
        except Exception:
            self.max_schedules = self.MAX_SCHEDULES
        self._user_overrides = {}
        if not self._path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with self._lock:
            try:
                raw = self._path.read_text(encoding="utf-8")
                data = json.loads(raw) if raw.strip() else []
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def _write(self, rules: list[dict[str, Any]]) -> None:
        with self._lock:
            self._path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(
        self,
        hour: int,
        minute: int,
        actions: list[dict[str, Any]],
        name: str = "",
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
        second: int = 0,
        recurrence: str = "once",
        weekday: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        rules = self._read()
        if len(rules) >= self.max_schedules:
            return None

        if self._has_conflict(rules, year, month, day, hour, minute, actions):
            return None

        rule: dict[str, Any] = {
            "id": uuid.uuid4().hex[:8],
            "name": name or self._generate_name(hour, minute, recurrence),
            "hour": hour,
            "minute": minute,
            "second": second,
            "actions": actions,
            "enabled": True,
            "recurrence": recurrence,
            "last_executed": None,
            "last_triggered": None,
            "last_result": None,
        }

        if year is not None:
            rule["year"] = year
        if month is not None:
            rule["month"] = month
        if day is not None:
            rule["day"] = day
        if weekday is not None:
            rule["weekday"] = weekday

        rules.append(rule)
        self._write(rules)
        return rule

    def _has_conflict(
        self,
        rules: list[dict[str, Any]],
        year: Optional[int],
        month: Optional[int],
        day: Optional[int],
        hour: int,
        minute: int,
        new_actions: list[dict[str, Any]],
    ) -> bool:
        # 用 _action_key 區分 LED_KITCHEN / LED_LIVING / LED_GUEST，避免不同房間被誤判衝突
        new_keys = {self._action_key(action) for action in new_actions}

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            if rule.get("hour") != hour or rule.get("minute") != minute:
                continue
            if year is not None and rule.get("year") != year:
                continue
            if month is not None and rule.get("month") != month:
                continue
            if day is not None and rule.get("day") != day:
                continue

            existing_keys = {self._action_key(action) for action in rule.get("actions", [])}
            if new_keys & existing_keys:
                return True

        return False

    def _generate_name(self, hour: int, minute: int, recurrence: str) -> str:
        time_str = f"{hour:02d}:{minute:02d}"
        if recurrence == "daily":
            return f"每天 {time_str}"
        if recurrence == "weekly":
            return f"每週 {time_str}"
        if recurrence == "monthly":
            return f"每月 {time_str}"
        return time_str

    def _action_key(self, action: dict[str, Any]) -> str:
        action_type = str(action.get("type", "")).upper()
        if action_type == "LED":
            location = str(action.get("location", "")).upper()
            return f"LED_{location}"
        return action_type

    def block_devices(self, actions: list[dict[str, Any]], duration_seconds: int = 60) -> None:
        until = time.time() + duration_seconds
        with self._lock:
            for action in actions:
                self._user_overrides[self._action_key(action)] = until

    def _is_device_blocked(self, action: dict[str, Any]) -> bool:
        key = self._action_key(action)
        with self._lock:
            until = self._user_overrides.get(key)
            if until is None:
                return False
            if time.time() >= until:
                del self._user_overrides[key]
                return False
            return True

    def list_all(self) -> list[dict[str, Any]]:
        return self._read()

    def list_by_date(self, month: int, day: int, year: Optional[int] = None) -> list[dict[str, Any]]:
        rules = self._read()
        result: list[dict[str, Any]] = []
        for rule in rules:
            recurrence = rule.get("recurrence", "once")

            if recurrence == "daily":
                result.append(rule)
                continue

            if recurrence == "monthly":
                if rule.get("day") == day:
                    result.append(rule)
                continue

            if recurrence == "once":
                if rule.get("month") == month and rule.get("day") == day:
                    if year is None or rule.get("year") == year:
                        result.append(rule)
                continue

            if rule.get("month") is None and rule.get("day") is None:
                result.append(rule)

        return result

    def delete(self, rule_id: str) -> bool:
        with self._lock:
            rules = self._read()
            new_rules = [r for r in rules if r.get("id") != rule_id]
            if len(new_rules) == len(rules):
                return False
            self._write(new_rules)
            return True

    def delete_by_time(self, hour: int, minute: int) -> list[str]:
        """Delete all rules matching exact HH:MM and return removed IDs."""
        with self._lock:
            rules = self._read()
            matched = [r for r in rules if r.get("hour") == hour and r.get("minute") == minute]
            if not matched:
                return []
            new_rules = [r for r in rules if not (r.get("hour") == hour and r.get("minute") == minute)]
            self._write(new_rules)
            return [str(r.get("id")) for r in matched if r.get("id")]

    def toggle(self, rule_id: str) -> Optional[bool]:
        with self._lock:
            rules = self._read()
            for rule in rules:
                if rule.get("id") == rule_id:
                    rule["enabled"] = not rule.get("enabled", True)
                    self._write(rules)
                    return bool(rule["enabled"])
            return None

    def set_enabled(self, rule_id: str, enabled: bool) -> Optional[bool]:
        """Set enabled state explicitly; returns new state or None if not found."""
        with self._lock:
            rules = self._read()
            for rule in rules:
                if rule.get("id") == rule_id:
                    rule["enabled"] = bool(enabled)
                    self._write(rules)
                    return bool(rule["enabled"])
            return None

    def tick(self, device_controller: Any) -> list[dict[str, Any]]:
        now = time.localtime()
        current_slot = f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d} {now.tm_hour:02d}:{now.tm_min:02d}"

        with self._lock:
            rules = self._read()
            triggered: list[dict[str, Any]] = []
            changed = False
            rules_to_delete: list[int] = []

            for idx, rule in enumerate(rules):
                if not rule.get("enabled", True):
                    continue

                if rule.get("hour") != now.tm_hour or rule.get("minute") != now.tm_min:
                    continue

                recurrence = rule.get("recurrence", "once")

                if recurrence == "weekly" and rule.get("weekday") is not None:
                    if int(rule.get("weekday")) != now.tm_wday:
                        continue
                elif recurrence == "monthly" and rule.get("day") is not None:
                    if int(rule.get("day")) != now.tm_mday:
                        continue
                else:
                    if rule.get("year") and rule.get("year") != now.tm_year:
                        continue
                    if rule.get("month") and rule.get("month") != now.tm_mon:
                        continue
                    if rule.get("day") and rule.get("day") != now.tm_mday:
                        continue

                if rule.get("last_triggered") == current_slot:
                    continue

                actions = [a for a in rule.get("actions", []) if not self._is_device_blocked(a)]
                if not actions:
                    continue

                try:
                    if device_controller is not None:
                        results = device_controller.execute_actions(actions)
                        success = all(r.get("success", False) for r in results)
                    else:
                        success = True
                    result_text = "成功" if success else "部分失敗"
                except Exception as exc:
                    success = False
                    result_text = str(exc)

                rule["last_triggered"] = current_slot
                rule["last_result"] = result_text
                changed = True
                triggered.append({"rule": dict(rule), "success": success, "result": result_text})

                if rule.get("recurrence") == "once":
                    rules_to_delete.append(idx)

            for idx in sorted(rules_to_delete, reverse=True):
                del rules[idx]
                changed = True

            if changed:
                self._write(rules)

            return triggered

    def now_string(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
