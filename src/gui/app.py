from __future__ import annotations

import json
import os
import locale
try:
    import audioop as _audioop
except ModuleNotFoundError:
    _audioop = None
import subprocess
import time
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from typing import Any

import customtkinter as ctk

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


from src.gui.schedule_popup_helper import render_schedule_panel, render_rules_panel
from src.core.scheduler_runtime import SchedulerRuntime
from src.runtime import build_runtime
from src.services.gui_command_service import GuiCommandPresentation, execute_gui_text_command, format_reply_for_language
from src.services.gui_state_service import display_location, display_state_value
from src.utils.config import (
    DATA_DIR,
    RULES_FILE,
    SHOW_DEBUG_TEXT_INPUT,
    SPEECH_ENABLED,
    VOICE_ONLY_MODE,
    VOICE_RETRY_BACKOFF_SEC,
    VOICE_WAKE_FALLBACK_THRESHOLD,
)

try:
    from src.audio.speech_processor import SpeechProcessor
except Exception:
    SpeechProcessor = None  # type: ignore[assignment]


# ─── Theme ────────────────────────────────────────────────────────────────────

class ThemeManager:
    DARK: dict[str, str] = {
        "app_bg": "#121212",
        "panel_bg": "#1E1E1E",
        "card_bg": "#252525",
        "card_border": "#333333",
        "accent": "#3A86FF",
        "success": "#2ECC71",
        "text_primary": "#F0F0F0",
        "text_secondary": "#A0A0A0",
        "hint": "#707070",
        "warning": "#FFB347",
        "user": "#3A86FF",
        "assistant": "#2ECC71",
        "system": "#FFB347",
        "btn_hover": "#2E2E2E",
        "input_bg": "#2A2A2A",
        "nav_hover": "#2E2E2E",
    }
    LIGHT: dict[str, str] = {
        "app_bg": "#F5F7F8",
        "panel_bg": "#FFFFFF",
        "card_bg": "#FFFFFF",
        "card_border": "#E0E0E0",
        "accent": "#3A86FF",
        "success": "#27AE60",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "hint": "#64748B",
        "warning": "#B45309",
        "user": "#1D4ED8",
        "assistant": "#047857",
        "system": "#B45309",
        "btn_hover": "#E8ECF0",
        "input_bg": "#F8FAFC",
        "nav_hover": "#E8ECF0",
    }

    @classmethod
    def get(cls, mode: str) -> dict[str, str]:
        return cls.DARK if mode == "dark" else cls.LIGHT


# ─── I18N ─────────────────────────────────────────────────────────────────────

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
        "ac": "冷氣",
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
        "theme": "主題",
        "theme_dark": "深色",
        "theme_light": "淺色",
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
        "ac": "AC",
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
        "theme": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
    },
}

WINDOW_TITLE_ASCII = "Smart Home Console"


def _is_raspberry_pi() -> bool:
    try:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            return "raspberry pi" in model_path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        pass
    return False


# ─── App ──────────────────────────────────────────────────────────────────────

class DashboardApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # Theme
        self._theme_mode = "dark"
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.colors = ThemeManager.get(self._theme_mode)
        self._clock_job: str | None = None

        # State vars
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

        # Runtime
        env_gui_with_device = os.environ.get("GUI_WITH_DEVICE")
        if env_gui_with_device is None:
            gui_with_device = _is_raspberry_pi()
        else:
            gui_with_device = env_gui_with_device.strip().lower() not in ("0", "false", "off", "no")
        runtime_mode = "hardware" if gui_with_device else "desktop"
        self.runtime = build_runtime(
            mode=runtime_mode,
            memory_keep=self.chat_limit,
            with_device=gui_with_device,
            setup_device=gui_with_device,
        )
        self.app_state = self.runtime.state
        self.memory = self.runtime.memory
        self.agent = self.runtime.agent
        self.schedule_path = Path(DATA_DIR) / "memory" / "schedules.json"
        self.rules_path = Path(RULES_FILE)
        self.chat_history: list[tuple[str, str]] = []
        self.speech_enabled = bool(SPEECH_ENABLED)
        self.voice_only_mode = bool(VOICE_ONLY_MODE)
        self.show_debug_text_input = bool(SHOW_DEBUG_TEXT_INPUT)
        self._text_input_visible = (not self.voice_only_mode) or self.show_debug_text_input
        self._force_waiting_requested = False
        self._discard_next_result = False
        self._voice_stop_event = threading.Event()
        self._voice_thread: threading.Thread | None = None
        self._speech = None
        if self.speech_enabled and SpeechProcessor is not None:
            try:
                self._speech = SpeechProcessor()
            except Exception:
                self._speech = None
                self.speech_enabled = False

        # Fonts
        self.ui_font_size = 14
        self.zh_font_family, self.en_font_family = self._resolve_font_families()
        self._active_font_family = self.zh_font_family if self.lang.get() == "zh" else self.en_font_family
        self._build_fonts()

        # Window
        self.title(WINDOW_TITLE_ASCII)
        self.geometry("1100x700+100+100")
        self.minsize(900, 540)

        # Build
        self._build_layout()
        self._set_boot_status()
        self._tick_clock()

        # Services
        SchedulerRuntime.start(self, self.agent, lambda: self.lang.get(), self._on_schedule_executed)
        self._start_voice_loop()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def _on_schedule_executed(self, command_text: str, reply: str) -> None:
        self._append_chat_message("system", f"[Scheduler] {command_text}\n{reply}")

    def _on_closing(self) -> None:
        self._voice_stop_event.set()
        SchedulerRuntime.stop()
        if self.runtime.device is not None:
            try:
                self.runtime.device.cleanup()
            except Exception:
                pass
        self.destroy()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def tr(self, key: str) -> str:
        return I18N[self.lang.get()].get(key, key)

    def _ensure_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            encodings = ["utf-8", locale.getpreferredencoding(False), "cp950", "big5"]
            tried: set[str] = set()
            for enc in encodings:
                if not enc or enc in tried:
                    continue
                tried.add(enc)
                try:
                    return value.decode(enc)
                except UnicodeDecodeError:
                    continue
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _pick_first_available_font(self, candidates: list[str]) -> str | None:
        available = {name.lower(): name for name in tkfont.families(self)}
        for candidate in candidates:
            found = available.get(candidate.lower())
            if found:
                return found
        return None

    def _resolve_font_families(self) -> tuple[str, str]:
        zh_candidates = [
            "Microsoft JhengHei UI", "Microsoft JhengHei",
            "PingFang TC", "Noto Sans CJK TC", "Noto Sans CJK SC",
            "Source Han Sans TC", "WenQuanYi Zen Hei", "AR PL UMing TW",
        ]
        en_candidates = [
            "Segoe UI", "Calibri", "Inter", "Noto Sans",
            "DejaVu Sans", "Liberation Sans", "Ubuntu", "Arial",
        ]
        zh_font = self._pick_first_available_font(zh_candidates)
        en_font = self._pick_first_available_font(en_candidates)
        safe_fallback = "Segoe UI"
        return zh_font or safe_fallback, en_font or zh_font or safe_fallback

    def _current_font_family(self) -> str:
        return self.zh_font_family if self.lang.get() == "zh" else self.en_font_family

    def _build_fonts(self) -> None:
        fam = self._current_font_family()
        self._active_font_family = fam
        self.font_normal = ctk.CTkFont(family=fam, size=self.ui_font_size)
        self.font_title = ctk.CTkFont(family=fam, size=self.ui_font_size + 4, weight="bold")
        self.font_status = ctk.CTkFont(family=fam, size=self.ui_font_size + 1)
        self.font_mono = ctk.CTkFont(family="Consolas", size=self.ui_font_size - 1)
        self._tk_font_normal = tkfont.Font(family=fam, size=self.ui_font_size)
        self._tk_font_bold = tkfont.Font(family=fam, size=self.ui_font_size, weight="bold")

    # ─── Theme ────────────────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        ctk.set_appearance_mode(self._theme_mode)
        self.colors = ThemeManager.get(self._theme_mode)
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        if self._clock_job:
            self.after_cancel(self._clock_job)
            self._clock_job = None
        for child in self.winfo_children():
            child.destroy()
        self._build_fonts()
        self._build_layout()
        self._set_boot_status()
        self._tick_clock()
        self._load_chat_history()
        if not self.chat_history:
            self.chat_history.append((self.tr("system"), self._ensure_text(self.tr("system_ready"))))
        self._render_chat_history()

    # ─── Layout ───────────────────────────────────────────────────────────────

    def _set_initial_sash(self) -> None:
        try:
            total = self._paned.winfo_width()
            if total > 10:
                self._paned.sash_place(0, int(total * 0.40), 0)
        except Exception:
            pass

    def _build_layout(self) -> None:
        root_frame = ctk.CTkFrame(self, fg_color=self.colors["app_bg"], corner_radius=0)
        root_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Top bar
        top_bar = ctk.CTkFrame(root_frame, fg_color="transparent", height=40)
        top_bar.pack(fill="x", pady=(0, 8))
        top_bar.pack_propagate(False)

        nav_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        nav_frame.pack(side="left", padx=(0, 4))

        self.nav_back_btn = ctk.CTkButton(
            nav_frame, text="←", width=32, height=32, corner_radius=16,
            fg_color="transparent", hover_color=self.colors["nav_hover"],
            text_color=self.colors["text_primary"], font=self.font_normal,
            state="disabled", command=self._nav_back,
        )
        self.nav_back_btn.pack(side="left")

        self.nav_fwd_btn = ctk.CTkButton(
            nav_frame, text="→", width=32, height=32, corner_radius=16,
            fg_color="transparent", hover_color=self.colors["nav_hover"],
            text_color=self.colors["text_primary"], font=self.font_normal,
            state="disabled", command=self._nav_fwd,
        )
        self.nav_fwd_btn.pack(side="left", padx=(4, 0))

        self.nav_page_label = ctk.CTkLabel(
            top_bar, text="", font=self.font_normal,
            text_color=self.colors["text_secondary"],
        )
        self.nav_page_label.pack(side="left", padx=8)

        self.clock_label = ctk.CTkLabel(
            top_bar, text="", font=self.font_normal,
            text_color=self.colors["text_secondary"],
        )
        self.clock_label.pack(side="left", expand=True)

        right_controls = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_controls.pack(side="right")

        self.theme_switch = ctk.CTkSwitch(
            right_controls,
            text=self.tr("theme_dark" if self._theme_mode == "dark" else "theme_light"),
            font=self.font_normal,
            command=self._toggle_theme,
        )
        self.theme_switch.pack(side="left", padx=(0, 12))
        if self._theme_mode == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()

        self.lang_picker = ctk.CTkOptionMenu(
            right_controls,
            values=["zh", "en"],
            variable=self.lang,
            font=self.font_normal,
            width=80,
            command=self._on_language_change,
        )
        self.lang_picker.pack(side="left")

        # Body — draggable split
        self._paned = tk.PanedWindow(
            root_frame,
            orient="horizontal",
            sashwidth=8,
            sashpad=2,
            sashrelief="flat",
            bg=self.colors["app_bg"],
            bd=0,
            relief="flat",
            opaqueresize=False,
        )
        self._paned.pack(fill="both", expand=True)

        left = ctk.CTkFrame(self._paned, fg_color=self.colors["panel_bg"], corner_radius=15)
        self._paned.add(left, minsize=260, stretch="always")
        self._build_left_panel(left)

        right = ctk.CTkFrame(self._paned, fg_color=self.colors["panel_bg"], corner_radius=15)
        self._paned.add(right, minsize=200, stretch="always")
        self._page_container = right
        self._show_page(self._current_page)

        # Set initial 40/60 split after window has rendered
        self._paned.after(50, self._set_initial_sash)

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        # Status card
        status_card = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=10)
        status_card.pack(fill="x", padx=12, pady=(12, 6))

        status_row = ctk.CTkFrame(status_card, fg_color="transparent")
        status_row.pack(fill="x", padx=10, pady=(8, 4))

        self.status_dot = ctk.CTkLabel(
            status_row, text="●", font=self.font_status,
            text_color=self.colors["success"],
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_label = ctk.CTkLabel(
            status_row, textvariable=self.current_status,
            font=self.font_status, text_color=self.colors["text_primary"], anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.status_detail_label = ctk.CTkLabel(
            status_card, text="", font=self.font_normal,
            text_color=self.colors["text_secondary"], anchor="w",
        )
        self.status_detail_label.pack(fill="x", padx=10, pady=(0, 8))

        # Font notice
        self.font_notice_label = ctk.CTkLabel(
            parent, text="", font=self.font_normal,
            text_color=self.colors["warning"], anchor="w", wraplength=280,
        )
        self.font_notice_label.pack(fill="x", padx=12, pady=(0, 2))

        # Voice mode
        vm_frame = ctk.CTkFrame(parent, fg_color="transparent")
        vm_frame.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(
            vm_frame, text=self.tr("voice_mode_title"),
            font=self.font_normal, text_color=self.colors["text_secondary"], anchor="w",
        ).pack(anchor="w")
        self.voice_mode_value_label = ctk.CTkLabel(
            vm_frame, textvariable=self.voice_mode_text,
            font=self.font_normal, text_color=self.colors["text_primary"], anchor="w",
        )
        self.voice_mode_value_label.pack(anchor="w")

        # Debug toggle
        self.debug_toggle_btn = ctk.CTkButton(
            parent, text=self.tr("debug_input_toggle"),
            font=self.font_normal, height=28, corner_radius=8,
            fg_color=self.colors["card_bg"], hover_color=self.colors["btn_hover"],
            text_color=self.colors["text_primary"],
            command=self._toggle_debug_input,
        )
        self.debug_toggle_btn.pack(anchor="w", padx=12, pady=(4, 4))

        # Command input
        self.cmd_frame = ctk.CTkFrame(parent, fg_color=self.colors["card_bg"], corner_radius=10)
        if self._text_input_visible:
            self.cmd_frame.pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkLabel(
            self.cmd_frame, text=self.tr("input_label"),
            font=self.font_normal, text_color=self.colors["text_secondary"], anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))

        input_row = ctk.CTkFrame(self.cmd_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 8))

        self.entry_input = ctk.CTkEntry(
            input_row, textvariable=self.command_text,
            font=self.font_normal,
            fg_color=self.colors["input_bg"],
            border_color=self.colors["card_border"],
            text_color=self.colors["text_primary"],
            corner_radius=8,
        )
        self.entry_input.pack(side="left", fill="x", expand=True)
        self.entry_input.bind("<Return>", self._on_send)

        self.send_btn = ctk.CTkButton(
            input_row, text=self.tr("send"),
            font=self.font_normal, width=64, height=32, corner_radius=8,
            fg_color=self.colors["accent"], hover_color="#2563EB",
            text_color="#FFFFFF", command=self._on_send,
        )
        self.send_btn.pack(side="left", padx=(8, 0))

        # Chat hint
        self.chat_hint_label = ctk.CTkLabel(
            parent, text=self.tr("chat_hint"),
            font=self.font_normal, text_color=self.colors["hint"],
            anchor="w", wraplength=280,
        )
        self.chat_hint_label.pack(fill="x", padx=12, pady=(0, 4))

        # Conversation label
        self.conv_label = ctk.CTkLabel(
            parent, text=self.tr("conversation"),
            font=self.font_title, text_color=self.colors["text_primary"], anchor="w",
        )
        self.conv_label.pack(fill="x", padx=12, pady=(4, 4))

        # Chat box
        self.chat_box = ctk.CTkTextbox(
            parent,
            font=self.font_normal,
            state="disabled",
            wrap="word",
            fg_color=self.colors["card_bg"],
            text_color=self.colors["text_primary"],
            corner_radius=10,
            border_width=0,
        )
        self.chat_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._configure_chat_tags()

    # ─── Chat ─────────────────────────────────────────────────────────────────

    def _configure_chat_tags(self) -> None:
        tb = self.chat_box._textbox
        tb.tag_configure("speaker_user", foreground=self.colors["user"], font=self._tk_font_bold, spacing1=8)
        tb.tag_configure("body_user", foreground=self.colors["text_primary"], lmargin1=16, lmargin2=16, rmargin=14, spacing3=8)
        tb.tag_configure("speaker_assistant", foreground=self.colors["assistant"], font=self._tk_font_bold, spacing1=8)
        tb.tag_configure("body_assistant", foreground=self.colors["text_primary"], lmargin1=16, lmargin2=16, rmargin=14, spacing3=8)
        tb.tag_configure("speaker_system", foreground=self.colors["system"], font=self._tk_font_bold, spacing1=8)
        tb.tag_configure("body_system", foreground=self.colors["text_secondary"], lmargin1=16, lmargin2=16, rmargin=14, spacing3=8)

    def _render_chat_history(self) -> None:
        if not hasattr(self, "chat_box"):
            return
        tb = self.chat_box._textbox
        self.chat_box.configure(state="normal")
        tb.delete("1.0", "end")
        for speaker, message in self.chat_history:
            if speaker == self.tr("you"):
                stag, btag = "speaker_user", "body_user"
            elif speaker == self.tr("assistant"):
                stag, btag = "speaker_assistant", "body_assistant"
            else:
                stag, btag = "speaker_system", "body_system"
            tb.insert("end", f"{speaker}\n", stag)
            tb.insert("end", f"{message}\n\n", btag)
        self.chat_box.configure(state="disabled")
        tb.see("end")

    def _append_chat_message(self, speaker: str, message: str) -> None:
        text = self._ensure_text(message).strip()
        if not text:
            return
        self.chat_history.append((speaker, text))
        self.chat_history = self.chat_history[-self.chat_limit:]
        self._render_chat_history()

    def _load_chat_history(self) -> None:
        try:
            rows = self.memory._read_short().get("interactions", [])
        except Exception:
            rows = []
        self.chat_history = []
        for row in rows[-self.chat_limit:]:
            user_text = self._ensure_text(row.get("user", "")).strip()
            assistant_text = self._ensure_text(row.get("assistant", "")).strip()
            if user_text:
                self.chat_history.append((self.tr("you"), user_text))
            if assistant_text:
                self.chat_history.append((self.tr("assistant"), format_reply_for_language(assistant_text, self.lang.get())))

    # ─── Status ───────────────────────────────────────────────────────────────

    def _set_status(self, state_text: str, detail_text: str) -> None:
        full_status = f"{self.tr('status_prefix')}: {state_text}"
        self.current_status.set(full_status)
        dot_colors = {
            self.tr("idle"): self.colors["success"],
            self.tr("processing"): self.colors["accent"],
            self.tr("speaking"): self.colors["warning"],
            self.tr("waiting_wake_word"): "#A855F7",
            self.tr("listening"): self.colors["success"],
        }
        dot_color = dot_colors.get(state_text, self.colors["text_secondary"])
        if hasattr(self, "status_dot"):
            self.status_dot.configure(text_color=dot_color)
        if hasattr(self, "status_detail_label"):
            self.status_detail_label.configure(text=self._ensure_text(detail_text))
        self._update_voice_mode_indicator(state_text)

    def _set_status_async(self, state_text: str, detail_text: str) -> None:
        self.after(0, lambda: self._set_status(state_text, detail_text))

    def _set_boot_status(self) -> None:
        if self.voice_only_mode and self.speech_enabled:
            self._set_status(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
        else:
            self._set_status(self.tr("idle"), self.tr("ready_detail"))
        self._update_debug_mode_indicator()
        has_cjk = self.zh_font_family not in {
            "DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial", "Helvetica", "Ubuntu"
        }
        if self.lang.get() == "zh" and not has_cjk and hasattr(self, "font_notice_label"):
            self.font_notice_label.configure(text="警告: 系統未偵測到中文字型，請安裝 fonts-noto-cjk 或 fonts-wqy-zenhei。")
        elif hasattr(self, "font_notice_label"):
            self.font_notice_label.configure(text="")

    def _update_voice_mode_indicator(self, state_text: str | None = None) -> None:
        prefix = self._ensure_text(self.tr("mic_prefix"))
        if not self.speech_enabled:
            self.voice_mode_text.set(f"{prefix} {self._ensure_text(self.tr('mic_disabled'))}")
            return
        target = state_text or ""
        if target == self.tr("idle") or not target:
            target = self._ensure_text(self.tr("mic_ready"))
        self.voice_mode_text.set(f"{prefix} {self._ensure_text(target)}")

    def _update_debug_mode_indicator(self) -> None:
        prefix = self._ensure_text(self.tr("debug_input_prefix"))
        value = self.tr("debug_input_enabled") if self._text_input_visible else self.tr("debug_input_hidden")
        self.debug_mode_text.set(f"{self._ensure_text(prefix)} {self._ensure_text(value)}")

    # ─── Input ────────────────────────────────────────────────────────────────

    def _focus_input(self) -> None:
        if self._text_input_visible and hasattr(self, "entry_input"):
            self.entry_input.focus_set()

    def _set_text_input_visibility(self, visible: bool) -> None:
        self._text_input_visible = bool(visible)
        if not hasattr(self, "cmd_frame"):
            return
        if self._text_input_visible:
            if not self.cmd_frame.winfo_ismapped():
                self.cmd_frame.pack(fill="x", padx=12, pady=(0, 6), before=self.chat_hint_label)
            self.send_btn.configure(state="normal")
            self.entry_input.configure(state="normal")
            self._focus_input()
        else:
            self.cmd_frame.pack_forget()
        self._update_debug_mode_indicator()

    def _toggle_debug_input(self) -> None:
        self._set_text_input_visibility(not self._text_input_visible)

    def _set_input_enabled(self, enabled: bool) -> None:
        if not self._text_input_visible:
            return
        state = "normal" if enabled else "disabled"
        self.send_btn.configure(state=state)
        self.entry_input.configure(state=state)

    # ─── Clock ────────────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_text.set(now)
        if hasattr(self, "clock_label"):
            self.clock_label.configure(text=now)
        self._clock_job = self.after(1000, self._tick_clock)

    # ─── Command flow ─────────────────────────────────────────────────────────

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

    # ─── Quick commands ───────────────────────────────────────────────────────

    def _run_quick_command(self, text: str) -> None:
        self._submit_command(text, self.tr("system"))

    def _quick_all_lights_on(self) -> None:
        self._run_quick_command(self.tr("quick_all_lights_on"))

    def _quick_all_lights_off(self) -> None:
        self._run_quick_command(self.tr("quick_all_lights_off"))

    def _quick_reset_device_state(self) -> None:
        self._run_quick_command("全部關燈，關風扇，溫度設為26度")

    def _quick_return_idle(self) -> None:
        is_processing = self.tr("processing") in self.current_status.get()
        self._discard_next_result = is_processing
        self._force_waiting_requested = True
        self.command_text.set("")
        self._set_input_enabled(True)
        self._set_status(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))

    # ─── Schedule helpers ─────────────────────────────────────────────────────

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

    # ─── Navigation ───────────────────────────────────────────────────────────

    _PAGE_TITLE_KEYS = {
        "dashboard": "dashboard",
        "device_state": "device_state",
        "habits": "habits",
        "queue": "queue",
    }

    def _update_nav_buttons(self) -> None:
        if not hasattr(self, "nav_back_btn"):
            return
        self.nav_back_btn.configure(state="normal" if self._page_history else "disabled")
        self.nav_fwd_btn.configure(state="normal" if self._page_future else "disabled")
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

    # ─── Pages ────────────────────────────────────────────────────────────────

    def _build_dashboard_page(self, container: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll, text=self.tr("quick_actions"),
            font=self.font_title, text_color=self.colors["text_primary"], anchor="w",
        ).pack(fill="x", pady=(0, 8))

        qa_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        qa_grid.pack(fill="x", pady=(0, 16))
        qa_grid.columnconfigure(0, weight=1)
        qa_grid.columnconfigure(1, weight=1)

        btn_configs = [
            (self.tr("quick_all_lights_on"), self._quick_all_lights_on, "#16A34A", "#15803D", "#FFFFFF"),
            (self.tr("quick_all_lights_off"), self._quick_all_lights_off, "#DC2626", "#B91C1C", "#FFFFFF"),
            (self.tr("quick_reset_state"), self._quick_reset_device_state, "#D97706", "#B45309", "#FFFFFF"),
            (self.tr("quick_return_idle"), self._quick_return_idle, "#2563EB", "#1D4ED8", "#FFFFFF"),
        ]
        for i, (label, cmd, fg, hover, txt) in enumerate(btn_configs):
            ctk.CTkButton(
                qa_grid, text=self._ensure_text(label), command=cmd,
                font=self.font_normal, height=38, corner_radius=10,
                fg_color=fg, hover_color=hover, text_color=txt,
            ).grid(
                row=i // 2, column=i % 2, sticky="ew",
                padx=(0, 4) if i % 2 == 0 else (4, 0),
                pady=4,
            )

        ctk.CTkLabel(
            scroll, text="─" * 30,
            font=self.font_normal, text_color=self.colors["hint"],
        ).pack(fill="x", pady=(0, 8))

        for page_key, label_key in [("device_state", "device_state"), ("habits", "habits"), ("queue", "queue")]:
            ctk.CTkButton(
                scroll, text=self._ensure_text(self.tr(label_key)),
                command=lambda p=page_key: self._navigate_to(p),
                font=self.font_normal, height=36, corner_radius=10,
                fg_color=self.colors["card_bg"], hover_color=self.colors["btn_hover"],
                text_color=self.colors["text_primary"], anchor="w",
            ).pack(fill="x", pady=4)

        ctk.CTkLabel(
            scroll, text=self.tr("habits_hint"),
            font=self.font_normal, text_color=self.colors["hint"],
            anchor="w", wraplength=300,
        ).pack(fill="x", pady=(0, 4))

    def _build_device_state_page(self, container: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        state = self.app_state.get_state()

        # Climate card
        climate_card = ctk.CTkFrame(scroll, fg_color=self.colors["card_bg"], corner_radius=12)
        climate_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            climate_card,
            text=f"{self.tr('temperature')} / {self.tr('fan')}",
            font=self.font_title, text_color=self.colors["text_primary"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 6))

        # AC status (reflect actual AC on/off state)
        ac_on = str(state.get("ac") or "").lower() == "on"
        ac_label = self._ensure_text(display_state_value(state.get("ac"), self.tr, self._ensure_text))
        self._device_row(climate_card, f"❄️  {self.tr('ac')}", ac_label, on=ac_on)

        temp_val = str(state.get("temperature") or self.tr("unknown"))
        self._device_row(climate_card, f"🌡  {self.tr('temperature')}", f"{temp_val}°C")

        fan_on = str(state.get("fan") or "").lower() == "on"
        fan_label = self._ensure_text(display_state_value(state.get("fan"), self.tr, self._ensure_text))
        self._device_row(climate_card, f"🌀  {self.tr('fan')}", fan_label, on=fan_on)

        amb_temp = state.get("ambient_temp")
        self._device_row(
            climate_card, f"🌡  {self.tr('ambient_temp')}",
            f"{amb_temp}°C" if amb_temp is not None else self._ensure_text(self.tr("unknown")),
        )
        amb_hum = state.get("ambient_humidity")
        self._device_row(
            climate_card, f"💧  {self.tr('ambient_humidity')}",
            f"{amb_hum}%" if amb_hum is not None else self._ensure_text(self.tr("unknown")),
        )
        ctk.CTkFrame(climate_card, fg_color="transparent", height=10).pack()

        # Lights card
        light_card = ctk.CTkFrame(scroll, fg_color=self.colors["card_bg"], corner_radius=12)
        light_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            light_card, text=self.tr("light"),
            font=self.font_title, text_color=self.colors["text_primary"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 6))

        light_state = state.get("light", {})
        loc_colors = {"KITCHEN": "#EF4444", "LIVING": "#22C55E", "GUEST": "#EAB308"}
        if isinstance(light_state, dict) and light_state:
            for location, status in light_state.items():
                loc_text = display_location(location, self.tr, self._ensure_text)
                is_on = str(status).lower() == "on"
                dot_color = loc_colors.get(location.upper(), self.colors["success"]) if is_on else self.colors["hint"]
                row = ctk.CTkFrame(light_card, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=3)
                ctk.CTkLabel(row, text="●", font=self.font_status, text_color=dot_color).pack(side="left", padx=(0, 8))
                ctk.CTkLabel(
                    row, text=self._ensure_text(loc_text),
                    font=self.font_normal, text_color=self.colors["text_primary"], anchor="w",
                ).pack(side="left", fill="x", expand=True)
                val_text = display_state_value(status, self.tr, self._ensure_text)
                ctk.CTkLabel(
                    row, text=self._ensure_text(val_text),
                    font=self.font_normal,
                    text_color=self.colors["success"] if is_on else self.colors["hint"],
                ).pack(side="right")
        else:
            ctk.CTkLabel(
                light_card, text=self.tr("no_data"),
                font=self.font_normal, text_color=self.colors["hint"], anchor="w",
            ).pack(padx=14, pady=(0, 10))
        ctk.CTkFrame(light_card, fg_color="transparent", height=10).pack()

        ctk.CTkButton(
            scroll, text=self.tr("refresh"),
            command=lambda: self._show_page("device_state"),
            font=self.font_normal, height=32, corner_radius=8,
            fg_color=self.colors["card_bg"], hover_color=self.colors["btn_hover"],
            text_color=self.colors["text_primary"],
        ).pack(anchor="w", pady=4)

    def _device_row(self, parent: ctk.CTkFrame, label: str, value: str, on: bool | None = None) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(
            row, text=self._ensure_text(label),
            font=self.font_normal, text_color=self.colors["text_secondary"], anchor="w",
        ).pack(side="left")
        if on is True:
            color = self.colors["success"]
        elif on is False:
            color = self.colors["hint"]
        else:
            color = self.colors["text_primary"]
        ctk.CTkLabel(
            row, text=self._ensure_text(value),
            font=self.font_normal, text_color=color, anchor="e",
        ).pack(side="right")

    def _build_habits_page(self, container: ctk.CTkFrame) -> None:
        render_rules_panel(
            container,
            memory=self.memory,
            parent=self,
            font_normal=self.font_normal,
            ensure_text=self._ensure_text,
            lang=self.lang.get(),
            colors=self.colors,
        )

    def _build_queue_page(self, container: ctk.CTkFrame) -> None:
        render_schedule_panel(
            container,
            scheduler=self.agent.scheduler,
            parent=self,
            font_mono=self.font_mono,
            font_normal=self.font_normal,
            tr=self.tr,
            ensure_text=self._ensure_text,
            lang=self.lang.get(),
            colors=self.colors,
        )

    # ─── Wake / Voice ─────────────────────────────────────────────────────────

    def _consume_force_waiting_request(self) -> bool:
        if self._force_waiting_requested:
            self._force_waiting_requested = False
            return True
        return False

    def _detect_wake_by_energy(self, timeout_seconds: int = 3) -> bool:
        if self._speech is None or _audioop is None:
            return False
        device = getattr(self._speech, "device", "default")
        cmd = ["arecord", "-D", str(device), "-r", "16000", "-c", "1", "-f", "S16_LE", "-t", "raw"]
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

    # ─── Language ─────────────────────────────────────────────────────────────

    def _on_language_change(self, value: str | None = None) -> None:
        self._rebuild_ui()


def run_gui() -> None:
    print("[GUI] app created")
    app = DashboardApp()
    print("[GUI] entering mainloop")
    app.mainloop()


if __name__ == "__main__":
    run_gui()
