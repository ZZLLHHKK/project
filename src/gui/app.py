from __future__ import annotations

import json
import locale
import audioop
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
    def _tts_speak(text: str) -> None:  # type: ignore[misc]
        pass


def _speak_async(text: str) -> None:
    """在背景執行緒播放 TTS，不阻塞 GUI 主執行緒。"""
    t = threading.Thread(target=_tts_speak, args=(text,), daemon=True)
    t.start()

from src.gui.popup_views import create_panel_popup, create_text_popup
from src.gui.schedule_popup_helper import open_schedule_manager_popup
from src.core.scheduler_runtime import SchedulerRuntime
from src.runtime import build_runtime
from src.services.gui_command_service import GuiCommandPresentation, execute_gui_text_command, format_reply_for_language
from src.services.gui_state_service import display_location, display_state_value, format_device_state_content, format_queue_content
from src.utils.config import DATA_DIR, RULES_FILE, SPEECH_ENABLED, WAKEWORD_ENABLED

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
        "idle": "閒置當中",
        "processing": "處理中",
        "waiting_wake_word": "等待喚醒詞...",
        "listening": "聆聽中...",
        "ready_detail": "系統已準備完成，可以直接輸入命令。",
        "processing_detail": "正在分析你的指令並產生回應。",
        "waiting_wake_word_detail": "語音系統待機中，請先喚醒。",
        "listening_detail": "已喚醒，正在聆聽正式指令。",
        "status_prefix": "狀態",
        "input_label": "輸入命令",
        "send": "送出",
        "conversation": "對話紀錄",
        "you": "你",
        "assistant": "助理",
        "system": "系統",
        "dashboard": "控制面板",
        "clock": "目前時間",
        "device_state": "家具狀態",
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
        "habits": "使用者習慣（開發中）",
        "queue": "排程 Queue",
        "schedule_manager": "排程管理",
        "refresh": "重新整理",
        "last_sync": "最後同步",
        "no_data": "目前沒有資料",
        "lang": "語言",
        "reply": "回覆",
        "coming_soon": "此功能尚未接上，先保留介面位置。",
        "habits_hint": "檢視已學習規則。",
        "habits_empty": "目前沒有已學習規則",
        "habits_rules": "已學習規則",
        "chat_hint": "按 Enter 或點送出即可對話。",
    },
    "en": {
        "title": "Smart Home Console",
        "system_ready": "System is ready. You can wake me anytime.",
        "idle": "Idle",
        "processing": "Processing",
        "waiting_wake_word": "Waiting for wake word...",
        "listening": "Listening...",
        "ready_detail": "The system is ready. You can type a command now.",
        "processing_detail": "Analyzing your command and preparing a reply.",
        "waiting_wake_word_detail": "Voice system is idle and waiting for wake word.",
        "listening_detail": "Wake word detected, listening for command.",
        "status_prefix": "Status",
        "input_label": "Command",
        "send": "Send",
        "conversation": "Conversation",
        "you": "You",
        "assistant": "Assistant",
        "system": "System",
        "dashboard": "Dashboard",
        "clock": "Current Time",
        "device_state": "Device States",
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
        "habits": "User Habits (Coming Soon)",
        "queue": "Schedule Queue",
        "schedule_manager": "Schedule Manager",
        "refresh": "Refresh",
        "last_sync": "Last Sync",
        "no_data": "No data yet",
        "lang": "Language",
        "reply": "Reply",
        "coming_soon": "This feature is not wired yet. The slot is reserved in the UI.",
        "habits_hint": "View learned rules.",
        "habits_empty": "No learned rules yet",
        "habits_rules": "Learned Rules",
        "chat_hint": "Press Enter or click Send to chat.",
    },
}


WINDOW_TITLE_ASCII = "Smart Home Console"
WINDOW_TITLE_SUFFIXES = {
    "zh": {
        "家具狀態": "Device States",
        "使用者習慣（開發中）": "User Habits",
        "排程 Queue": "Schedule Queue",
    },
    "en": {
        "Device States": "Device States",
        "User Habits (Coming Soon)": "User Habits",
        "Schedule Queue": "Schedule Queue",
    },
}


class DashboardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.chat_limit = 20
        self.lang = tk.StringVar(value="zh")
        self.current_status = tk.StringVar(value="")
        self.time_text = tk.StringVar(value="")
        self.command_text = tk.StringVar(value="")
        self.reply_text = tk.StringVar(value="")

        self.runtime = build_runtime(mode="desktop", memory_keep=self.chat_limit, with_device=False)
        self.state = self.runtime.state
        self.memory = self.runtime.memory
        self.agent = self.runtime.agent
        self.schedule_path = Path(DATA_DIR) / "memory" / "schedules.json"
        self.rules_path = Path(RULES_FILE)
        self.chat_history: list[tuple[str, str]] = []
        self.speech_enabled = bool(SPEECH_ENABLED)
        self.wakeword_enabled = bool(WAKEWORD_ENABLED)
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
        self.zh_font_family, self.en_font_family = self._resolve_font_families()
        self.has_cjk_font = self.zh_font_family not in {"DejaVu Sans", "Noto Sans", "Liberation Sans", "Arial", "Helvetica", "Ubuntu"}
        self._active_font_family = self.zh_font_family if self.lang.get() == "zh" else self.en_font_family
        self._build_fonts()

        self._set_window_title()
        self.geometry("1040x620")
        self.minsize(900, 540)

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
        widgets = [
            getattr(self, "system_title", None),
            getattr(self, "lang_label", None),
            getattr(self, "status_label", None),
            getattr(self, "entry_input", None),
            getattr(self, "send_btn", None),
            getattr(self, "chat_box", None),
            getattr(self, "clock_label", None),
            getattr(self, "device_btn", None),
            getattr(self, "habits_btn", None),
            getattr(self, "queue_btn", None),
            getattr(self, "sync_label", None),
            getattr(self, "font_notice_label", None),
        ]
        for widget in widgets:
            if widget is None:
                continue
            if widget is self.system_title:
                widget.configure(font=self.font_title)
            elif widget is self.status_label:
                widget.configure(font=self.font_status)
            elif widget is self.chat_box:
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
        if hasattr(self, "entry_input"):
            self.entry_input.focus_set()

    def _set_status(self, state_text: str, detail_text: str) -> None:
        full_status = f"{self.tr('status_prefix')}: {state_text}"
        self.current_status.set(full_status)
        self.status_label.configure(text=full_status)
        self.status_detail_label.configure(text=self._ensure_text(detail_text))

    def _set_input_enabled(self, enabled: bool) -> None:
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
            _speak_async(result.spoken_reply)

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
        self.chat_box.tag_configure("speaker_user", foreground="#1d4ed8", font=self.font_chat_speaker, spacing1=4)
        self.chat_box.tag_configure("body_user", foreground="#0f172a", lmargin1=18, lmargin2=18, spacing3=8)
        self.chat_box.tag_configure("speaker_assistant", foreground="#047857", font=self.font_chat_speaker, spacing1=4)
        self.chat_box.tag_configure("body_assistant", foreground="#111827", lmargin1=18, lmargin2=18, spacing3=8)
        self.chat_box.tag_configure("speaker_system", foreground="#b45309", font=self.font_chat_speaker, spacing1=4)
        self.chat_box.tag_configure("body_system", foreground="#78350f", lmargin1=18, lmargin2=18, spacing3=8)

    def _format_device_state_content(self) -> str:
        return format_device_state_content(self.state.get_state(), self.tr, self._ensure_text)

    def _format_queue_content(self) -> str:
        return format_queue_content(self._read_schedule_queue(), self.tr, self._ensure_text)

    def _build_layout(self) -> None:
        wrapper = ttk.Frame(self, padding=12)
        wrapper.pack(fill=tk.BOTH, expand=True)

        top_bar = ttk.Frame(wrapper)
        top_bar.pack(fill=tk.X)

        self.system_title = tk.Label(top_bar, text=self._ensure_text(self.tr("system_ready")), anchor="w", font=self.font_title)
        self.system_title.pack(side=tk.LEFT)

        lang_group = ttk.Frame(top_bar)
        lang_group.pack(side=tk.RIGHT)
        self.lang_label = tk.Label(lang_group, text=f"{self._ensure_text(self.tr('lang'))}: ", font=self.font_normal)
        self.lang_label.pack(side=tk.LEFT)
        lang_picker = ttk.Combobox(lang_group, textvariable=self.lang, values=["zh", "en"], width=6, state="readonly")
        lang_picker.pack(side=tk.LEFT)
        lang_picker.bind("<<ComboboxSelected>>", self._on_language_change)

        body = ttk.Frame(wrapper)
        body.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, padding=(0, 0, 10, 0))
        left.grid(row=0, column=0, sticky="nsew")

        self.status_label = tk.Label(left, text="", anchor="w", font=self.font_status)
        self.status_label.pack(anchor="w", pady=(0, 12))

        self.status_detail_label = tk.Label(left, text="", anchor="w", justify=tk.LEFT, fg="#475569", font=self.font_normal)
        self.status_detail_label.pack(anchor="w", pady=(0, 10))

        self.font_notice_label = tk.Label(left, text="", anchor="w", fg="#b45309", font=self.font_normal)
        self.font_notice_label.pack(anchor="w", pady=(0, 8))

        self.chat_hint_label = tk.Label(left, text=self._ensure_text(self.tr("chat_hint")), anchor="w", fg="#475569", font=self.font_normal)
        self.chat_hint_label.pack(anchor="w", pady=(0, 8))

        cmd_frame = ttk.LabelFrame(left, text=self.tr("input_label"), padding=10)
        cmd_frame.pack(fill=tk.X)
        self.entry_input = tk.Entry(cmd_frame, textvariable=self.command_text, font=self.font_normal)
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_input.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(cmd_frame, text=self._ensure_text(self.tr("send")), command=self._on_send, font=self.font_normal)
        self.send_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.conversation_frame = ttk.LabelFrame(left, text=self.tr("conversation"), padding=10)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.chat_box = scrolledtext.ScrolledText(
            self.conversation_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=16,
            font=self.font_normal,
            relief=tk.FLAT,
            padx=8,
            pady=8,
        )
        self.chat_box.pack(fill=tk.BOTH, expand=True)
        self._configure_chat_tags()

        self._load_chat_history()
        if not self.chat_history:
            self.chat_history.append((self.tr("system"), self._ensure_text(self.tr("system_ready"))))
        self._render_chat_history()

        right = ttk.LabelFrame(body, text=self.tr("dashboard"), padding=10)
        self.dashboard_frame = right
        right.grid(row=0, column=1, sticky="nsew")

        self.clock_label = tk.Label(right, text="", anchor="w", font=self.font_normal)
        self.clock_label.pack(anchor="w")

        btns = ttk.Frame(right)
        btns.pack(fill=tk.X, pady=(10, 8))
        self.device_btn = tk.Button(btns, text=self._ensure_text(self.tr("device_state")), command=self._open_device_state, font=self.font_normal)
        self.device_btn.pack(fill=tk.X, pady=3)
        self.habits_btn = tk.Button(
            btns,
            text=self._ensure_text(self.tr("habits")),
            command=self._open_habits,
            font=self.font_normal,
        )
        self.habits_btn.pack(fill=tk.X, pady=3)
        self.habits_hint_label = tk.Label(right, text=self._ensure_text(self.tr("habits_hint")), anchor="w", justify=tk.LEFT, wraplength=250, fg="#6b7280", font=self.font_normal)
        self.habits_hint_label.pack(fill=tk.X, pady=(0, 8))
        self.queue_btn = tk.Button(btns, text=self._ensure_text(self.tr("queue")), command=self._open_queue, font=self.font_normal)
        self.queue_btn.pack(fill=tk.X, pady=3)

        self.sync_label = tk.Label(right, text="", anchor="w", font=self.font_normal)
        self.sync_label.pack(anchor="w", pady=(8, 0))

        self._apply_widget_fonts()

    def _set_boot_status(self) -> None:
        self._set_status(self.tr("idle"), self.tr("ready_detail"))
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
        self._apply_command_result(result)
        self._finish_command_flow()

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

    def _detect_wake_by_energy(self, timeout_seconds: int = 3) -> bool:
        if self._speech is None:
            return False
        device = getattr(self._speech, "device", "default")
        cmd = [
            "arecord", "-D", str(device), "-r", "16000", "-c", "1", "-f", "S16_LE", "-t", "raw",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception:
            return False

        threshold = 800
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
                if audioop.rms(data, 2) >= threshold:
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
                self._set_status_async(self.tr("waiting_wake_word"), self.tr("waiting_wake_word_detail"))
                if not self._wait_for_wake():
                    continue
                if self._voice_stop_event.is_set():
                    break

                self._set_status_async(self.tr("listening"), self.tr("listening_detail"))
                try:
                    spoken = self._speech.speech_to_text(duration=getattr(self._speech, "default_duration", 5)).strip()
                except Exception:
                    spoken = ""

                if not spoken:
                    continue

                self.after(0, lambda text=spoken: self._submit_command(text, self.tr("you")))

        self._voice_thread = threading.Thread(target=_voice_worker, daemon=True, name="gui-voice-loop")
        self._voice_thread.start()

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
        )

    def _open_habits(self) -> None:
        self._open_text_window(self._ensure_text(self.tr("habits")), self._format_habits_content())

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
        self.send_btn.configure(text=self._ensure_text(self.tr("send")))
        self.conversation_frame.configure(text=self._ensure_text(self.tr("conversation")))
        self.dashboard_frame.configure(text=self._ensure_text(self.tr("dashboard")))
        self.device_btn.configure(text=self._ensure_text(self.tr("device_state")))
        self.habits_btn.configure(text=self._ensure_text(self.tr("habits")))
        self.habits_hint_label.configure(text=self._ensure_text(self.tr("habits_hint")))
        self.queue_btn.configure(text=self._ensure_text(self.tr("queue")))
        self._load_chat_history()
        if not self.chat_history:
            self.chat_history.append((self.tr("system"), self._ensure_text(self.tr("system_ready"))))
        self._render_chat_history()
        self._set_boot_status()
        self._focus_input()


def run_gui() -> None:
    app = DashboardApp()
    app.mainloop()
