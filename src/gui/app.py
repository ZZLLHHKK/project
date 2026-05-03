from __future__ import annotations

import json
import os
import locale
try:
    import audioop as _audioop
except ModuleNotFoundError:
    _audioop = None  # type: ignore[assignment]
import subprocess
import time
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

try:
    from src.utils.tts import speak as _tts_speak
except Exception:
    def _tts_speak(text: str, lang: str = "zh") -> None:  # type: ignore[misc]
        pass


def _speak_async(
    text: str,
    lang: str = "zh",
    on_start: callable | None = None,
    on_done: callable | None = None,
) -> None:
    """在背景執行緒播放 TTS，不阻塞 GUI 主執行緒。"""
    def _runner() -> None:
        if callable(on_start):
            on_start()
        try:
            _tts_speak(text, lang=lang)
        finally:
            if callable(on_done):
                on_done()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()

from src.gui.popup_views import create_panel_popup, create_text_popup
from src.gui.schedule_popup_helper import open_schedule_manager_popup, open_rules_manager_popup, render_schedule_panel, render_rules_panel
from src.core.scheduler_runtime import SchedulerRuntime
from src.runtime import build_runtime
from src.services.gui_command_service import GuiCommandPresentation, execute_gui_text_command, format_reply_for_language
from src.services.gui_state_service import display_location, display_state_value, format_device_state_content, format_queue_content
from src.utils.config import (
    DATA_DIR,
    RULES_FILE,
    SHOW_DEBUG_TEXT_INPUT,
    SPEECH_ENABLED,
    VOICE_ONLY_MODE,
    VOICE_RETRY_BACKOFF_SEC,
    VOICE_WAKE_FALLBACK_THRESHOLD,
    WAKEWORD_ENABLED,
)

try:
    from src.audio.speech_processor import SpeechProcessor
except Exception:
    SpeechProcessor = None  # type: ignore[assignment]

try:
    from src.utils.wait_wakeword import wait_for_wake_word
except Exception:
    wait_for_wake_word = None  # type: ignore[assignment]


I18N: dict[str, dict[str, str]] = {
    "zh": {
        "title": "智慧家庭控制台",
        "system_ready": "系統已啟動，隨時可叫我",
        "idle": "Idle",
        "processing": "Thinking...",
        "speaking": "Speaking...",
        "waiting_wake_word": "Waiting for wake word...",
        "listening": "Listening...",
        "ready_detail": "Idle",
        "processing_detail": "Thinking...",
        "speaking_detail": "Speaking...",
        "waiting_wake_word_detail": "Waiting for wake word...",
        "listening_detail": "Listening...",
        "status_prefix": "狀態",
        "voice_mode_title": "Voice Mode",
        "debug_mode_title": "Debug Mode",
        "debug_input_toggle": "Debug Input",
        "mic_prefix": "Mic:",
        "mic_ready": "Ready",
        "mic_disabled": "Disabled",
        "debug_input_prefix": "Debug input:",
        "debug_input_enabled": "Enabled",
        "debug_input_hidden": "Hidden",
        "input_label": "輸入命令",
        "send": "送出",
        "conversation": "對話紀錄",
        "you": "你",
        "assistant": "助理",
        "system": "系統",
        "dashboard": "控制面板",
        "clock": "目前時間",
        "device_state": "家具狀態",
        "quick_actions": "快捷操作",
        "quick_all_lights_on": "全部開燈",
        "quick_all_lights_off": "全部關燈",
        "quick_reset_state": "重置家具狀態",
        "quick_return_idle": "回到 Idle",
        "temperature": "設定溫度",
        "fan": "風扇",
        "light": "燈光",
        "ambient_temp": "環境溫度",
        "ambient_humidity": "環境濕度",
        "on": "開啟",
        "off": "關閉",
        "unknown": "未知",
        "queue_empty": "目前沒有排程項目。",
        "queue_item": "排程項目",
        "queue_source": "來源",
        "queue_status": "狀態",
        "queue_time": "執行時間",
        "queue_device": "裝置",
        "queue_action": "動作",
        "kitchen": "廚房",
        "living": "客廳",
        "guest": "客房",
        "habits": "使用者習慣",
        "queue": "排程 Queue",
        "schedule_manager": "排程管理",
        "refresh": "重新整理",
        "last_sync": "最後同步",
        "no_data": "目前沒有資料",
        "lang": "語言",
        "reply": "回覆",
        "coming_soon": "此功能尚未接上，先保留介面位置。",
        "habits_hint": "管理已學習規則（可新增與刪除）。",
        "habits_empty": "目前沒有已學習規則",
        "habits_rules": "已學習規則",
        "rules_manager": "規則管理",
        "chat_hint": "按 Enter 或點送出即可對話。",
    },
    "en": {
        "title": "Smart Home Console",
        "system_ready": "System is ready. You can wake me anytime.",
        "idle": "Idle",
        "processing": "Thinking...",
        "speaking": "Speaking...",
        "waiting_wake_word": "Waiting for wake word...",
        "listening": "Listening...",
        "ready_detail": "Idle",
        "processing_detail": "Thinking...",
        "speaking_detail": "Speaking...",
        "waiting_wake_word_detail": "Waiting for wake word...",
        "listening_detail": "Listening...",
        "status_prefix": "Status",
        "voice_mode_title": "Voice Mode",
        "debug_mode_title": "Debug Mode",
        "debug_input_toggle": "Debug Input",
        "mic_prefix": "Mic:",
        "mic_ready": "Ready",
        "mic_disabled": "Disabled",
        "debug_input_prefix": "Debug input:",
        "debug_input_enabled": "Enabled",
        "debug_input_hidden": "Hidden",
        "input_label": "Command",
        "send": "Send",
        "conversation": "Conversation",
        "you": "You",
        "assistant": "Assistant",
        "system": "System",
        "dashboard": "Dashboard",
        "clock": "Current Time",
        "device_state": "Device States",
        "quick_actions": "Quick Actions",
        "quick_all_lights_on": "All Lights On",
        "quick_all_lights_off": "All Lights Off",
        "quick_reset_state": "Reset Device State",
        "quick_return_idle": "Return to Idle",
        "temperature": "Set Temperature",
        "fan": "Fan",
        "light": "Lights",
        "ambient_temp": "Ambient Temperature",
        "ambient_humidity": "Ambient Humidity",
        "on": "On",
        "off": "Off",
        "unknown": "Unknown",
        "queue_empty": "No schedule items yet.",
        "queue_item": "Queue Item",
        "queue_source": "Source",
        "queue_status": "Status",
        "queue_time": "Run Time",
        "queue_device": "Device",
        "queue_action": "Action",
        "kitchen": "Kitchen",
        "living": "Living Room",
        "guest": "Guest Room",
        "habits": "User Habits",
        "queue": "Schedule Queue",
        "schedule_manager": "Schedule Manager",
        "refresh": "Refresh",
        "last_sync": "Last Sync",
        "no_data": "No data yet",
        "lang": "Language",
        "reply": "Reply",
        "coming_soon": "This feature is not wired yet. The slot is reserved in the UI.",
        "habits_hint": "Manage learned rules (add & delete).",
        "habits_empty": "No learned rules yet",
        "habits_rules": "Learned Rules",
        "rules_manager": "Rules Manager",
        "chat_hint": "Press Enter or click Send to chat.",
    },
}


WINDOW_TITLE_ASCII = "Smart Home Console"
WINDOW_TITLE_SUFFIXES = {
    "zh": {
        "家具狀態": "Device States",
        "使用者習慣": "User Habits",
        "排程 Queue": "Schedule Queue",
    },
    "en": {
        "Device States": "Device States",
        "User Habits": "User Habits",
        "Schedule Queue": "Schedule Queue",
    },
}


def _is_raspberry_pi() -> bool:
    try:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            model_text = model_path.read_text(encoding="utf-8", errors="ignore")
            return "raspberry pi" in model_text.lower()
    except Exception:
        pass
    return False


class DashboardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.chat_limit = 20
        self.lang = tk.StringVar(value="zh")
        self.current_status = tk.StringVar(value="")
        self.voice_mode_text = tk.StringVar(value="")
        self.debug_mode_text = tk.StringVar(value="")
        self.time_text = tk.StringVar(value="")
        self.command_text = tk.StringVar(value="")
        self.reply_text = tk.StringVar(value="")
        self._current_page: str = "dashboard"
        self._page_history: list[str] = []
        self._page_future: list[str] = []

        env_gui_with_device = os.environ.get("GUI_WITH_DEVICE")
        if env_gui_with_device is None:
            gui_with_device = _is_raspberry_pi()
        else:
            gui_with_device = env_gui_with_device.strip().lower() not in ("0", "false", "off", "no")
        self.runtime = build_runtime(
            mode="desktop",
            memory_keep=self.chat_limit,
            with_device=gui_with_device,
            setup_device=gui_with_device,
        )
        self.state = self.runtime.state
        self.memory = self.runtime.memory
        self.agent = self.runtime.agent
        self.schedule_path = Path(DATA_DIR) / "memory" / "schedules.json"
        self.rules_path = Path(RULES_FILE)
        self.chat_history: list[tuple[str, str]] = []
        self.speech_enabled = bool(SPEECH_ENABLED)
        self.wakeword_enabled = bool(WAKEWORD_ENABLED)
        self.voice_only_mode = bool(VOICE_ONLY_MODE)
        self.show_debug_text_input = bool(SHOW_DEBUG_TEXT_INPUT)
        self._text_input_visible = (not self.voice_only_mode) or self.show_debug_text_input
        self._force_waiting_requested = False
        self._discard_next_result = False
        self._voice_stop_event = threading.Event()
        self._voice_thread: threading.Thread | None = None
        self._speech = None
        self._wakeword_backend_available = self.wakeword_enabled and callable(wait_for_wake_word)
        if self.speech_enabled and SpeechProcessor is not None:
            try:
                self._speech = SpeechProcessor()
            except Exception:
                self._speech = None
                self.speech_enabled = False
        self.ui_font_size = 11
        self.colors = {
            "app_bg": "#eef2f7",
            "panel_bg": "#f8fafc",
            "card_bg": "#ffffff",
            "card_border": "#dbe4ee",
            "text_primary": "#0f172a",
            "text_secondary": "#475569",
            "hint": "#64748b",
            "warning": "#b45309",
            "user": "#1d4ed8",
            "assistant": "#047857",
            "system": "#b45309",
        }
        self.zh_font_family, self.en_font_family = self._resolve_font_families()
        self.has_cjk_font = self.zh_font_family not in {"DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial", "Helvetica", "Ubuntu"}
        self._active_font_family = self.zh_font_family if self.lang.get() == "zh" else self.en_font_family
        self._build_fonts()

        self._set_window_title()
        self.geometry("1100x700+100+100")
        self.minsize(900, 540)
        self.configure(bg=self.colors["app_bg"])
        self.deiconify()
        self.lift()
        self.focus_force()
        self.update_idletasks()  # force window manager to process show event
        print("[GUI] window visible")

        self._build_layout()
        self._set_boot_status()
        self._tick_clock()
        self.after(50, self._focus_input)
        self.after(300, lambda: _speak_async(I18N["zh"]["system_ready"]) if self.lang.get() == "zh" else None)

        SchedulerRuntime.start(
            self,
            self.agent,
            lambda: self.lang.get(),
            self._on_schedule_executed
        )
        self._start_voice_loop()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_schedule_executed(self, command_text: str, reply: str) -> None:
        self._append_chat_message("system", f"[Scheduler] {command_text}\n{reply}")

    def _on_closing(self) -> None:
        self._voice_stop_event.set()
        SchedulerRuntime.stop()
        self.destroy()
    def tr(self, key: str) -> str:
        return I18N[self.lang.get()].get(key, key)

    def _ensure_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            encodings = ["utf-8", locale.getpreferredencoding(False), "cp950", "big5"]
            tried: set[str] = set()
            for encoding in encodings:
                if not encoding or encoding in tried:
                    continue
                tried.add(encoding)
                try:
                    return value.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _safe_title_text(self) -> str:
        raw_title = self._ensure_text(I18N[self.lang.get()]["title"])
        try:
            raw_title.encode("ascii")
            return raw_title
        except UnicodeEncodeError:
            return WINDOW_TITLE_ASCII

    def _safe_child_title_text(self, raw_title: str) -> str:
        clean_title = self._ensure_text(raw_title)
        mapped = WINDOW_TITLE_SUFFIXES.get(self.lang.get(), {}).get(clean_title)
        if mapped:
            return f"{WINDOW_TITLE_ASCII} - {mapped}"
        try:
            clean_title.encode("ascii")
            return f"{WINDOW_TITLE_ASCII} - {clean_title}"
        except UnicodeEncodeError:
            return WINDOW_TITLE_ASCII

    def _set_window_title(self) -> None:
        safe_title = self._safe_title_text()
        self.title(safe_title)
        self.wm_title(safe_title)

    def _pick_first_available_font(self, candidates: list[str]) -> str | None:
        available = {name.lower(): name for name in tkfont.families(self)}
        for candidate in candidates:
            found = available.get(candidate.lower())
            if found:
                return found
        return None

    def _resolve_font_families(self) -> tuple[str, str]:
        zh_candidates = [
            "Noto Sans CJK TC",
            "Noto Sans CJK SC",
            "Noto Sans CJK JP",
            "Source Han Sans TC",
            "WenQuanYi Zen Hei",
            "PingFang TC",
            "Microsoft JhengHei",
            "AR PL UMing TW",
            "AR PL UKai TW",
        ]
        en_candidates = [
            "DejaVu Sans",
            "Noto Sans",
            "Liberation Sans",
            "Ubuntu",
            "Arial",
            "Helvetica",
        ]

        zh_font = self._pick_first_available_font(zh_candidates)
        en_font = self._pick_first_available_font(en_candidates)

        safe_fallback = "DejaVu Sans"
        return zh_font or safe_fallback, en_font or zh_font or safe_fallback

    def _current_font_family(self) -> str:
        return self.zh_font_family if self.lang.get() == "zh" else self.en_font_family

    def _build_fonts(self) -> None:
        self._active_font_family = self._current_font_family()
        self.font_normal = tkfont.Font(self, family=self._active_font_family, size=self.ui_font_size)
        self.font_title = tkfont.Font(self, family=self._active_font_family, size=self.ui_font_size + 3, weight="bold")
        self.font_status = tkfont.Font(self, family=self._active_font_family, size=self.ui_font_size + 1)
        self.font_mono = tkfont.Font(self, family=self._active_font_family, size=self.ui_font_size)
        self.font_chat_speaker = tkfont.Font(self, family=self._active_font_family, size=self.ui_font_size, weight="bold")

    def _apply_widget_fonts(self) -> None:
        always_present = [
            getattr(self, "system_title", None),
            getattr(self, "lang_label", None),
            getattr(self, "status_label", None),
            getattr(self, "voice_mode_title_label", None),
            getattr(self, "voice_mode_value_label", None),
            getattr(self, "debug_mode_title_label", None),
            getattr(self, "debug_mode_value_label", None),
            getattr(self, "debug_toggle_btn", None),
            getattr(self, "entry_input", None),
            getattr(self, "send_btn", None),
            getattr(self, "chat_box", None),
            getattr(self, "clock_label", None),
            getattr(self, "sync_label", None),
            getattr(self, "nav_back_btn", None),
            getattr(self, "nav_fwd_btn", None),
            getattr(self, "nav_page_label", None),
            getattr(self, "font_notice_label", None),
        ]
        for widget in always_present:
            if widget is None:
                continue
            if widget is getattr(self, "system_title", None):
                widget.configure(font=self.font_title)
            elif widget is getattr(self, "status_label", None):
                widget.configure(font=self.font_status)
            elif widget is getattr(self, "chat_box", None):
                widget.configure(font=self.font_normal)
            else:
                widget.configure(font=self.font_normal)

    def _load_chat_history(self) -> None:
        try:
            rows = self.memory._read_short().get("interactions", [])
        except Exception:
            rows = []

        self.chat_history = []
        for row in rows[-self.chat_limit :]:
            user_text = self._ensure_text(row.get("user", "")).strip()
            assistant_text = self._ensure_text(row.get("assistant", "")).strip()
            if user_text:
                self.chat_history.append((self.tr("you"), user_text))
            if assistant_text:
                self.chat_history.append((self.tr("assistant"), format_reply_for_language(assistant_text, self.lang.get())))

    def _append_chat_message(self, speaker: str, message: str) -> None:
        text = self._ensure_text(message).strip()
        if not text:
            return

        self.chat_history.append((speaker, text))
        self.chat_history = self.chat_history[-self.chat_limit :]
        self._render_chat_history()

    def _focus_input(self) -> None:
        if self._text_input_visible and hasattr(self, "entry_input"):
            self.entry_input.focus_set()

    def _update_voice_mode_indicator(self, state_text: str | None = None) -> None:
        prefix = self._ensure_text(self.tr("mic_prefix"))
        if not self.speech_enabled:
            self.voice_mode_text.set(f"{prefix} {self._ensure_text(self.tr('mic_disabled'))}")
            return

        target_state = state_text or ""
        if target_state == self.tr("idle"):
            target_state = self._ensure_text(self.tr("mic_ready"))
        elif not target_state:
            target_state = self._ensure_text(self.tr("mic_ready"))

        self.voice_mode_text.set(f"{prefix} {self._ensure_text(target_state)}")

    def _update_debug_mode_indicator(self) -> None:
        prefix = self._ensure_text(self.tr("debug_input_prefix"))
        value = self.tr("debug_input_enabled") if self._text_input_visible else self.tr("debug_input_hidden")
        self.debug_mode_text.set(f"{self._ensure_text(prefix)} {self._ensure_text(value)}")

    def _set_text_input_visibility(self, visible: bool) -> None:
        self._text_input_visible = bool(visible)
        if self._text_input_visible:
            if self.cmd_frame.winfo_manager() == "":
                self.cmd_frame.pack(fill=tk.X, before=self.conversation_frame)
            self.send_btn.configure(state=tk.NORMAL)
            self.entry_input.configure(state=tk.NORMAL)
            self._focus_input()
        else:
            if self.cmd_frame.winfo_manager() != "":
                self.cmd_frame.pack_forget()
        self._update_debug_mode_indicator()

    def _toggle_debug_input(self) -> None:
        self._set_text_input_visibility(not self._text_input_visible)

    def _set_status(self, state_text: str, detail_text: str) -> None:
        full_status = f"{self.tr('status_prefix')}: {state_text}"
        self.current_status.set(full_status)
        status_palette = {
            self.tr("idle"): ("#0f766e", "#ccfbf1"),
            self.tr("processing"): ("#1d4ed8", "#dbeafe"),
            self.tr("speaking"): ("#b45309", "#ffedd5"),
            self.tr("waiting_wake_word"): ("#7c3aed", "#ede9fe"),
            self.tr("listening"): ("#047857", "#d1fae5"),
        }
        fg, bg = status_palette.get(state_text, (self.colors["text_primary"], "#e2e8f0"))
        self.status_label.configure(text=full_status, fg=fg, bg=bg, padx=10, pady=4)
        self.status_detail_label.configure(text=self._ensure_text(detail_text), fg=self.colors["text_secondary"], bg=self.colors["panel_bg"])
        self._update_voice_mode_indicator(state_text)

    def _set_input_enabled(self, enabled: bool) -> None:
        if not self._text_input_visible:
            return
        state = tk.NORMAL if enabled else tk.DISABLED
        self.send_btn.configure(state=state)
        self.entry_input.configure(state=state)

    def _begin_command_flow(self, raw: str) -> None:
        self._set_input_enabled(False)
        self._set_status(self.tr("processing"), self.tr("processing_detail"))
        self._append_chat_message(self.tr("you"), raw)
        self.command_text.set("")

    def _finish_command_flow(self) -> None:
        self._set_status(self.tr("idle"), self.tr("ready_detail"))
        self._set_input_enabled(True)
        self._focus_input()

    def _apply_command_result(self, result: GuiCommandPresentation) -> None:
        self.reply_text.set(result.formatted_reply)
        self._append_chat_message(self.tr("assistant"), result.formatted_reply)
        if result.should_speak and result.spoken_reply:
            _speak_async(
                result.spoken_reply,
                lang=self.lang.get(),
                on_start=lambda: self.after(0, lambda: self._set_status(self.tr("speaking"), self.tr("speaking_detail"))),
                on_done=lambda: self.after(0, lambda: self._set_status(self.tr("idle"), self.tr("ready_detail"))),
            )

    def _render_chat_history(self) -> None:
        if not hasattr(self, "chat_box"):
            return

        self.chat_box.configure(state=tk.NORMAL)
        self.chat_box.delete("1.0", tk.END)
        for speaker, message in self.chat_history:
            if speaker == self.tr("you"):
                speaker_tag = "speaker_user"
                body_tag = "body_user"
            elif speaker == self.tr("assistant"):
                speaker_tag = "speaker_assistant"
                body_tag = "body_assistant"
            else:
                speaker_tag = "speaker_system"
                body_tag = "body_system"

            self.chat_box.insert(tk.END, f"{speaker}\n", speaker_tag)
            self.chat_box.insert(tk.END, f"{message}\n\n", body_tag)
        self.chat_box.configure(state=tk.DISABLED)
        self.chat_box.see(tk.END)

    def _configure_chat_tags(self) -> None:
        self.chat_box.tag_configure("speaker_user", foreground=self.colors["user"], font=self.font_chat_speaker, spacing1=8)
        self.chat_box.tag_configure("body_user", foreground=self.colors["text_primary"], background="#eff6ff", lmargin1=16, lmargin2=16, rmargin=14, spacing3=10)
        self.chat_box.tag_configure("speaker_assistant", foreground=self.colors["assistant"], font=self.font_chat_speaker, spacing1=8)
        self.chat_box.tag_configure("body_assistant", foreground=self.colors["text_primary"], background="#ecfdf5", lmargin1=16, lmargin2=16, rmargin=14, spacing3=10)
        self.chat_box.tag_configure("speaker_system", foreground=self.colors["system"], font=self.font_chat_speaker, spacing1=8)
        self.chat_box.tag_configure("body_system", foreground="#78350f", background="#fffbeb", lmargin1=16, lmargin2=16, rmargin=14, spacing3=10)

    def _format_device_state_content(self) -> str:
        return format_device_state_content(self.state.get_state(), self.tr, self._ensure_text)

    def _format_queue_content(self) -> str:
        return format_queue_content(self._read_schedule_queue(), self.tr, self._ensure_text)

    def _build_layout(self) -> None:
        wrapper = tk.Frame(self, bg=self.colors["app_bg"], padx=12, pady=12)
        wrapper.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(wrapper, bg=self.colors["app_bg"])
        top_bar.pack(fill=tk.X)

        self.system_title = tk.Label(
            top_bar,
            text=self._ensure_text(self.tr("system_ready")),
            anchor="w",
            font=self.font_title,
            bg=self.colors["app_bg"],
            fg=self.colors["text_primary"],
        )
        self.system_title.pack(side=tk.LEFT)

        lang_group = tk.Frame(top_bar, bg=self.colors["app_bg"])
        lang_group.pack(side=tk.RIGHT)
        self.lang_label = tk.Label(lang_group, text=f"{self._ensure_text(self.tr('lang'))}: ", font=self.font_normal, bg=self.colors["app_bg"], fg=self.colors["text_secondary"])
        self.lang_label.pack(side=tk.LEFT)
        lang_picker = ttk.Combobox(lang_group, textvariable=self.lang, values=["zh", "en"], width=6, state="readonly")
        lang_picker.pack(side=tk.LEFT)
        lang_picker.bind("<<ComboboxSelected>>", self._on_language_change)

        body = tk.Frame(wrapper, bg=self.colors["app_bg"])
        body.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=self.colors["panel_bg"], highlightbackground=self.colors["card_border"], highlightthickness=1, padx=12, pady=12)
        left.grid(row=0, column=0, sticky="nsew")

        self.status_label = tk.Label(left, text="", anchor="w", font=self.font_status, bg="#e2e8f0", fg=self.colors["text_primary"])
        self.status_label.pack(anchor="w", pady=(0, 12))

        self.status_detail_label = tk.Label(left, text="", anchor="w", justify=tk.LEFT, fg=self.colors["text_secondary"], bg=self.colors["panel_bg"], font=self.font_normal)
        self.status_detail_label.pack(anchor="w", pady=(0, 10))

        self.font_notice_label = tk.Label(left, text="", anchor="w", fg=self.colors["warning"], bg=self.colors["panel_bg"], font=self.font_normal)
        self.font_notice_label.pack(anchor="w", pady=(0, 8))

        self.chat_hint_label = tk.Label(left, text=self._ensure_text(self.tr("chat_hint")), anchor="w", fg=self.colors["hint"], bg=self.colors["panel_bg"], font=self.font_normal)
        self.chat_hint_label.pack(anchor="w", pady=(0, 8))

        self.voice_mode_title_label = tk.Label(
            left,
            text=self._ensure_text(self.tr("voice_mode_title")),
            anchor="w",
            fg=self.colors["text_secondary"],
            bg=self.colors["panel_bg"],
            font=self.font_normal,
        )
        self.voice_mode_title_label.pack(anchor="w")
        self.voice_mode_value_label = tk.Label(
            left,
            textvariable=self.voice_mode_text,
            anchor="w",
            fg=self.colors["text_primary"],
            bg=self.colors["panel_bg"],
            font=self.font_normal,
        )
        self.voice_mode_value_label.pack(anchor="w", pady=(0, 6))

        self.debug_mode_title_label = tk.Label(
            left,
            text=self._ensure_text(self.tr("debug_mode_title")),
            anchor="w",
            fg=self.colors["text_secondary"],
            bg=self.colors["panel_bg"],
            font=self.font_normal,
        )
        self.debug_mode_title_label.pack(anchor="w")
        self.debug_mode_value_label = tk.Label(
            left,
            textvariable=self.debug_mode_text,
            anchor="w",
            fg=self.colors["text_primary"],
            bg=self.colors["panel_bg"],
            font=self.font_normal,
        )
        self.debug_mode_value_label.pack(anchor="w", pady=(0, 6))

        self.debug_toggle_btn = tk.Button(
            left,
            text=self._ensure_text(self.tr("debug_input_toggle")),
            command=self._toggle_debug_input,
            font=self.font_normal,
            relief=tk.GROOVE,
            bd=1,
            bg="#ffffff",
            fg="#0f172a",
            activebackground="#f1f5f9",
            activeforeground="#0f172a",
            padx=8,
        )
        self.debug_toggle_btn.pack(anchor="w", pady=(0, 8))

        self.cmd_frame = ttk.LabelFrame(left, text=self.tr("input_label"), padding=10)
        self.entry_input = tk.Entry(self.cmd_frame, textvariable=self.command_text, font=self.font_normal)
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_input.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(
            self.cmd_frame,
            text=self._ensure_text(self.tr("send")),
            command=self._on_send,
            font=self.font_normal,
            bg="#1d4ed8",
            fg="#ffffff",
            activebackground="#1e40af",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
        )
        self.send_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._set_text_input_visibility(self._text_input_visible)

        self.conversation_frame = ttk.LabelFrame(left, text=self.tr("conversation"), padding=10)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.chat_box = scrolledtext.ScrolledText(
            self.conversation_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=16,
            font=self.font_normal,
            relief=tk.SOLID,
            bd=1,
            bg=self.colors["card_bg"],
            fg=self.colors["text_primary"],
            padx=8,
            pady=8,
        )
        self.chat_box.pack(fill=tk.BOTH, expand=True)
        self._configure_chat_tags()

        self._load_chat_history()
        if not self.chat_history:
            self.chat_history.append((self.tr("system"), self._ensure_text(self.tr("system_ready"))))
        self._render_chat_history()

        right = tk.LabelFrame(
            body,
            text=self.tr("dashboard"),
            bg=self.colors["panel_bg"],
            fg=self.colors["text_primary"],
            highlightbackground=self.colors["card_border"],
            highlightthickness=1,
            padx=10,
            pady=10,
        )
        self.dashboard_frame = right
        right.grid(row=0, column=1, sticky="nsew")

        self.clock_label = tk.Label(right, text="", anchor="w", font=self.font_normal, bg=self.colors["panel_bg"], fg=self.colors["text_secondary"])
        self.clock_label.pack(anchor="w")

        nav_bar = tk.Frame(right, bg=self.colors["panel_bg"])
        nav_bar.pack(fill=tk.X, pady=(6, 4))

        self.nav_back_btn = tk.Button(
            nav_bar, text="←", command=self._nav_back,
            state=tk.DISABLED,
            font=self.font_normal,
            relief=tk.GROOVE, bd=1,
            bg="#ffffff", fg="#0f172a",
            activebackground="#f1f5f9", activeforeground="#0f172a",
            padx=8, pady=2,
        )
        self.nav_back_btn.pack(side=tk.LEFT)

        self.nav_fwd_btn = tk.Button(
            nav_bar, text="→", command=self._nav_fwd,
            state=tk.DISABLED,
            font=self.font_normal,
            relief=tk.GROOVE, bd=1,
            bg="#ffffff", fg="#0f172a",
            activebackground="#f1f5f9", activeforeground="#0f172a",
            padx=8, pady=2,
        )
        self.nav_fwd_btn.pack(side=tk.LEFT, padx=(4, 0))

        self.nav_page_label = tk.Label(nav_bar, text="", anchor="w", font=self.font_normal, bg=self.colors["panel_bg"], fg=self.colors["text_secondary"])
        self.nav_page_label.pack(side=tk.LEFT, padx=8)

        self._page_container = tk.Frame(right, bg=self.colors["panel_bg"])
        self._page_container.pack(fill=tk.BOTH, expand=True)

        self.sync_label = tk.Label(right, text="", anchor="w", font=self.font_normal, bg=self.colors["panel_bg"], fg=self.colors["text_secondary"])
        self.sync_label.pack(anchor="w", pady=(4, 0))

        self._show_page("dashboard")
        self._apply_widget_fonts()

    def _set_boot_status(self) -> None:
        if self.voice_only_mode and self.speech_enabled:
            self._set_status(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
        else:
            self._set_status(self.tr("idle"), self.tr("ready_detail"))
        self._update_debug_mode_indicator()
        if self.lang.get() == "zh" and not self.has_cjk_font:
            self.font_notice_label.configure(text="警告: 系統未偵測到中文字型，請安裝 fonts-noto-cjk 或 fonts-wqy-zenhei。")
        else:
            self.font_notice_label.configure(text="")

    def _tick_clock(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_text.set(now)
        self.clock_label.configure(text=f"{self._ensure_text(self.tr('clock'))}: {now}")
        self.sync_label.configure(text=f"{self._ensure_text(self.tr('last_sync'))}: {now}")
        self.after(1000, self._tick_clock)

    def _submit_command(self, raw: str, speaker: str) -> None:
        if not raw:
            return
        self._set_input_enabled(False)
        self._set_status(self.tr("processing"), self.tr("processing_detail"))
        self._append_chat_message(speaker, raw)
        current_language = self.lang.get()

        def _worker() -> None:
            result = execute_gui_text_command(self.agent, raw, current_language)
            self.after(0, lambda: self._on_send_done(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_send(self, event: tk.Event | None = None) -> None:
        raw = self.command_text.get().strip()
        if not raw:
            self._focus_input()
            return

        self.command_text.set("")
        self._submit_command(raw, self.tr("you"))

    def _on_send_done(self, result: GuiCommandPresentation) -> None:
        if self._discard_next_result:
            self._discard_next_result = False
            self._finish_command_flow()
            self._set_status(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
            return
        self._finish_command_flow()
        self._apply_command_result(result)

    def _read_schedule_queue(self) -> list[dict[str, Any]]:
        if not self.schedule_path.exists():
            return []
        try:
            payload = json.loads(self.schedule_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, dict):
            items = payload.get("items", [])
            return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        return []

    def _format_habits_content(self) -> str:
        rules: list[dict[str, Any]] = []

        try:
            raw_rules = json.loads(self.rules_path.read_text(encoding="utf-8")) if self.rules_path.exists() else {}
            if isinstance(raw_rules, dict):
                items = raw_rules.get("rules", [])
                if isinstance(items, list):
                    rules = [x for x in items if isinstance(x, dict)]
            elif isinstance(raw_rules, list):
                rules = [x for x in raw_rules if isinstance(x, dict)]
        except Exception:
            rules = []

        sections: list[str] = []
        sections.append(self._ensure_text(self.tr("habits_rules")))
        if rules:
            for rule in rules:
                trigger = self._ensure_text(rule.get("trigger", "")).strip()
                meaning = self._ensure_text(rule.get("meaning", "")).strip()
                if trigger and meaning:
                    sections.append(f"- {trigger} => {meaning}")
        else:
            sections.append(f"- {self._ensure_text(self.tr('habits_empty'))}")

        return "\n".join(sections)

    def _set_status_async(self, state_text: str, detail_text: str) -> None:
        self.after(0, lambda: self._set_status(state_text, detail_text))

    def _consume_force_waiting_request(self) -> bool:
        if self._force_waiting_requested:
            self._force_waiting_requested = False
            return True
        return False

    def _run_quick_command(self, text: str) -> None:
        self._submit_command(text, self.tr("system"))

    def _quick_all_lights_on(self) -> None:
        self._run_quick_command(self.tr("quick_all_lights_on"))

    def _quick_all_lights_off(self) -> None:
        self._run_quick_command(self.tr("quick_all_lights_off"))

    def _quick_reset_device_state(self) -> None:
        # Keep reset action minimal and reuse existing command routing.
        self._run_quick_command("全部關燈，關風扇，溫度設為26度")

    def _quick_return_idle(self) -> None:
        is_processing = self.tr("processing") in self.current_status.get()
        self._discard_next_result = is_processing
        self._force_waiting_requested = True
        self.command_text.set("")
        self._set_input_enabled(True)
        self._set_status(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))

    def _detect_wake_by_energy(self, timeout_seconds: int = 3) -> bool:
        if self._speech is None or _audioop is None:
            return False
        device = getattr(self._speech, "device", "default")
        cmd = [
            "arecord", "-D", str(device), "-r", "16000", "-c", "1", "-f", "S16_LE", "-t", "raw",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception:
            return False

        threshold = VOICE_WAKE_FALLBACK_THRESHOLD
        chunk_bytes = 3200
        end_at = time.time() + max(1, timeout_seconds)
        activated = False
        try:
            while not self._voice_stop_event.is_set() and time.time() < end_at:
                if proc.stdout is None:
                    break
                data = proc.stdout.read(chunk_bytes)
                if not data:
                    break
                if _audioop.rms(data, 2) >= threshold:
                    activated = True
                    break
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        return activated

    def _wait_for_wake(self) -> bool:
        if self._voice_stop_event.is_set():
            return False
        if self._wakeword_backend_available and callable(wait_for_wake_word):
            ok = bool(wait_for_wake_word())
            if not ok:
                self._wakeword_backend_available = False
            return ok
        return self._detect_wake_by_energy(timeout_seconds=3)

    def _start_voice_loop(self) -> None:
        if not self.speech_enabled or self._speech is None:
            return

        def _voice_worker() -> None:
            while not self._voice_stop_event.is_set():
                if self._consume_force_waiting_request():
                    self._set_status_async(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
                    time.sleep(max(0.0, VOICE_RETRY_BACKOFF_SEC))
                    continue
                self._set_status_async(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
                if not self._wait_for_wake():
                    time.sleep(max(0.0, VOICE_RETRY_BACKOFF_SEC))
                    continue
                if self._consume_force_waiting_request():
                    self._set_status_async(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
                    time.sleep(max(0.0, VOICE_RETRY_BACKOFF_SEC))
                    continue
                if self._voice_stop_event.is_set():
                    break

                self._set_status_async(self.tr("listening"), self.tr("listening_detail"))
                try:
                    spoken = self._speech.speech_to_text(
                        duration=getattr(self._speech, "default_duration", 5),
                        on_transcribe_start=lambda: self._set_status_async(self.tr("processing"), self.tr("processing_detail")),
                    ).strip()
                except TypeError:
                    spoken = self._speech.speech_to_text(duration=getattr(self._speech, "default_duration", 5)).strip()
                    self._set_status_async(self.tr("processing"), self.tr("processing_detail"))
                except Exception:
                    spoken = ""

                if self._consume_force_waiting_request():
                    self._set_status_async(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
                    time.sleep(max(0.0, VOICE_RETRY_BACKOFF_SEC))
                    continue
                if not spoken:
                    time.sleep(max(0.0, VOICE_RETRY_BACKOFF_SEC))
                    continue

                self.after(0, lambda text=spoken: self._submit_command(text, self.tr("you")))

        self._voice_thread = threading.Thread(target=_voice_worker, daemon=True, name="gui-voice-loop")
        self._voice_thread.start()

    _PAGE_TITLE_KEYS = {
        "dashboard": "dashboard",
        "device_state": "device_state",
        "habits": "habits",
        "queue": "queue",
    }

    def _update_nav_buttons(self) -> None:
        self.nav_back_btn.configure(state=tk.NORMAL if self._page_history else tk.DISABLED)
        self.nav_fwd_btn.configure(state=tk.NORMAL if self._page_future else tk.DISABLED)
        key = self._PAGE_TITLE_KEYS.get(self._current_page, self._current_page)
        self.nav_page_label.configure(text=self._ensure_text(self.tr(key)))

    def _navigate_to(self, page: str) -> None:
        if page == self._current_page:
            return
        self._page_history.append(self._current_page)
        self._page_future.clear()
        self._current_page = page
        self._show_page(page)

    def _nav_back(self) -> None:
        if not self._page_history:
            return
        self._page_future.append(self._current_page)
        self._current_page = self._page_history.pop()
        self._show_page(self._current_page)

    def _nav_fwd(self) -> None:
        if not self._page_future:
            return
        self._page_history.append(self._current_page)
        self._current_page = self._page_future.pop()
        self._show_page(self._current_page)

    def _show_page(self, page: str) -> None:
        for child in self._page_container.winfo_children():
            child.destroy()
        if page == "dashboard":
            self._build_dashboard_page(self._page_container)
        elif page == "device_state":
            self._build_device_state_page(self._page_container)
        elif page == "habits":
            self._build_habits_page(self._page_container)
        elif page == "queue":
            self._build_queue_page(self._page_container)
        self._update_nav_buttons()

    def _build_dashboard_page(self, container: tk.Frame) -> None:
        qa_frame = tk.LabelFrame(
            container,
            text=self._ensure_text(self.tr("quick_actions")),
            bg=self.colors["panel_bg"],
            fg=self.colors["text_primary"],
            highlightbackground=self.colors["card_border"],
            highlightthickness=1,
            padx=8, pady=8,
        )
        qa_frame.pack(fill=tk.X, pady=(4, 8))
        qa_frame.columnconfigure(0, weight=1)
        qa_frame.columnconfigure(1, weight=1)

        btn_style = dict(font=self.font_normal, relief=tk.GROOVE, bd=1)
        tk.Button(qa_frame, text=self._ensure_text(self.tr("quick_all_lights_on")),
                  command=self._quick_all_lights_on, bg="#e8f7ee", fg="#065f46",
                  activebackground="#d1fae5", activeforeground="#065f46", **btn_style
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        tk.Button(qa_frame, text=self._ensure_text(self.tr("quick_all_lights_off")),
                  command=self._quick_all_lights_off, bg="#fef2f2", fg="#991b1b",
                  activebackground="#fee2e2", activeforeground="#991b1b", **btn_style
                  ).grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        tk.Button(qa_frame, text=self._ensure_text(self.tr("quick_reset_state")),
                  command=self._quick_reset_device_state, bg="#fff7ed", fg="#9a3412",
                  activebackground="#ffedd5", activeforeground="#9a3412", **btn_style
                  ).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        tk.Button(qa_frame, text=self._ensure_text(self.tr("quick_return_idle")),
                  command=self._quick_return_idle, bg="#eaf2ff", fg="#1e3a8a",
                  activebackground="#dbeafe", activeforeground="#1e3a8a", **btn_style
                  ).grid(row=1, column=1, sticky="ew", padx=(4, 0))

        nav_style = dict(font=self.font_normal, relief=tk.GROOVE, bd=1, bg="#ffffff",
                         fg="#0f172a", activebackground="#f1f5f9", activeforeground="#0f172a")
        btns = tk.Frame(container, bg=self.colors["panel_bg"])
        btns.pack(fill=tk.X, pady=(0, 4))
        tk.Button(btns, text=self._ensure_text(self.tr("device_state")),
                  command=lambda: self._navigate_to("device_state"), **nav_style
                  ).pack(fill=tk.X, pady=3)
        tk.Button(btns, text=self._ensure_text(self.tr("habits")),
                  command=lambda: self._navigate_to("habits"), **nav_style
                  ).pack(fill=tk.X, pady=3)
        tk.Label(container, text=self._ensure_text(self.tr("habits_hint")),
                 anchor="w", justify=tk.LEFT, wraplength=250,
                 fg=self.colors["hint"], bg=self.colors["panel_bg"], font=self.font_normal
                 ).pack(fill=tk.X, pady=(0, 4))
        tk.Button(btns, text=self._ensure_text(self.tr("queue")),
                  command=lambda: self._navigate_to("queue"), **nav_style
                  ).pack(fill=tk.X, pady=3)

    def _build_device_state_page(self, container: tk.Frame) -> None:
        state = self.state.get_state()

        climate_lf = ttk.LabelFrame(container, text=self._ensure_text(self.tr("temperature") + " / " + self.tr("fan")), padding=10)
        climate_lf.pack(fill=tk.X, pady=(0, 8))
        climate_lf.columnconfigure(1, weight=1)

        rows_climate = [
            (self.tr("temperature"), f"{state.get('temperature', self.tr('unknown'))}"),
            (self.tr("fan"), display_state_value(state.get("fan"), self.tr, self._ensure_text)),
            (self.tr("ambient_temp"), self._ensure_text(str(state.get("ambient_temp") or self.tr("unknown")))),
            (self.tr("ambient_humidity"), self._ensure_text(str(state.get("ambient_humidity") or self.tr("unknown")))),
        ]
        for r, (label_text, value_text) in enumerate(rows_climate):
            tk.Label(climate_lf, text=self._ensure_text(label_text), anchor="w", font=self.font_normal, fg="#374151").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 16))
            color = "#16a34a" if value_text in {self.tr("on"), "on", "On"} else ("#dc2626" if value_text in {self.tr("off"), "off", "Off"} else "#1e293b")
            tk.Label(climate_lf, text=self._ensure_text(value_text), anchor="w", font=self.font_normal, fg=color).grid(row=r, column=1, sticky="w", pady=2)

        light_lf = ttk.LabelFrame(container, text=self._ensure_text(self.tr("light")), padding=10)
        light_lf.pack(fill=tk.X, pady=(0, 8))
        light_lf.columnconfigure(1, weight=1)

        light_state = state.get("light", {})
        if isinstance(light_state, dict) and light_state:
            for r, (location, status) in enumerate(light_state.items()):
                loc_text = display_location(location, self.tr, self._ensure_text)
                val_text = display_state_value(status, self.tr, self._ensure_text)
                dot_color = "#16a34a" if str(status).lower() == "on" else "#9ca3af"
                row_frame = ttk.Frame(light_lf)
                row_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=2)
                tk.Label(row_frame, text="●", fg=dot_color, font=self.font_normal).pack(side=tk.LEFT, padx=(0, 6))
                tk.Label(row_frame, text=self._ensure_text(loc_text), anchor="w", font=self.font_normal, fg="#374151").pack(side=tk.LEFT)
                tk.Label(row_frame, text=self._ensure_text(val_text), anchor="w", font=self.font_normal, fg="#16a34a" if str(status).lower() == "on" else "#6b7280").pack(side=tk.RIGHT)
        else:
            tk.Label(light_lf, text=self._ensure_text(self.tr("no_data")), anchor="w", font=self.font_normal, fg="#9ca3af").grid(row=0, column=0, sticky="w")

        tk.Button(
            container, text=self._ensure_text(self.tr("refresh")),
            command=lambda: self._show_page("device_state"),
            font=self.font_normal, relief=tk.GROOVE, bd=1,
            bg="#ffffff", fg="#0f172a",
            activebackground="#f1f5f9", activeforeground="#0f172a",
            padx=8,
        ).pack(anchor="w", pady=(4, 0))

    def _build_habits_page(self, container: tk.Frame) -> None:
        frame = ttk.Frame(container)
        frame.pack(fill=tk.BOTH, expand=True)
        render_rules_panel(
            frame,
            memory=self.memory,
            parent=self,
            font_normal=self.font_normal,
            ensure_text=self._ensure_text,
            lang=self.lang.get(),
        )

    def _build_queue_page(self, container: tk.Frame) -> None:
        frame = ttk.Frame(container)
        frame.pack(fill=tk.BOTH, expand=True)
        render_schedule_panel(
            frame,
            scheduler=self.agent.scheduler,
            parent=self,
            font_mono=self.font_mono,
            font_normal=self.font_normal,
            tr=self.tr,
            ensure_text=self._ensure_text,
            lang=self.lang.get(),
        )

    def _open_device_state(self) -> None:
        safe_title = self._safe_child_title_text(self._ensure_text(self.tr("device_state")))

        def _render(target: ttk.Frame) -> None:
            for child in target.winfo_children():
                child.destroy()

            state = self.state.get_state()

            climate_lf = ttk.LabelFrame(target, text=self._ensure_text(self.tr("temperature") + " / " + self.tr("fan")), padding=10)
            climate_lf.pack(fill=tk.X, pady=(0, 8))
            climate_lf.columnconfigure(1, weight=1)

            rows_climate = [
                (self.tr("temperature"), f"{state.get('temperature', self.tr('unknown'))}"),
                (self.tr("fan"), display_state_value(state.get("fan"), self.tr, self._ensure_text)),
                (self.tr("ambient_temp"), self._ensure_text(str(state.get("ambient_temp") or self.tr("unknown")))),
                (self.tr("ambient_humidity"), self._ensure_text(str(state.get("ambient_humidity") or self.tr("unknown")))),
            ]
            for r, (label_text, value_text) in enumerate(rows_climate):
                tk.Label(climate_lf, text=self._ensure_text(label_text), anchor="w", font=self.font_normal, fg="#374151").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 16))
                color = "#16a34a" if value_text in {self.tr("on"), "on", "On"} else ("#dc2626" if value_text in {self.tr("off"), "off", "Off"} else "#1e293b")
                tk.Label(climate_lf, text=self._ensure_text(value_text), anchor="w", font=self.font_normal, fg=color).grid(row=r, column=1, sticky="w", pady=2)

            light_lf = ttk.LabelFrame(target, text=self._ensure_text(self.tr("light")), padding=10)
            light_lf.pack(fill=tk.X, pady=(0, 8))
            light_lf.columnconfigure(1, weight=1)

            light_state = state.get("light", {})
            if isinstance(light_state, dict) and light_state:
                for r, (location, status) in enumerate(light_state.items()):
                    loc_text = display_location(location, self.tr, self._ensure_text)
                    val_text = display_state_value(status, self.tr, self._ensure_text)
                    dot_color = "#16a34a" if str(status).lower() == "on" else "#9ca3af"
                    row_frame = ttk.Frame(light_lf)
                    row_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=2)
                    tk.Label(row_frame, text="●", fg=dot_color, font=self.font_normal).pack(side=tk.LEFT, padx=(0, 6))
                    tk.Label(row_frame, text=self._ensure_text(loc_text), anchor="w", font=self.font_normal, fg="#374151").pack(side=tk.LEFT)
                    tk.Label(row_frame, text=self._ensure_text(val_text), anchor="w", font=self.font_normal, fg="#16a34a" if str(status).lower() == "on" else "#6b7280").pack(side=tk.RIGHT)
            else:
                tk.Label(light_lf, text=self._ensure_text(self.tr("no_data")), anchor="w", font=self.font_normal, fg="#9ca3af").grid(row=0, column=0, sticky="w")

        create_panel_popup(
            self,
            safe_title=safe_title,
            heading_text=self._ensure_text(self.tr("device_state")),
            heading_font=self.font_title,
            button_font=self.font_normal,
            geometry="420x380",
            refresh_label=self._ensure_text(self.tr("refresh")),
            on_refresh=_render,
            padding=14,
            resizable=(False, False),
        )

    def _open_queue(self) -> None:
        open_schedule_manager_popup(
            self,
            self.agent.scheduler,
            safe_title=self._safe_child_title_text(self._ensure_text(self.tr("schedule_manager"))),
            tr=self.tr,
            ensure_text=self._ensure_text,
            font_title=self.font_title,
            font_normal=self.font_normal,
            font_mono=self.font_mono,
            lang=self.lang.get(),
        )

    def _open_habits(self) -> None:
        open_rules_manager_popup(
            self,
            self.memory,
            safe_title=self._safe_child_title_text(self._ensure_text(self.tr("rules_manager"))),
            font_title=self.font_title,
            font_normal=self.font_normal,
            ensure_text=self._ensure_text,
            lang=self.lang.get(),
        )

    def _open_text_window(self, title: str, content: str) -> None:
        create_text_popup(
            self,
            safe_title=self._safe_child_title_text(title),
            heading_text=self._ensure_text(title),
            heading_font=self.font_title,
            body_font=self.font_mono,
            button_font=self.font_normal,
            geometry="560x360",
            refresh_label=self._ensure_text(self.tr("refresh")),
            initial_content=content,
            on_refresh=lambda: self._get_window_content(title),
        )

    def _get_window_content(self, title: str) -> str:
        if title == self.tr("device_state"):
            return self._format_device_state_content()
        if title == self.tr("queue"):
            return self._format_queue_content()
        if title == self.tr("habits"):
            return self._format_habits_content()
        return self._ensure_text(self.tr("no_data"))

    def _on_language_change(self, event: tk.Event | None = None) -> None:
        self._build_fonts()
        self._apply_widget_fonts()
        self._set_window_title()
        self._configure_chat_tags()
        self.system_title.configure(text=self._ensure_text(self.tr("system_ready")))
        self.lang_label.configure(text=f"{self._ensure_text(self.tr('lang'))}: ")
        self.chat_hint_label.configure(text=self._ensure_text(self.tr("chat_hint")))
        self.voice_mode_title_label.configure(text=self._ensure_text(self.tr("voice_mode_title")))
        self.debug_mode_title_label.configure(text=self._ensure_text(self.tr("debug_mode_title")))
        self.debug_toggle_btn.configure(text=self._ensure_text(self.tr("debug_input_toggle")))
        self.send_btn.configure(text=self._ensure_text(self.tr("send")))
        self.cmd_frame.configure(text=self.tr("input_label"))
        self.conversation_frame.configure(text=self._ensure_text(self.tr("conversation")))
        self.dashboard_frame.configure(text=self._ensure_text(self.tr("dashboard")))
        self._show_page(self._current_page)
        self._load_chat_history()
        if not self.chat_history:
            self.chat_history.append((self.tr("system"), self._ensure_text(self.tr("system_ready"))))
        self._render_chat_history()
        self._set_boot_status()
        self._update_voice_mode_indicator()
        self._update_debug_mode_indicator()
        self._focus_input()


def run_gui() -> None:
    print("[GUI] app created")
    app = DashboardApp()
    print("[GUI] entering mainloop")
    app.mainloop()
