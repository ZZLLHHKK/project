from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk


def _t(lang: str, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _c(colors: dict | None, key: str, fallback: str) -> str:
    if colors and key in colors:
        return colors[key]
    return fallback


def _center_on_parent(dlg: ctk.CTkToplevel, parent: tk.Misc, w: int, h: int) -> None:
    dlg.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    dlg.geometry(f"{w}x{h}+{x}+{y}")


def _make_dialog_base(
    parent: tk.Misc,
    title: str,
    w: int,
    h: int,
    colors: dict | None,
) -> tuple[ctk.CTkToplevel, str, str, str, str]:
    dlg = ctk.CTkToplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.lift()
    dlg.focus_force()
    _center_on_parent(dlg, parent, w, h)

    bg = _c(colors, "panel_bg", "#1E1E1E")
    accent = _c(colors, "accent", "#3A86FF")
    text_primary = _c(colors, "text_primary", "#F0F0F0")
    input_bg = _c(colors, "input_bg", "#2A2A2A")
    dlg.configure(fg_color=bg)
    return dlg, bg, accent, text_primary, input_bg


def _add_buttons(
    dlg: ctk.CTkToplevel,
    font: Any,
    accent: str,
    text_primary: str,
    on_ok: Callable[[], None],
    on_cancel: Callable[[], None],
) -> None:
    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(fill="x", padx=20, pady=(0, 16))
    ctk.CTkButton(btn_row, text="OK", font=font, width=90, height=36,
                  fg_color=accent, corner_radius=8, command=on_ok).pack(side="right", padx=(8, 0))
    ctk.CTkButton(btn_row, text="Cancel", font=font, width=90, height=36,
                  fg_color="transparent", border_width=1,
                  text_color=text_primary, corner_radius=8, command=on_cancel).pack(side="right")


def _ctk_ask_schedule(
    parent: tk.Misc,
    title: str,
    lang: str,
    *,
    font: Any,
    colors: dict | None = None,
) -> str | None:
    """Schedule add dialog with aligned format hint rows."""
    result: list[str | None] = [None]
    W, H = 540, 260

    dlg, bg, accent, text_primary, input_bg = _make_dialog_base(parent, title, W, H, colors)
    hint_color = _c(colors, "text_secondary", "#A0A0A0")

    # Format hint block — separate labels keep alignment clean
    hint_header = _t(lang, "格式：", "Format:")
    hint_rows = [
        "HH:MM  fan  on | off",
        "HH:MM  led  living | kitchen | guest  on | off",
        "HH:MM  temp  <" + _t(lang, "數值", "value") + ">",
    ]

    ctk.CTkLabel(dlg, text=hint_header, font=font,
                 text_color=hint_color, anchor="w").pack(padx=20, pady=(18, 2), anchor="w")

    hint_frame = ctk.CTkFrame(dlg, fg_color=_c(colors, "card_bg", "#252525"), corner_radius=6)
    hint_frame.pack(fill="x", padx=20, pady=(0, 10))
    for row_text in hint_rows:
        ctk.CTkLabel(hint_frame, text=row_text, font=font,
                     text_color=hint_color, anchor="w").pack(padx=12, pady=2, anchor="w")

    entry = ctk.CTkEntry(dlg, font=font, fg_color=input_bg,
                         text_color=text_primary, border_color=accent,
                         height=40, corner_radius=8, placeholder_text="e.g. 08:00 fan on")
    entry.pack(fill="x", padx=20, pady=(0, 12))
    entry.focus()

    def _ok(event: Any = None) -> None:
        result[0] = entry.get()
        dlg.destroy()

    def _cancel(event: Any = None) -> None:
        dlg.destroy()

    _add_buttons(dlg, font, accent, text_primary, _ok, _cancel)
    entry.bind("<Return>", _ok)
    dlg.bind("<Escape>", _cancel)
    dlg.wait_window()
    return result[0]


def _ctk_ask_rule(
    parent: tk.Misc,
    lang: str,
    *,
    font: Any,
    colors: dict | None = None,
) -> tuple[str, str] | None:
    """Modal two-field dialog for adding a custom rule."""
    result: list[tuple[str, str] | None] = [None]
    W, H = 520, 260

    title = _t(lang, "新增規則", "Add Rule")
    dlg, bg, accent, text_primary, input_bg = _make_dialog_base(parent, title, W, H, colors)
    text_secondary = _c(colors, "text_secondary", "#A0A0A0")

    ctk.CTkLabel(dlg, text=_t(lang, "觸發詞（你會說的話）：", "Trigger phrase (what you say):"),
                 font=font, text_color=text_secondary, anchor="w").pack(padx=20, pady=(20, 4), anchor="w")
    trigger_entry = ctk.CTkEntry(dlg, font=font, fg_color=input_bg,
                                 text_color=text_primary, border_color=accent,
                                 height=40, corner_radius=8)
    trigger_entry.pack(fill="x", padx=20, pady=(0, 12))
    trigger_entry.focus()

    ctk.CTkLabel(dlg, text=_t(lang, "代表的動作或語意：", "What it means / action:"),
                 font=font, text_color=text_secondary, anchor="w").pack(padx=20, pady=(0, 4), anchor="w")
    meaning_entry = ctk.CTkEntry(dlg, font=font, fg_color=input_bg,
                                 text_color=text_primary, border_color=accent,
                                 height=40, corner_radius=8)
    meaning_entry.pack(fill="x", padx=20, pady=(0, 12))

    def _ok(event: Any = None) -> None:
        t = trigger_entry.get().strip()
        m = meaning_entry.get().strip()
        if t and m:
            result[0] = (t, m)
        dlg.destroy()

    def _cancel(event: Any = None) -> None:
        dlg.destroy()

    _add_buttons(dlg, font, accent, text_primary, _ok, _cancel)
    meaning_entry.bind("<Return>", _ok)
    dlg.bind("<Escape>", _cancel)
    dlg.wait_window()
    return result[0]


def _format_schedule_recurrence(rule: dict[str, Any], lang: str = "zh") -> str:
    recurrence = str(rule.get("recurrence") or "daily").lower()
    if recurrence == "daily":
        return _t(lang, "每天", "Every day")
    if recurrence == "weekly":
        return _t(lang, "每週", "Weekly")
    if recurrence == "monthly":
        return _t(lang, "每月", "Monthly")
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
                    return _t(lang, "今天", "Today")
                if target == today + timedelta(days=1):
                    return _t(lang, "明天", "Tomorrow")
            except Exception:
                pass
            if year:
                return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
            return f"{int(month):02d}/{int(day):02d}"
        return _t(lang, "單次", "Once")
    return _t(lang, "排程", "Scheduled")


def _format_schedule_action_summary(rule: dict[str, Any], lang: str = "zh") -> str:
    actions = rule.get("actions")
    if not isinstance(actions, list) or not actions:
        return str(rule.get("name") or "").strip() or _t(lang, "排程", "schedule")

    loc_zh = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}
    loc_en = {"LIVING": "living", "KITCHEN": "kitchen", "GUEST": "guest"}
    parts: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "").upper()
        state_on = str(action.get("state") or "").lower() == "on"
        if action_type == "FAN":
            parts.append(_t(lang,
                            "開風扇" if state_on else "關風扇",
                            "fan on" if state_on else "fan off"))
        elif action_type == "LED":
            loc_key = str(action.get("location") or "").upper()
            if lang == "en":
                loc = loc_en.get(loc_key, "light")
                parts.append(f"{loc} light {'on' if state_on else 'off'}")
            else:
                loc = loc_zh.get(loc_key, "")
                parts.append(f"{'開' if state_on else '關'}{loc}燈" if loc else ("開燈" if state_on else "關燈"))
        elif action_type == "SET_TEMP":
            val = action.get("value")
            parts.append(_t(lang, f"設定溫度 {val} 度", f"set temp {val}°C"))

    if parts:
        return (", " if lang == "en" else "、").join(parts)
    return str(rule.get("name") or "").strip() or _t(lang, "排程", "schedule")


def _format_schedule_line(idx: int, rule: dict[str, Any], lang: str = "zh") -> str:
    hour = int(rule.get("hour", 0))
    minute = int(rule.get("minute", 0))
    recurrence = _format_schedule_recurrence(rule, lang)
    action_text = _format_schedule_action_summary(rule, lang)
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
    target: ctk.CTkFrame,
    *,
    scheduler: Any,
    parent: tk.Misc,
    font_mono: Any,
    font_normal: Any,
    tr: Callable[[str], str],
    ensure_text: Callable[[Any], str],
    lang: str = "zh",
    colors: dict | None = None,
) -> None:
    for child in target.winfo_children():
        child.destroy()

    rules = scheduler.list_all()
    title_text = ensure_text(tr("schedule_manager"))

    text_secondary = _c(colors, "text_secondary", "#475569")
    text_primary = _c(colors, "text_primary", "#0f172a")
    card_bg = _c(colors, "card_bg", "#f8fafc")
    card_border = _c(colors, "card_border", "#e2e8f0")
    hint = _c(colors, "hint", "#9ca3af")

    ctk.CTkLabel(
        target,
        text=_t(lang, f"共 {len(rules)} 筆排程", f"{len(rules)} schedule(s)"),
        anchor="w",
        font=font_normal,
        text_color=text_secondary,
    ).pack(fill="x", pady=(0, 6))

    scroll_frame = ctk.CTkScrollableFrame(target, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    def _refresh() -> None:
        render_schedule_panel(
            target,
            scheduler=scheduler,
            parent=parent,
            font_mono=font_mono,
            font_normal=font_normal,
            tr=tr,
            ensure_text=ensure_text,
            lang=lang,
            colors=colors,
        )

    if not rules:
        ctk.CTkLabel(
            scroll_frame,
            text=_t(lang, "(目前沒有排程)", "(No schedules)"),
            anchor="w",
            font=font_normal,
            text_color=hint,
        ).pack(fill="x", padx=8, pady=4)
    else:
        for idx, rule in enumerate(rules):
            rule_id = str(rule.get("id") or "")
            hour = int(rule.get("hour", 0))
            minute = int(rule.get("minute", 0))
            recurrence = _format_schedule_recurrence(rule, lang)
            action_text = _format_schedule_action_summary(rule, lang)
            enabled = bool(rule.get("enabled", True))

            row = ctk.CTkFrame(scroll_frame, fg_color=card_bg, corner_radius=6)
            row.pack(fill="x", pady=3, padx=4)

            status_color = "#16a34a" if enabled else "#9ca3af"
            status_char = "●" if enabled else "○"
            ctk.CTkLabel(
                row,
                text=f"{idx + 1:02d}. {status_char}",
                font=font_normal,
                text_color=status_color,
                width=52,
                anchor="e",
            ).pack(side="left", padx=(6, 0), pady=6)

            info_text = f"{recurrence} {hour:02d}:{minute:02d}  {action_text}"
            ctk.CTkLabel(
                row,
                text=ensure_text(info_text),
                anchor="w",
                font=font_normal,
                text_color=text_primary,
            ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

            def _make_toggle(rid: str, current_enabled: bool) -> Callable[[], None]:
                def _toggle() -> None:
                    scheduler.set_enabled(rid, not current_enabled)
                    _refresh()
                return _toggle

            def _make_delete(rid: str, label: str) -> Callable[[], None]:
                def _delete() -> None:
                    msg = _t(lang,
                             f"確定要刪除排程「{label}」嗎？",
                             f"Delete schedule '{label}'?")
                    title = _t(lang, "刪除排程", "Delete Schedule")
                    if messagebox.askyesno(title, msg, parent=parent):
                        scheduler.delete(rid)
                        _refresh()
                return _delete

            toggle_label = _t(lang, "停用" if enabled else "啟用", "Disable" if enabled else "Enable")
            toggle_fg = "#92400e" if enabled else "#065f46"
            toggle_hover = "#fef3c7" if enabled else "#d1fae5"
            toggle_bg = "#fef9c3" if enabled else "#e8f7ee"
            ctk.CTkButton(
                row,
                text=toggle_label,
                command=_make_toggle(rule_id, enabled),
                font=font_normal,
                fg_color=toggle_bg,
                text_color=toggle_fg,
                hover_color=toggle_hover,
                corner_radius=6,
                height=28,
                width=60,
            ).pack(side="right", padx=(2, 4), pady=6)

            ctk.CTkButton(
                row,
                text=_t(lang, "刪除", "Delete"),
                command=_make_delete(rule_id, ensure_text(info_text)),
                font=font_normal,
                fg_color="#fee2e2",
                text_color="#991b1b",
                hover_color="#fecaca",
                corner_radius=6,
                height=28,
                width=52,
            ).pack(side="right", padx=(2, 0), pady=6)

    add_bar = ctk.CTkFrame(target, fg_color="transparent")
    add_bar.pack(fill="x", pady=(8, 0))

    def _add() -> None:
        raw = _ctk_ask_schedule(parent, title_text, lang, font=font_normal, colors=colors)
        if not raw:
            return
        parsed = parse_add_payload(raw)
        if parsed is None:
            messagebox.showerror(
                title_text,
                _t(lang, "格式錯誤，請確認輸入格式。", "Invalid format. Please check the input."),
            )
            return
        hour, minute, sched_actions, name = parsed
        rule = scheduler.add(hour, minute, sched_actions, name=name, recurrence="daily")
        if rule is None:
            messagebox.showwarning(
                title_text,
                _t(lang, "新增失敗（時間衝突或已達上限）。", "Failed: conflict or limit reached."),
            )
            return
        _refresh()

    ctk.CTkButton(
        add_bar,
        text=_t(lang, "新增排程", "Add Schedule"),
        command=_add,
        font=font_normal,
        fg_color=_c(colors, "success", "#2ECC71"),
        text_color="#ffffff",
        hover_color="#27AE60",
        corner_radius=6,
        height=30,
        width=120,
    ).pack(side="left")


def render_rules_panel(
    target: ctk.CTkFrame,
    *,
    memory: Any,
    parent: tk.Misc,
    font_normal: Any,
    ensure_text: Callable[[Any], str],
    lang: str = "zh",
    colors: dict | None = None,
) -> None:
    for child in target.winfo_children():
        child.destroy()

    rules = memory.load_rules()

    text_secondary = _c(colors, "text_secondary", "#475569")
    text_primary = _c(colors, "text_primary", "#0f172a")
    card_bg = _c(colors, "card_bg", "#f8fafc")
    hint = _c(colors, "hint", "#9ca3af")

    ctk.CTkLabel(
        target,
        text=ensure_text(_t(lang,
                            f"共 {len(rules)} 筆自訂規則",
                            f"{len(rules)} custom rule(s)")),
        anchor="w",
        font=font_normal,
        text_color=text_secondary,
    ).pack(fill="x", pady=(0, 6))

    scroll_frame = ctk.CTkScrollableFrame(target, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    def _refresh() -> None:
        render_rules_panel(
            target,
            memory=memory,
            parent=parent,
            font_normal=font_normal,
            ensure_text=ensure_text,
            lang=lang,
            colors=colors,
        )

    if not rules:
        ctk.CTkLabel(
            scroll_frame,
            text=_t(lang, "(目前沒有自訂規則)", "(No custom rules)"),
            anchor="w",
            font=font_normal,
            text_color=hint,
        ).pack(fill="x", padx=8, pady=4)
    else:
        for idx, rule in enumerate(rules):
            trigger = ensure_text(rule.get("trigger", "")).strip()
            meaning = ensure_text(rule.get("meaning", "")).strip()

            row = ctk.CTkFrame(scroll_frame, fg_color=card_bg, corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)

            ctk.CTkLabel(
                row,
                text=f"{idx + 1:02d}.",
                font=font_normal,
                text_color=_c(colors, "hint", "#94a3b8"),
                width=32,
                anchor="e",
            ).pack(side="left", padx=(6, 0), pady=6)

            ctk.CTkLabel(
                row,
                text=f"{trigger}  →  {meaning}",
                anchor="w",
                font=font_normal,
                text_color=text_primary,
            ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

            def _make_delete(t: str) -> Callable[[], None]:
                def _delete() -> None:
                    msg = _t(lang, f"確定要刪除規則「{t}」嗎？", f"Delete rule '{t}'?")
                    title = _t(lang, "刪除規則", "Delete Rule")
                    if messagebox.askyesno(title, msg, parent=parent):
                        memory.delete_rule(t)
                        _refresh()
                return _delete

            ctk.CTkButton(
                row,
                text=_t(lang, "刪除", "Delete"),
                command=_make_delete(trigger),
                font=font_normal,
                fg_color="#fee2e2",
                text_color="#991b1b",
                hover_color="#fecaca",
                corner_radius=6,
                height=28,
                width=52,
            ).pack(side="right", padx=(2, 6), pady=6)

    add_bar = ctk.CTkFrame(target, fg_color="transparent")
    add_bar.pack(fill="x", pady=(8, 0))

    def _add_rule() -> None:
        pair = _ctk_ask_rule(parent, lang, font=font_normal, colors=colors)
        if pair is None:
            return
        trigger, meaning = pair
        memory.save_rule(trigger, meaning)
        _refresh()

    ctk.CTkButton(
        add_bar,
        text=_t(lang, "新增規則", "Add Rule"),
        command=_add_rule,
        font=font_normal,
        fg_color=_c(colors, "success", "#2ECC71"),
        text_color="#ffffff",
        hover_color="#27AE60",
        corner_radius=6,
        height=30,
        width=110,
    ).pack(side="left")
