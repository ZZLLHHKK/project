from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable

from src.services.command_service import execute_text_command

logger = logging.getLogger(__name__)


class SchedulerRuntime:
    _instance: "SchedulerRuntime | None" = None
    _class_lock = threading.RLock()

    def __init__(
        self,
        root: Any,
        agent: Any,
        lang_getter: Callable[[], str | None] | None,
        gui_callback: Callable[[str, str], None] | None,
        poll_interval_seconds: int = 10,
    ) -> None:
        self.root = root
        self.agent = agent
        self.lang_getter = lang_getter
        self.gui_callback = gui_callback
        self.poll_interval_seconds = max(1, int(poll_interval_seconds))
        self.scheduler = getattr(agent, "scheduler", None)

        self._runtime_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executed_today: dict[str, str] = {}

    @classmethod
    def start(
        cls,
        root: Any,
        agent: Any,
        lang_getter: Callable[[], str | None] | None = None,
        gui_callback: Callable[[str, str], None] | None = None,
    ) -> "SchedulerRuntime":
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls(
                    root=root,
                    agent=agent,
                    lang_getter=lang_getter,
                    gui_callback=gui_callback,
                    poll_interval_seconds=10,
                )
            else:
                cls._instance.root = root
                cls._instance.agent = agent
                cls._instance.lang_getter = lang_getter
                cls._instance.gui_callback = gui_callback
                cls._instance.scheduler = getattr(agent, "scheduler", None)

            cls._instance._ensure_running()
            return cls._instance

    @classmethod
    def stop(cls) -> None:
        with cls._class_lock:
            instance = cls._instance
            cls._instance = None
        if instance is not None:
            instance._stop()

    def _ensure_running(self) -> None:
        with self._runtime_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="SchedulerRuntimeThread",
                daemon=True,
            )
            self._thread.start()

    def _stop(self) -> None:
        thread: threading.Thread | None
        with self._runtime_lock:
            self._stop_event.set()
            thread = self._thread
            self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=3)

    def _resolve_language(self) -> str | None:
        if callable(self.lang_getter):
            try:
                return self.lang_getter()
            except Exception as exc:
                logger.warning("scheduler_runtime lang_getter failed: %s", exc)
                return None
        return None

    def _extract_reply(self, result: Any) -> str:
        raw_reply = getattr(result, "raw_reply", None)
        if raw_reply:
            return str(raw_reply)

        reply = getattr(result, "reply", None)
        if reply:
            return str(reply)

        payload = getattr(result, "payload", None)
        if isinstance(payload, dict):
            payload_reply = payload.get("reply")
            if payload_reply:
                return str(payload_reply)

        return ""

    def _already_executed_today(self, schedule: dict[str, Any], today: str) -> bool:
        schedule_id = str(schedule.get("id") or "")
        if not schedule_id:
            return False

        with self._runtime_lock:
            if self._executed_today.get(schedule_id) == today:
                return True

        last_executed = str(schedule.get("last_executed") or "")
        if last_executed == today:
            with self._runtime_lock:
                self._executed_today[schedule_id] = today
            return True

        return False

    def _mark_executed_today(self, schedule_id: str, today: str) -> None:
        if not schedule_id:
            return
        with self._runtime_lock:
            self._executed_today[schedule_id] = today

    def _sync_dht11(self) -> None:
        try:
            device_controller = getattr(self.agent, "device_controller", None)
            state = getattr(self.agent, "state", None)
            if device_controller is None or state is None:
                return
            t = device_controller.get_temp()
            h = device_controller.get_humidity()
            if t is not None:
                state.ambient_temp = int(t)
            if h is not None:
                state.ambient_humidity = round(h)
        except Exception as exc:
            logger.debug("dht11 sync failed: %s", exc)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._sync_dht11()
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            try:
                if self.scheduler is None:
                    due_schedules: list[dict[str, Any]] = []
                else:
                    due_schedules = self.scheduler.get_due_schedules(now)
                    if not isinstance(due_schedules, list):
                        due_schedules = []
            except Exception as exc:
                logger.error("scheduler_runtime get_due_schedules failed: %s", exc, exc_info=True)
                due_schedules = []

            for sched in due_schedules:
                if self._stop_event.is_set():
                    break
                if not isinstance(sched, dict):
                    continue
                if self._already_executed_today(sched, today):
                    continue

                schedule_id = str(sched.get("id") or "")
                sched_name = str(sched.get("name") or "").strip()
                actions = sched.get("actions") or []
                recurrence = str(sched.get("recurrence") or "daily")

                try:
                    device_controller = getattr(self.agent, "device_controller", None)
                    if device_controller is not None and actions:
                        results = device_controller.execute_actions(actions)
                        state = getattr(self.agent, "state", None)
                        if state is not None:
                            state.update_from_actions([r for r in results if r.get("success")])
                        lang = self._resolve_language() or "zh"
                        reply = "已執行排程：" + sched_name if lang != "en" else "Schedule executed: " + sched_name
                    else:
                        result = execute_text_command(
                            self.agent,
                            sched_name,
                            lang=self._resolve_language(),
                        )
                        reply = self._extract_reply(result)

                    if self.scheduler is not None and schedule_id:
                        self.scheduler.mark_schedule_executed(schedule_id, now)
                        if recurrence == "once":
                            self.scheduler.delete(schedule_id)
                    self._mark_executed_today(schedule_id, today)

                    if self.root is not None and callable(self.gui_callback):
                        self.root.after(0, self.gui_callback, sched_name, reply)
                except Exception as exc:
                    logger.error(
                        "scheduler_runtime execute failed (id=%s, name=%s): %s",
                        schedule_id,
                        sched_name,
                        exc,
                        exc_info=True,
                    )

            self._stop_event.wait(self.poll_interval_seconds)
