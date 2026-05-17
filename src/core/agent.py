from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Optional

from .memory_agent import MemoryAgent
from .parser.fastpath_parser import FastPathParser
from .parser.gemini_parser import GeminiParser
from .parser.schedule_parser import ScheduleFastPathParser
from .scheduler import ScheduleManager
from .state_manager import StateManager
from src.utils.lang_detect import detect_lang

FRIENDLY_ERROR = "抱歉，我現在無法處理，請稍後再試。"
FRIENDLY_ERROR_EN = "Sorry, I'm unable to process that right now. Please try again later."

_COMMON_STT_REWRITES = {
    "行程": "排程",
    "定時": "排程",
    "開登": "開燈",
    "關登": "關燈",
    "風善": "風扇",
    "溫渡": "溫度",
    "萬上": "晚上",
}


def _t(lang: str, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _normalize_input(text: str) -> str:
    normalized = text
    for wrong, corrected in _COMMON_STT_REWRITES.items():
        normalized = normalized.replace(wrong, corrected)
    return normalized


def _has_temperature_condition(text: str) -> bool:
    lowered = (text or "").lower()
    if "如果" not in text and "if" not in lowered:
        return False
    if "溫度" not in text and "temperature" not in lowered:
        return False
    return any(token in text for token in ("超過", "高於", "大於", "以上", ">")) or any(
        token in lowered for token in ("over", "above", ">")
    )


_CLARIFY_PERIOD_ZH = ("早上", "上午", "下午", "晚上", "夜晚", "夜間", "中午", "凌晨")
_CLARIFY_PERIOD_EN = ("morning", "afternoon", "evening", "night", "noon", "am", "a.m.", "pm", "p.m.")
_CLARIFY_PAIR_RE = re.compile(
    r"(早上|上午|下午|晚上|夜晚|夜間|中午|凌晨)(\d{1,2})點\s*還是\s*"
    r"(早上|上午|下午|晚上|夜晚|夜間|中午|凌晨)(\d{1,2})點(?P<tail>[^？?以及]*)"
)


def _is_period_only_response(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if re.search(r"\d|:", cleaned) or "點" in cleaned:
        return False
    lowered = cleaned.lower()
    return any(word in cleaned for word in _CLARIFY_PERIOD_ZH) or any(word in lowered for word in _CLARIFY_PERIOD_EN)


def _resolve_period_choice(pending: str, period: str) -> str:
    if not pending:
        return period

    resolved = pending
    for word in _CLARIFY_PERIOD_ZH:
        resolved = resolved.replace(word, period)

    dup_pattern = re.compile(
        rf"{re.escape(period)}\s*(\d{{1,2}}(?:[:點]\d{{1,2}})?)\s*(?:還是|或|或者)\s*{re.escape(period)}\s*\1"
    )
    resolved = dup_pattern.sub(rf"{period}\1", resolved)
    return resolved


def _extract_time_choice_pairs(text: str) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for match in _CLARIFY_PAIR_RE.finditer(text or ""):
        action_hint = (match.group("tail") or "").strip()
        pairs.append(
            {
                "p1": match.group(1),
                "h1": match.group(2),
                "p2": match.group(3),
                "h2": match.group(4),
                "action": action_hint,
            }
        )
    return pairs


def _format_choice_question(pair: dict[str, str]) -> str:
    action = pair.get("action", "").strip()
    return f"請問是{pair['p1']}{pair['h1']}點還是{pair['p2']}{pair['h2']}點{action}呢？"


def _replace_time_with_period(text: str, hour: str, period: str, action_hint: str) -> str:
    if not text:
        return text
    token = f"{hour}點"
    replacement = f"{period}{hour}點"
    if action_hint and "關" in action_hint:
        idx = text.rfind(token)
        if idx >= 0:
            return text[:idx] + replacement + text[idx + len(token):]
    if action_hint and "開" in action_hint:
        idx = text.find(token)
        if idx >= 0:
            return text[:idx] + replacement + text[idx + len(token):]
    return text.replace(token, replacement, 1)


def _contains_device_word(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        token in text or token in lowered
        for token in (
            "燈",
            "風扇",
            "溫度",
            "冷氣",
            "空調",
            "light",
            "fan",
            "temperature",
            "ac",
            "air conditioner",
        )
    )


class ActionExecutionError(RuntimeError):
    """Compatibility placeholder for older call sites."""


class SmartHomeAgent:
    """Main orchestrator: fastpath first, Gemini fallback, then execute and persist."""

    def __init__(
        self,
        memory: Optional[MemoryAgent] = None,
        state: Optional[StateManager] = None,
        fastpath_parser: Optional[FastPathParser] = None,
        gemini_parser: Optional[GeminiParser] = None,
        device_controller: Any = None,
        scheduler: Optional[ScheduleManager] = None,
    ) -> None:
        self.memory = memory or MemoryAgent()
        self.state = state or StateManager()
        self.fastpath = fastpath_parser or FastPathParser()
        self.gemini = gemini_parser or GeminiParser()
        self.device_controller = device_controller
        self.scheduler = scheduler or ScheduleManager()
        self.schedule_parser = ScheduleFastPathParser()

    def _friendly_fastpath_reply(self, actions: list[dict[str, Any]], lang: str = "zh") -> str:
        labels_zh = {"KITCHEN": "廚房", "LIVING": "客廳", "GUEST": "客房"}
        labels_en = {"KITCHEN": "kitchen", "LIVING": "living room", "GUEST": "guest room"}
        parts: list[str] = []
        for action in actions:
            action_type = str(action.get("type", "")).upper()
            is_on = str(action.get("state", "off")).lower() == "on"
            if action_type == "SET_TEMP":
                parts.append(_t(lang, f"溫度已設定為 {action.get('value')} 度", f"temperature set to {action.get('value')}°C"))
            elif action_type == "FAN":
                parts.append(_t(lang, f"風扇已{'開啟' if is_on else '關閉'}", f"fan turned {'on' if is_on else 'off'}"))
            elif action_type == "LED":
                loc_key = str(action.get("location", "")).upper()
                if lang == "en":
                    location = labels_en.get(loc_key, "light")
                    parts.append(f"{location} light turned {'on' if is_on else 'off'}")
                else:
                    location = labels_zh.get(loc_key, "燈")
                    parts.append(f"{location}燈已{'開啟' if is_on else '關閉'}")
            elif action_type == "AC_ON":
                parts.append(_t(lang, "冷氣已開啟", "AC turned on"))
            elif action_type == "AC_OFF":
                parts.append(_t(lang, "冷氣已關閉", "AC turned off"))
        if parts:
            return _t(lang, f"好的，{'，'.join(parts)}。", f"Done, {', '.join(parts)}.")
        return _t(lang, "好的，已為您處理。", "Done, your request has been processed.")

    def _execute_actions(self, actions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Optional[str]]:
        if not actions:
            return [], None
        controller_name = self.device_controller.__class__.__name__ if self.device_controller is not None else "None"
        print(f"[DEVICE CONTROLLER INSTANCE] class={controller_name}")
        if self.device_controller is None:
            executed = [dict(action, success=True) for action in actions]
            return executed, None

        print(f"[AGENT ACTIONS] dispatch_to_device_controller={actions}")
        results = self.device_controller.execute_actions(actions)
        failures = [item for item in results if not item.get("success", False)]
        if failures:
            return results, "device_execution_failed"
        return results, None

    def _format_schedule_recurrence(self, rule: dict[str, Any], lang: str = "zh") -> str:
        recurrence = str(rule.get("recurrence") or "daily").lower()
        if lang == "en":
            if recurrence == "daily":
                return "Every day"
            if recurrence == "weekly":
                return "Weekly"
            if recurrence == "monthly":
                return "Monthly"
            if recurrence == "once":
                year = rule.get("year")
                month = rule.get("month")
                day = rule.get("day")
                if month and day:
                    if year:
                        return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
                    return f"{int(month):02d}/{int(day):02d}"
                return "One-time"
            return "Scheduled"

        if recurrence == "daily":
            return "每天"
        if recurrence == "weekly":
            return "每週"
        if recurrence == "monthly":
            return "每月"
        if recurrence == "once":
            year = rule.get("year")
            month = rule.get("month")
            day = rule.get("day")
            if month and day:
                today = datetime.now().date()
                try:
                    target = datetime(
                        int(year) if year is not None else today.year,
                        int(month),
                        int(day),
                    ).date()
                    if target == today:
                        return "今天"
                    if target == today + timedelta(days=1):
                        return "明天"
                except Exception:
                    pass
                if year:
                    return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
                return f"{int(month):02d}/{int(day):02d}"
            return "單次"
        return "排程"

    def _format_schedule_action_summary(self, rule: dict[str, Any], lang: str = "zh") -> str:
        actions = rule.get("actions")
        if not isinstance(actions, list) or not actions:
            name = str(rule.get("name") or "").strip()
            return name or ("scheduled task" if lang == "en" else "排程")

        zh_loc = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}
        en_loc = {"LIVING": "living room", "KITCHEN": "kitchen", "GUEST": "guest room"}
        parts: list[str] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").upper()
            state_on = str(action.get("state") or "").lower() == "on"
            if action_type == "FAN":
                parts.append("turn fan on" if (lang == "en" and state_on) else "turn fan off" if lang == "en" else "開風扇" if state_on else "關風扇")
            elif action_type == "LED":
                loc_key = str(action.get("location") or "").upper()
                if lang == "en":
                    loc = en_loc.get(loc_key, "light")
                    parts.append(f"turn {loc} light {'on' if state_on else 'off'}")
                else:
                    loc = zh_loc.get(loc_key, "燈")
                    parts.append(f"{'開' if state_on else '關'}{loc}燈")
            elif action_type == "SET_TEMP":
                val = action.get("value")
                parts.append(f"set temperature to {val}°C" if lang == "en" else f"設定溫度 {val} 度")

        if parts:
            return ", ".join(parts) if lang == "en" else "、".join(parts)

        name = str(rule.get("name") or "").strip()
        return name or ("scheduled task" if lang == "en" else "排程")

    def _format_schedule_line(self, idx: int, rule: dict[str, Any], lang: str = "zh") -> str:
        hour = int(rule.get("hour", 0))
        minute = int(rule.get("minute", 0))
        recurrence = self._format_schedule_recurrence(rule, lang)
        action_text = self._format_schedule_action_summary(rule, lang)
        return f"{idx}. {recurrence} {hour:02d}:{minute:02d} {action_text}".strip()

    def _handle_schedule_add(self, parsed: dict[str, Any], original: str, lang: str = "zh") -> dict[str, Any]:
        rule = self.scheduler.add(
            hour=parsed["hour"],
            minute=parsed["minute"],
            actions=parsed["actions"],
            name=parsed["name"],
            year=parsed.get("year"),
            month=parsed.get("month"),
            day=parsed.get("day"),
            recurrence=parsed.get("recurrence", "daily"),
            weekday=parsed.get("weekday"),
        )
        if rule is None:
            reply = _t(
                lang,
                "排程新增失敗，可能已達上限（5條）或與現有排程衝突。",
                "Failed to add schedule. The limit (5) may be reached or a conflict exists.",
            )
        else:
            reply = _t(
                lang,
                f"好的，已設定排程：{parsed['name']}。",
                f"Schedule set: {parsed['name']}.",
            )
        self.memory.add_interaction(original, reply)
        return self._build_result(reply, [], None)

    def _handle_schedule_manage(self, parsed: dict[str, Any], original: str, lang: str = "zh") -> dict[str, Any]:
        op = parsed["op"]
        rule_id = parsed.get("id")

        enabled_label = _t(lang, "啟用", "enabled")
        disabled_label = _t(lang, "停用", "disabled")

        if op == "list":
            rules = self.scheduler.list_all()
            if not rules:
                reply = _t(lang, "目前沒有設定任何排程。", "No schedules set.")
            else:
                lines = [self._format_schedule_line(idx, r, lang) for idx, r in enumerate(rules, start=1)]
                reply = _t(lang, "目前的排程：\n", "Current schedules:\n") + "\n".join(lines)

        elif op == "list_date":
            month = parsed.get("month")
            day = parsed.get("day")
            year = parsed.get("year")
            if month and day:
                rules = self.scheduler.list_by_date(month, day, year)
                if not rules:
                    reply = _t(lang, f"{month}月{day}號沒有設定任何排程。", f"No schedules on {month}/{day}.")
                else:
                    lines = [self._format_schedule_line(idx, r, lang) for idx, r in enumerate(rules, start=1)]
                    reply = _t(lang, f"{month}月{day}號的排程：\n", f"Schedules on {month}/{day}:\n") + "\n".join(lines)
            else:
                reply = _t(lang, "請告訴我要查詢哪一天的排程。", "Please tell me which date to query.")

        elif op == "delete_by_time":
            hour = parsed.get("hour")
            minute = parsed.get("minute", 0)
            if hour is None:
                reply = _t(lang, "請告訴我要刪除哪個時間的排程。", "Please tell me which schedule time to delete.")
            else:
                deleted_ids = self.scheduler.delete_by_time(int(hour), int(minute))
                hhmm = f"{int(hour):02d}:{int(minute):02d}"
                if deleted_ids:
                    reply = _t(lang, f"已刪除 {hhmm} 的排程。", f"Schedules at {hhmm} deleted.")
                else:
                    reply = _t(lang, f"找不到 {hhmm} 的排程。", f"No schedules found at {hhmm}.")

        elif op == "delete":
            if not rule_id:
                reply = _t(lang, "請告訴我要刪除哪個排程的 ID。", "Please tell me the schedule ID to delete.")
            elif self.scheduler.delete(rule_id):
                reply = _t(lang, "已刪除指定排程。", "Selected schedule deleted.")
            else:
                reply = _t(lang, "找不到指定排程。", "Selected schedule not found.")

        elif op in ("enable", "disable"):
            if not rule_id:
                reply = _t(lang, "請告訴我要操作哪個排程的 ID。", "Please tell me the schedule ID.")
            else:
                result = self.scheduler.set_enabled(rule_id, op == "enable")
                if result is None:
                    reply = _t(lang, "找不到指定排程。", "Selected schedule not found.")
                else:
                    reply = _t(
                        lang,
                        f"排程已{'啟用' if result else '停用'}。",
                        f"Schedule {'enabled' if result else 'disabled'}.",
                    )
        else:
            reply = _t(lang, "不確定你想對排程做什麼操作。", "I'm not sure what you want to do with the schedule.")

        self.memory.add_interaction(original, reply)
        return self._build_result(reply, [], None)

    def _process_gemini_schedule_actions(
        self,
        actions: list[dict[str, Any]],
        lang: str = "zh",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        device_actions: list[dict[str, Any]] = []
        sched_executed: list[dict[str, Any]] = []
        sched_reply_parts: list[str] = []

        for action in actions:
            action_type = str(action.get("type", "")).upper()

            if action_type == "SCHEDULE_ADD":
                nested = action.get("actions", [])
                h = int(action.get("hour", 0))
                m = int(action.get("minute", 0))
                name = str(action.get("name", f"{h:02d}:{m:02d} 排程"))
                year = int(action["year"]) if action.get("year") else None
                month = int(action["month"]) if action.get("month") else None
                day = int(action["day"]) if action.get("day") else None
                recurrence = str(action.get("recurrence", "daily"))
                weekday = int(action["weekday"]) if action.get("weekday") is not None else None

                rule = self.scheduler.add(
                    h,
                    m,
                    nested,
                    name,
                    year=year,
                    month=month,
                    day=day,
                    recurrence=recurrence,
                    weekday=weekday,
                )
                if rule:
                    sched_executed.append(dict(action, success=True, id=rule["id"]))
                    sched_reply_parts.append(
                        _t(lang, f"已設定排程：{name}", f"Schedule set: {name}")
                    )
                else:
                    sched_executed.append(dict(action, success=False))
                    sched_reply_parts.append(
                        _t(
                            lang,
                            "排程新增失敗，可能已達上限（5條）或與現有排程衝突。",
                            "Failed to add schedule. The limit (5) may be reached or a conflict exists.",
                        )
                    )

            elif action_type == "SCHEDULE_LIST_DATE":
                month = int(action.get("month", 0))
                day = int(action.get("day", 0))
                year = int(action["year"]) if action.get("year") else None
                if month and day:
                    rules = self.scheduler.list_by_date(month, day, year)
                    if rules:
                        lines = [self._format_schedule_line(idx, r, lang) for idx, r in enumerate(rules, start=1)]
                        sched_reply_parts.append(
                            _t(lang, f"{month}月{day}號的排程：\n" + "\n".join(lines), f"Schedules on {month}/{day}:\n" + "\n".join(lines))
                        )
                    else:
                        sched_reply_parts.append(
                            _t(lang, f"{month}月{day}號沒有設定任何排程。", f"No schedules on {month}/{day}.")
                        )
                else:
                    sched_reply_parts.append(_t(lang, "請告訴我要查詢哪一天的排程。", "Please tell me which date to query."))
                sched_executed.append(dict(action, success=True))

            elif action_type == "SCHEDULE_LIST":
                rules = self.scheduler.list_all()
                if rules:
                    lines = [self._format_schedule_line(idx, r, lang) for idx, r in enumerate(rules, start=1)]
                    sched_reply_parts.append(_t(lang, "排程列表：\n" + "\n".join(lines), "Schedule list:\n" + "\n".join(lines)))
                else:
                    sched_reply_parts.append(_t(lang, "目前沒有設定任何排程。", "No schedules set."))
                sched_executed.append(dict(action, success=True))

            elif action_type == "SCHEDULE_DELETE":
                rule_id = str(action.get("id", ""))
                ok = self.scheduler.delete(rule_id) if rule_id else False
                sched_executed.append(dict(action, success=ok))
                sched_reply_parts.append(
                    _t(
                        lang,
                        "已刪除指定排程。" if ok else "找不到指定排程。",
                        "Selected schedule deleted." if ok else "Selected schedule not found.",
                    )
                )

            elif action_type == "SCHEDULE_TOGGLE":
                rule_id = str(action.get("id", ""))
                result = self.scheduler.toggle(rule_id) if rule_id else None
                ok = result is not None
                sched_executed.append(dict(action, success=ok))
                if ok:
                    sched_reply_parts.append(
                        _t(
                            lang,
                            f"排程已{'啟用' if result else '停用'}。",
                            f"Schedule {'enabled' if result else 'disabled'}.",
                        )
                    )
                else:
                    sched_reply_parts.append(_t(lang, "找不到指定排程。", "Selected schedule not found."))

            elif action_type == "LEARN_RULE":
                trigger = str(action.get("trigger", "")).strip()
                meaning = str(action.get("meaning", "")).strip()
                ok = self.memory.save_rule(trigger, meaning) if trigger and meaning else False
                sched_executed.append(dict(action, success=ok))
                if ok:
                    sched_reply_parts.append(
                        _t(
                            lang,
                            f"好的，我記住了：{trigger} 代表 {meaning}",
                            f"Got it! When you say '{trigger}', it means '{meaning}'.",
                        )
                    )
                else:
                    sched_reply_parts.append(
                        _t(
                            lang,
                            "規則新增失敗，請確認觸發詞與語意是否完整，或是否已存在。",
                            "Failed to add rule. Please ensure trigger and meaning are complete or not duplicated.",
                        )
                    )

            else:
                device_actions.append(action)

        return device_actions, sched_executed, sched_reply_parts

    def _build_result(
        self,
        reply: str,
        actions_executed: list[dict[str, Any]],
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "reply": reply,
            "actions_executed": actions_executed,
            "state": self.state.get_state(),
            "error": error,
        }

    def handle(self, user_input: str, lang: str | None = None) -> dict[str, Any]:
        clean_input = _normalize_input((user_input or "").strip())
        lang = lang if lang in ("zh", "en") else detect_lang(clean_input)
        if not clean_input:
            return self._build_result(_t(lang, "請告訴我你想控制的設備或需求。", "Please tell me what you need."), [], None)

        if self.state.needs_clarification and self.state.clarification_context:
            if _is_period_only_response(clean_input):
                period = clean_input
                question = self.state.clarification_message or ""
                pairs = _extract_time_choice_pairs(question)
                if pairs:
                    target_pair = None
                    for pair in pairs:
                        if period in (pair.get("p1"), pair.get("p2")):
                            target_pair = pair
                            break
                    if target_pair is None:
                        target_pair = pairs[-1]

                    chosen_hour = target_pair["h1"] if period == target_pair.get("p1") else target_pair["h2"]
                    updated = _replace_time_with_period(
                        self.state.clarification_context,
                        chosen_hour,
                        period,
                        target_pair.get("action", ""),
                    )

                    remaining = [p for p in pairs if p is not target_pair]
                    if remaining:
                        follow_up = f"收到，{period}{chosen_hour}點{target_pair.get('action', '')}。"
                        follow_up += _format_choice_question(remaining[0])
                        self.state.needs_clarification = True
                        self.state.clarification_message = follow_up
                        self.state.clarification_context = updated
                        self.memory.add_interaction(clean_input, follow_up)
                        return self._build_result(follow_up, [], None)

                    clean_input = updated
                    self.state.needs_clarification = False
                    self.state.clarification_message = None
                    self.state.clarification_context = None

                    from src.core.parser.schedule_parser import find_ambiguous_hours

                    remaining_hours = find_ambiguous_hours(clean_input)
                    if remaining_hours and _contains_device_word(clean_input):
                        next_item = remaining_hours[0]
                        next_hour = int(next_item.get("hour", 0))
                        next_tail = (next_item.get("tail", "") or "").strip()
                        next_question = f"請問是早上{next_hour}點還是晚上{next_hour}點{next_tail}呢？"
                        self.state.needs_clarification = True
                        self.state.clarification_message = next_question
                        self.state.clarification_context = clean_input
                        self.memory.add_interaction(clean_input, next_question)
                        return self._build_result(next_question, [], None)
                else:
                    clean_input = _resolve_period_choice(self.state.clarification_context, period)
                    self.state.needs_clarification = False
                    self.state.clarification_message = None
                    self.state.clarification_context = None
            else:
                self.state.needs_clarification = False
                self.state.clarification_message = None
                self.state.clarification_context = None

        lower_input = clean_input.lower()

        standby_zh = ("掰掰", "再見", "待機", "拜拜")
        standby_en = ("goodbye", "bye", "good night", "standby", "go to sleep")
        shutdown_zh = ("關機", "關閉系統", "結束程式")
        shutdown_en = ("shut down", "shutdown", "power off", "turn off system")
        clear_zh = ("清除記憶", "重置記憶", "清記憶")
        clear_en = ("clear memory", "reset memory", "forget everything", "clear history")

        # 規則學習必須在排程解析之前，避免含時間詞的學習句被誤判為排程指令
        learned = self.fastpath.try_learn_rule(clean_input)
        if learned is not None:
            ok = self.memory.save_rule(learned["trigger"], learned["meaning"])
            if ok:
                reply = _t(
                    lang,
                    f"好的，我記住了：{learned['trigger']} 代表 {learned['meaning']}",
                    f"Got it! When you say '{learned['trigger']}', it means '{learned['meaning']}'.",
                )
            else:
                reply = _t(
                    lang,
                    f"好的，已更新：{learned['trigger']} 代表 {learned['meaning']}",
                    f"Updated: '{learned['trigger']}' now means '{learned['meaning']}'.",
                )
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        rules = self.memory.load_rules()
        clean_input = self.fastpath.apply_rules(clean_input, rules)

        # Step 3: schedule fastpath minimal CRUD
        # 1. add
        from src.core.parser.schedule_parser import find_ambiguous_hours

        ambiguous_hours = find_ambiguous_hours(clean_input)
        if ambiguous_hours and _contains_device_word(clean_input):
            first = ambiguous_hours[0]
            hour = int(first.get("hour", 0))
            action_tail = (first.get("tail", "") or "").strip()
            question = f"請問是早上{hour}點還是晚上{hour}點{action_tail}呢？"
            self.state.needs_clarification = True
            self.state.clarification_message = question
            self.state.clarification_context = clean_input
            self.memory.add_interaction(clean_input, question)
            return self._build_result(question, [], None)

        parsed_add = self.schedule_parser.parse_add(clean_input, lang=lang)
        if parsed_add is not None:
            rule = self.scheduler.add(
                hour=parsed_add["hour"],
                minute=parsed_add["minute"],
                actions=parsed_add["actions"],
                name=parsed_add["name"],
                year=parsed_add.get("year"),
                month=parsed_add.get("month"),
                day=parsed_add.get("day"),
                recurrence=parsed_add.get("recurrence", "daily"),
                weekday=parsed_add.get("weekday"),
            )
            if rule is None:
                reply = _t(
                    lang,
                    "排程新增失敗，可能已達上限（5條）或與現有排程衝突。",
                    "Failed to add schedule. The limit (5) may be reached or a conflict exists.",
                )
            else:
                reply = _t(
                    lang,
                    f"好的，已設定排程：{parsed_add['name']}。",
                    f"Schedule set: {parsed_add['name']}.",
                )
                if _has_temperature_condition(clean_input):
                    reply += _t(
                        lang,
                        "目前不支援溫度條件自動化；需要固定時間排程或手動開啟。",
                        " Temperature-based automation is not supported yet; use a fixed-time schedule or manual control.",
                    )
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        # 2. list
        parsed_list = self.schedule_parser.parse_list(clean_input)
        if parsed_list is not None:
            rules = self.scheduler.list_all()
            if not rules:
                reply = _t(lang, "目前沒有設定任何排程。", "No schedules set.")
            else:
                lines = [self._format_schedule_line(idx, r, lang) for idx, r in enumerate(rules, start=1)]
                reply = _t(lang, "目前的排程：\n", "Current schedules:\n") + "\n".join(lines)
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        # 3. delete
        parsed_delete = self.schedule_parser.parse_delete(clean_input)
        if parsed_delete is not None:
            op = parsed_delete.get("op", "delete")
            if op == "delete_by_time":
                hour = parsed_delete.get("hour")
                minute = parsed_delete.get("minute")
                if self.scheduler.delete_by_time(hour, minute):
                    reply = _t(lang, "已刪除指定時間的排程。", "Schedule at the specified time deleted.")
                else:
                    reply = _t(lang, "找不到指定時間的排程。", "No schedule found at the specified time.")
            else:
                rule_id = parsed_delete.get("id")
                if not rule_id:
                    reply = _t(lang, "請告訴我要刪除哪個排程的 ID。", "Please tell me the schedule ID to delete.")
                elif self.scheduler.delete(rule_id):
                    reply = _t(lang, "已刪除指定排程。", "Selected schedule deleted.")
                else:
                    reply = _t(lang, "找不到指定排程。", "Selected schedule not found.")
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        # 4. toggle (enable/disable)
        parsed_toggle = self.schedule_parser.parse_toggle(clean_input)
        if parsed_toggle is not None:
            rule_id = parsed_toggle.get("id")
            op = parsed_toggle.get("op")
            if not rule_id:
                reply = _t(lang, "請告訴我要操作哪個排程的 ID。", "Please tell me the schedule ID.")
            else:
                result = self.scheduler.set_enabled(rule_id, op == "enable")
                if result is None:
                    reply = _t(lang, "找不到指定排程。", "Selected schedule not found.")
                else:
                    reply = _t(
                        lang,
                        f"排程已{'啟用' if result else '停用'}。",
                        f"Schedule {'enabled' if result else 'disabled'}.",
                    )
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        # If input contains delete/cancel keywords with a time reference but
        # parse_delete couldn't resolve the time (ambiguous AM/PM), skip fastpath
        # so Gemini can ask for clarification instead of executing a device command.
        _DELETE_KW = ("刪除", "移除", "取消", "delete", "remove", "cancel")
        from src.core.parser.schedule_parser import has_time_reference as _has_time_ref
        _has_delete_intent = (
            any(kw in clean_input for kw in _DELETE_KW)
            and _has_time_ref(clean_input)
        )

        fast_actions = None if _has_delete_intent else self.fastpath.parse(clean_input, rules=rules)
        print(f"[AGENT ACTIONS] {fast_actions}")
        if fast_actions:
            executed, exec_error = self._execute_actions(fast_actions)
            self.state.update_from_actions([item for item in executed if item.get("success")])
            if not exec_error:
                self.scheduler.block_devices(fast_actions)
            reply = self._friendly_fastpath_reply(fast_actions, lang)
            if exec_error:
                reply += _t(lang, " 但有部分裝置沒有成功執行。", " However, some devices failed to execute.")
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, executed, exec_error)

        gemini_result = self.gemini.parse(clean_input, self.state, self.memory, lang)
        intent = gemini_result.get("intent")
        all_actions = gemini_result.get("actions", [])
        print(f"[AGENT ACTIONS] {all_actions}")
        reply = str(gemini_result.get("reply") or _t(lang, FRIENDLY_ERROR, FRIENDLY_ERROR_EN))

        if intent == "unclear":
            self.state.needs_clarification = True
            self.state.clarification_message = reply
            self.state.clarification_context = clean_input
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], None)

        self.state.needs_clarification = False
        self.state.clarification_message = None
        self.state.clarification_context = None

        if intent == "error":
            self.memory.add_interaction(clean_input, reply)
            return self._build_result(reply, [], "gemini_error")

        device_actions, sched_executed, sched_parts = self._process_gemini_schedule_actions(all_actions, lang)

        executed, exec_error = self._execute_actions(device_actions)
        self.state.update_from_actions([item for item in executed if item.get("success")])
        if device_actions and not exec_error:
            self.scheduler.block_devices(device_actions)

        if sched_parts:
            sep = ", " if lang == "en" else "、"
            end = "." if lang == "en" else "。"
            reply = sep.join(sched_parts)
            if not reply.endswith(end):
                reply += end

        if exec_error:
            reply += _t(lang, " 但有部分裝置沒有成功執行。", " However, some devices failed to execute.")

        all_executed = executed + sched_executed
        self.memory.add_interaction(clean_input, reply)
        return self._build_result(reply, all_executed, exec_error)
