from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Callable

from src.gui.popup_views import create_panel_popup


def _format_schedule_recurrence(rule: dict[str, Any]) -> str:
    recurrence = str(rule.get("recurrence") or "daily").lower()
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


def _format_schedule_action_summary(rule: dict[str, Any]) -> str:
    actions = rule.get("actions")
    if not isinstance(actions, list) or not actions:
        return str(rule.get("name") or "").strip() or "排程"

    loc_map = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}
    parts: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "").upper()
        state_on = str(action.get("state") or "").lower() == "on"
        if action_type == "FAN":
            parts.append("開風扇" if state_on else "關風扇")
        elif action_type == "LED":
            loc_key = str(action.get("location") or "").upper()
            loc = loc_map.get(loc_key, "")
            parts.append(f"{'開' if state_on else '關'}{loc}燈" if loc else ("開燈" if state_on else "關燈"))
        elif action_type == "SET_TEMP":
            parts.append(f"設定溫度 {action.get('value')} 度")

    if parts:
        return "、".join(parts)
    return str(rule.get("name") or "").strip() or "排程"


def _format_schedule_line(idx: int, rule: dict[str, Any]) -> str:
    hour = int(rule.get("hour", 0))
    minute = int(rule.get("minute", 0))
    recurrence = _format_schedule_recurrence(rule)
    action_text = _format_schedule_action_summary(rule)
    rule_id = str(rule.get("id") or "-")
    enabled = bool(rule.get("enabled", True))
    status = "ON" if enabled else "OFF"
    return (
        f"{idx:02d}. [{status}] {recurrence} {hour:02d}:{minute:02d}\n"
        f"    {action_text}\n"
        f"    ID: {rule_id}"
    ).strip()


def parse_add_payload(
    payload: str,
) -> tuple[int, int, list[dict[str, Any]], str] | None:
    """Parse a raw add-command string into (hour, minute, actions, name).

    Accepted formats::
        HH:MM fan on|off
        HH:MM led living|kitchen|guest on|off
        HH:MM temp <int>

    Returns None on any parse failure.
    """
    parts = [p for p in (payload or "").strip().split() if p]
    if len(parts) < 3:
        return None
    try:
        hh, mm = parts[0].split(":", 1)
        hour, minute = int(hh), int(mm)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
    except Exception:
        return None

    device = parts[1].lower()

    if device == "fan" and len(parts) >= 3 and parts[2].lower() in {"on", "off"}:
        state = parts[2].lower()
        return hour, minute, [{"type": "FAN", "state": state}], f"{hour:02d}:{minute:02d} fan {state}"

    if device == "led" and len(parts) >= 4 and parts[3].lower() in {"on", "off"}:
        loc_map = {"living": "LIVING", "kitchen": "KITCHEN", "guest": "GUEST"}
        loc = loc_map.get(parts[2].lower())
        if loc is None:
            return None
        state = parts[3].lower()
        return hour, minute, [{"type": "LED", "location": loc, "state": state}], f"{hour:02d}:{minute:02d} {loc.lower()} light {state}"

    if device == "temp" and len(parts) >= 3:
        try:
            val = int(parts[2])
        except Exception:
            return None
        return hour, minute, [{"type": "SET_TEMP", "value": val}], f"{hour:02d}:{minute:02d} set temp {val}"

    return None


def render_schedule_panel(
    target: ttk.Frame,
    *,
    scheduler: Any,
    parent: tk.Tk,
    font_mono: tkfont.Font,
    font_normal: tkfont.Font,
    tr: Callable[[str], str],
    ensure_text: Callable[[Any], str],
) -> None:
    """Render the schedule list + Add/Delete/Enable-Disable buttons into *target*."""
    for child in target.winfo_children():
        child.destroy()

    rules = scheduler.list_all()
    summary = tk.Label(
        target,
        text=f"共 {len(rules)} 筆排程，使用 ID 可精準刪除與啟用/停用",
        anchor="w",
        font=font_normal,
        fg="#475569",
    )
    summary.pack(fill=tk.X, pady=(0, 6))

    body = tk.Text(
        target,
        height=14,
        wrap=tk.WORD,
        font=font_mono,
        bg="#ffffff",
        fg="#0f172a",
        relief=tk.SOLID,
        bd=1,
        padx=10,
        pady=8,
    )
    body.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
    body.tag_configure("item", spacing1=3, spacing3=8)

    if not rules:
        body.insert("1.0", "(no schedules)")
    else:
        lines: list[str] = []
        for idx, rule in enumerate(rules, start=1):
            lines.append(_format_schedule_line(idx, rule))
        body.insert("1.0", "\n\n".join(lines), "item")
    body.configure(state=tk.DISABLED)

    actions_frame = ttk.Frame(target)
    actions_frame.pack(fill=tk.X)

    title_text = ensure_text(tr("schedule_manager"))

    def _refresh() -> None:
        render_schedule_panel(
            target,
            scheduler=scheduler,
            parent=parent,
            font_mono=font_mono,
            font_normal=font_normal,
            tr=tr,
            ensure_text=ensure_text,
        )

    def _add() -> None:
        raw = simpledialog.askstring(
            title_text,
            "新增格式: HH:MM fan on|off | HH:MM led living|kitchen|guest on|off | HH:MM temp <value>",
            parent=parent,
        )
        if not raw:
            return
        parsed = parse_add_payload(raw)
        if parsed is None:
            messagebox.showerror(title_text, "Invalid add command format.")
            return
        hour, minute, sched_actions, name = parsed
        rule = scheduler.add(hour, minute, sched_actions, name=name, recurrence="daily")
        if rule is None:
            messagebox.showwarning(title_text, "Failed to add schedule (limit/conflict).")
            return
        _refresh()

    def _delete() -> None:
        raw = simpledialog.askstring(
            title_text,
            "輸入 ID 或 HH:MM 刪除排程",
            parent=parent,
        )
        if not raw:
            return
        text = raw.strip()
        if ":" in text:
            try:
                hh, mm = text.split(":", 1)
                deleted = scheduler.delete_by_time(int(hh), int(mm))
            except Exception:
                deleted = []
            if not deleted:
                messagebox.showinfo(title_text, "No schedules found at that time.")
                return
        else:
            if not scheduler.delete(text):
                messagebox.showinfo(title_text, "Schedule ID not found.")
                return
        _refresh()

    def _toggle() -> None:
        rule_id = simpledialog.askstring(title_text, "輸入排程 ID", parent=parent)
        if not rule_id:
            return
        mode = simpledialog.askstring(title_text, "輸入 on/off 或留空(切換)", parent=parent)
        result: bool | None
        if mode is None or not mode.strip():
            result = scheduler.toggle(rule_id.strip())
        else:
            val = mode.strip().lower()
            if val not in {"on", "off"}:
                messagebox.showerror(title_text, "Mode must be on or off.")
                return
            result = scheduler.set_enabled(rule_id.strip(), val == "on")
        if result is None:
            messagebox.showinfo(title_text, "Schedule ID not found.")
            return
        _refresh()

    tk.Button(actions_frame, text="Add", command=_add, font=font_normal).pack(side=tk.LEFT, padx=(0, 8))
    tk.Button(actions_frame, text="Delete", command=_delete, font=font_normal).pack(side=tk.LEFT, padx=(0, 8))
    tk.Button(actions_frame, text="Enable/Disable", command=_toggle, font=font_normal).pack(side=tk.LEFT)


def open_schedule_manager_popup(
    parent: tk.Tk,
    scheduler: Any,
    *,
    safe_title: str,
    tr: Callable[[str], str],
    ensure_text: Callable[[Any], str],
    font_title: tkfont.Font,
    font_normal: tkfont.Font,
    font_mono: tkfont.Font,
) -> None:
    """Open the schedule manager popup window."""

    def _render(target: ttk.Frame) -> None:
        render_schedule_panel(
            target,
            scheduler=scheduler,
            parent=parent,
            font_mono=font_mono,
            font_normal=font_normal,
            tr=tr,
            ensure_text=ensure_text,
        )

    create_panel_popup(
        parent,
        safe_title=safe_title,
        heading_text=ensure_text(tr("schedule_manager")),
        heading_font=font_title,
        button_font=font_normal,
        geometry="620x420",
        refresh_label=ensure_text(tr("refresh")),
        on_refresh=_render,
        padding=14,
        resizable=(True, True),
    )
