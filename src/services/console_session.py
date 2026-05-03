from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from src.core.scheduler import ScheduleManager
from src.core.state_manager import StateManager
from src.devices.device_controller import DeviceController
from src.services.command_service import execute_text_command


class ConsoleSpeech:
    def speech_to_text(self, duration: int = 5) -> str:
        return ""

    def text_to_speech(self, text: str) -> None:
        print(f"[TTS] {text}")


def say(speech: Any, text: str, tts_enabled: bool) -> None:
    if tts_enabled and hasattr(speech, "text_to_speech"):
        try:
            speech.text_to_speech(text)
            return
        except Exception as exc:
            print(f"⚠️ TTS 播放失敗，改為文字輸出: {exc}")
    print(f"🔊 [回覆]: {text}")


def print_dashboard(state: StateManager) -> None:
    print("\n" + "=" * 40)
    print("🏠 [智慧家庭當前狀態面板]")
    print(f"🌡️  當前設定溫度: {state.temperature}°C (環境: {state.ambient_temp}°C)")
    print(f"💧 當前環境濕度: {state.ambient_humidity}%")
    print(f"💨 風扇狀態: {state.fan}")
    print(
        "💡 燈光狀態: "
        f"客廳({state.light.get('LIVING', 'off')}) | "
        f"廚房({state.light.get('KITCHEN', 'off')}) | "
        f"客房({state.light.get('GUEST', 'off')})"
    )
    if state.needs_clarification and state.clarification_message:
        print(f"❓ 待澄清: {state.clarification_message}")
    print("=" * 40 + "\n")


def read_environment(device: DeviceController) -> Tuple[Optional[int], Optional[int]]:
    temp: Optional[int] = None
    humidity: Optional[int] = None
    try:
        temp = device.get_temp()
    except Exception as exc:
        print(f"⚠️ 環境溫度讀取失敗: {exc}")
    try:
        humidity = device.get_humidity()
    except Exception as exc:
        print(f"⚠️ 環境濕度讀取失敗: {exc}")
    return temp, humidity


def is_wake_word(text: str) -> bool:
    clean = (text or "").strip().lower()
    wake_words = ["hi my pi", "my pi", "my pie", "hi", "開機", "在嗎", "醒來", "嗨"]
    return any(word in clean for word in wake_words)


def collect_text_input(speech: Any, is_standby: bool, use_speech: bool = True) -> Tuple[str, bool]:
    if is_standby:
        if use_speech:
            print("\n[🟡 待機中] 請說喚醒詞...", flush=True)
            try:
                text = speech.speech_to_text(duration=2)
                if text:
                    return text, True
            except Exception as exc:
                print(f"⚠️ 語音辨識失敗: {exc}")
                return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), False
        return input("[🟡 待機中] 請輸入喚醒詞（或 exit 離開）: ").strip(), True

    if use_speech:
        print("\n[🟢 聆聽中] 🗣️ 請說指令...", flush=True)
        try:
            text = speech.speech_to_text(duration=getattr(speech, "default_duration", 5))
            if text:
                return text, True
        except Exception as exc:
            print(f"⚠️ 語音辨識失敗: {exc}")
            return input("[🟢 聆聽中] 請輸入指令（或 exit 離開）: ").strip(), False
    return input("[🟢 聆聽中] 請輸入指令（或 exit 離開）: ").strip(), True


def print_controls() -> None:
    print("\n[控制指令]")
    print("  /help               顯示控制指令")
    print("  /k                  快速切到鍵盤命令輸入")
    print("  /v                  快速切到語音命令輸入")
    print("  /mode voice         命令輸入改為語音")
    print("  /mode keyboard      命令輸入改為鍵盤")
    print("  /rec <秒數>         設定語音錄音秒數（1~15）")
    print("  /voice              顯示目前語音模型")
    print("  /voice <模型路徑>   切換 Piper 語音模型 (.onnx)")
    print("  /status             顯示目前輸入模式與錄音秒數")
    print("  /standby            立即進入待機")
    print("  /exit               結束程式")
    print("\n[排程指令]")
    print("  /sched list                        查看所有排程")
    print("  /sched add <HH:MM> fan on|off      新增風扇排程")
    print("  /sched add <HH:MM> led <位置> on|off  新增燈光排程（living/kitchen/guest）")
    print("  /sched add <HH:MM> temp <度數>     新增溫度排程")
    print("  /sched del <id>                    刪除排程")
    print("  /sched toggle <id>                 啟用/停用排程")


def print_schedules(scheduler: ScheduleManager) -> None:
    rules = scheduler.list_all()
    print("\n" + "═" * 70)
    print("📅 [排程列表]")
    print("═" * 70)

    if not rules:
        print("  （目前沒有任何排程）")
    else:
        print(f"{'狀態':<4} {'ID':<9} {'時間':<6} {'動作':<25} {'上次觸發':<15} 結果")
        print("─" * 70)

        for r in rules:
            status = "✅" if r.get("enabled", True) else "⏸️"
            rule_id = r["id"]
            time_str = f"{r['hour']:02d}:{r['minute']:02d}"

            name = r.get("name", "")
            if isinstance(name, str) and name.startswith(f"{time_str} "):
                name = name[len(time_str) + 1 :].strip()

            last = r.get("last_triggered") or "從未觸發"
            result = r.get("last_result") or "-"
            print(f"{status:<4} [{rule_id}] {time_str}  {name:<25} {last:<15} {result}")

    print("═" * 70 + "\n")


def parse_sched_add(parts: list[str]) -> Optional[Tuple[int, int, list[dict[str, Any]], str]]:
    if len(parts) < 4:
        return None
    time_str = parts[2]
    try:
        hh, mm = time_str.split(":")
        hour, minute = int(hh), int(mm)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
    except Exception:
        return None

    device = parts[3].lower()

    if device == "fan":
        if len(parts) < 5:
            return None
        state = parts[4].lower()
        if state not in ("on", "off"):
            return None
        actions = [{"type": "FAN", "state": state}]
        name = f"{hour:02d}:{minute:02d} 風扇{'開' if state == 'on' else '關'}"
        return hour, minute, actions, name

    if device == "led":
        if len(parts) < 6:
            return None
        loc_map = {
            "living": "LIVING",
            "kitchen": "KITCHEN",
            "guest": "GUEST",
            "客廳": "LIVING",
            "廚房": "KITCHEN",
            "客房": "GUEST",
        }
        loc = loc_map.get(parts[4].lower())
        if loc is None:
            return None
        state = parts[5].lower()
        if state not in ("on", "off"):
            return None
        loc_label = {"LIVING": "客廳", "KITCHEN": "廚房", "GUEST": "客房"}.get(loc, loc)
        actions = [{"type": "LED", "location": loc, "state": state}]
        name = f"{hour:02d}:{minute:02d} {loc_label}燈{'開' if state == 'on' else '關'}"
        return hour, minute, actions, name

    if device == "temp":
        if len(parts) < 5:
            return None
        try:
            val = int(parts[4])
        except Exception:
            return None
        actions = [{"type": "SET_TEMP", "value": val}]
        name = f"{hour:02d}:{minute:02d} 溫度設定 {val}°C"
        return hour, minute, actions, name

    return None


def _schedule_ticker(
    scheduler: ScheduleManager,
    device: Any,
    speech: Any,
    tts_enabled: bool,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            for fired in scheduler.tick(device):
                rule_name = fired["rule"].get("name", "排程")
                ok = "✅" if fired["success"] else "⚠️"
                print(f"\n{ok} [排程觸發] {rule_name} — {fired['result']}", flush=True)
                say(speech, f"排程執行：{rule_name}", tts_enabled)
        except Exception as exc:
            print(f"\n⚠️ [排程背景執行錯誤]: {exc}", flush=True)
        stop_event.wait(50)


def detect_capture_status(speech: Any) -> str:
    if hasattr(speech, "describe_capture_path"):
        try:
            return str(speech.describe_capture_path())
        except Exception:
            return "unknown"
    return "keyboard(console)"


class ConsoleSessionService:
    def __init__(
        self,
        *,
        state: StateManager,
        agent: Any,
        speech: Any,
        device: DeviceController,
        speech_enabled: bool,
        tts_enabled: bool,
        sensors_enabled: bool,
        scheduler: ScheduleManager | None = None,
    ) -> None:
        self.state = state
        self.agent = agent
        self.speech = speech
        self.device = device
        self.speech_enabled = speech_enabled
        self.tts_enabled = tts_enabled
        self.sensors_enabled = sensors_enabled
        self.scheduler = scheduler
        self._schedule_stop_event = threading.Event()
        self._schedule_thread: threading.Thread | None = None

        self.is_standby = True
        self.use_command_speech_input = speech_enabled
        self.command_record_seconds = max(1, min(15, int(os.environ.get("COMMAND_RECORD_SECONDS", "5"))))
        if hasattr(self.speech, "default_duration"):
            try:
                self.speech.default_duration = self.command_record_seconds
            except Exception:
                pass

    def run(self) -> None:
        print("✅ 系統準備就緒！")
        say(self.speech, "系統已經啟動，隨時可以叫我。", self.tts_enabled)
        print_dashboard(self.state)
        print_controls()

        capture_status = detect_capture_status(self.speech)
        print(
            f"[啟動狀態] standby_input=keyboard, "
            f"command_input={'voice' if self.use_command_speech_input else 'keyboard'}, "
            f"capture={capture_status}, rec={self.command_record_seconds}s"
        )

        error_count = 0
        max_errors = 3

        if self.scheduler is not None:
            self._schedule_thread = threading.Thread(
                target=_schedule_ticker,
                args=(self.scheduler, self.device, self.speech, self.tts_enabled, self._schedule_stop_event),
                daemon=True,
                name="schedule-ticker",
            )
            self._schedule_thread.start()

        try:
            while True:
                try:
                    if self.sensors_enabled:
                        self._update_environment()

                    user_input = self._collect_input()
                    clean_input = (user_input or "").strip()
                    if not clean_input:
                        continue

                    if self._handle_control_command(clean_input):
                        if clean_input.lower() in ("/exit", "/quit"):
                            break
                        continue

                    if clean_input.lower() in ["exit", "quit"]:
                        say(self.speech, "系統關閉中，再見。", self.tts_enabled)
                        break

                    if self.is_standby:
                        if is_wake_word(clean_input):
                            self.is_standby = False
                            say(self.speech, "我在，請說！", self.tts_enabled)
                        continue

                    if self._handle_agent_turn(clean_input):
                        break

                    error_count = 0

                except KeyboardInterrupt:
                    say(self.speech, "強制中斷，系統關閉中。", self.tts_enabled)
                    break
                except Exception as exc:
                    error_count += 1
                    print(f"\n❌ 發生未預期錯誤: {exc}")
                    if error_count >= max_errors:
                        print("❌ 錯誤過多，系統停止。")
                        break
                    time.sleep(1)
        finally:
            self._schedule_stop_event.set()

    def _update_environment(self) -> None:
        env_temp, env_hum = read_environment(self.device)
        if env_temp is not None:
            self.state.ambient_temp = env_temp
        if env_hum is not None:
            self.state.ambient_humidity = env_hum

    def _collect_input(self) -> str:
        if self.is_standby:
            user_input, _ = collect_text_input(self.speech, is_standby=True, use_speech=False)
            return user_input

        user_input, speech_ok = collect_text_input(
            self.speech,
            is_standby=self.is_standby,
            use_speech=self.use_command_speech_input,
        )
        if not speech_ok and self.use_command_speech_input:
            self.use_command_speech_input = False
            print("⚠️ 命令語音辨識失敗，已自動降級為鍵盤輸入模式。")
        return user_input

    def _handle_control_command(self, clean_input: str) -> bool:
        lower_input = clean_input.lower()
        if not lower_input.startswith("/"):
            return False

        if lower_input == "/help":
            print_controls()
            return True
        if lower_input == "/k":
            self.use_command_speech_input = False
            print("⌨️ 命令輸入已快速切換為鍵盤模式。")
            return True
        if lower_input == "/v":
            self.use_command_speech_input = True
            print("🎙️ 命令輸入已快速切換為語音模式。")
            return True
        if lower_input in ("/exit", "/quit"):
            say(self.speech, "系統關閉中，再見。", self.tts_enabled)
            return True
        if lower_input == "/voice":
            current_voice = os.environ.get("TTS_MODEL_PATH", "(default) data/models/voice.onnx")
            print(f"[語音模型] {current_voice}")
            return True
        if lower_input.startswith("/voice "):
            model_path = clean_input.split(maxsplit=1)[1].strip()
            if not model_path:
                print("⚠️ 用法: /voice /path/to/model.onnx")
                return True
            path = Path(model_path)
            if not path.exists():
                print(f"⚠️ 找不到模型檔: {model_path}")
                return True
            if path.suffix.lower() != ".onnx":
                print("⚠️ 模型副檔名需為 .onnx")
                return True
            os.environ["TTS_MODEL_PATH"] = str(path)
            print(f"🗣️ 已切換語音模型: {path}")
            return True
        if lower_input == "/status":
            mode_text = "voice" if self.use_command_speech_input else "keyboard"
            capture_status = detect_capture_status(self.speech)
            print(f"[狀態] standby={self.is_standby}, command_input={mode_text}, capture={capture_status}, rec={self.command_record_seconds}s")
            return True
        if lower_input == "/standby":
            self.is_standby = True
            print("💤 已切換到待機模式。")
            return True
        if lower_input.startswith("/mode "):
            target = lower_input.split(maxsplit=1)[1].strip()
            if target == "voice":
                self.use_command_speech_input = True
                print("🎙️ 命令輸入已切換為語音模式。")
            elif target == "keyboard":
                self.use_command_speech_input = False
                print("⌨️ 命令輸入已切換為鍵盤模式。")
            else:
                print("⚠️ 用法: /mode voice 或 /mode keyboard")
            return True
        if lower_input.startswith("/rec "):
            raw = lower_input.split(maxsplit=1)[1].strip()
            try:
                seconds = int(raw)
                self.command_record_seconds = max(1, min(15, seconds))
                if hasattr(self.speech, "default_duration"):
                    self.speech.default_duration = self.command_record_seconds
                print(f"⏱️ 命令錄音秒數已設定為 {self.command_record_seconds}s")
            except Exception:
                print("⚠️ 用法: /rec 3（秒數範圍 1~15）")
            return True

        if lower_input.startswith("/sched"):
            if self.scheduler is None:
                print("⚠️ Scheduler 尚未啟用。")
                return True
            parts = clean_input.split()
            sub = parts[1].lower() if len(parts) > 1 else ""

            if sub == "list":
                print_schedules(self.scheduler)
                return True

            if sub == "add":
                parsed = parse_sched_add(parts)
                if parsed is None:
                    print("⚠️ 用法範例:")
                    print("  /sched add 22:00 fan on")
                    print("  /sched add 07:00 led living on")
                    print("  /sched add 18:00 temp 26")
                    return True
                hour, minute, actions, name = parsed
                rule = self.scheduler.add(hour, minute, actions, name, recurrence="daily")
                if rule is None:
                    print("⚠️ 排程新增失敗（可能衝突或達上限）。")
                    return True
                print(f"✅ 已新增排程 [{rule['id']}]: {name}")
                return True

            if sub == "del":
                if len(parts) < 3:
                    print("⚠️ 用法: /sched del <id>")
                    return True
                if self.scheduler.delete(parts[2]):
                    print(f"✅ 已刪除排程 {parts[2]}")
                else:
                    print(f"⚠️ 找不到排程 {parts[2]}")
                return True

            if sub == "toggle":
                if len(parts) < 3:
                    print("⚠️ 用法: /sched toggle <id>")
                    return True
                result = self.scheduler.toggle(parts[2])
                if result is None:
                    print(f"⚠️ 找不到排程 {parts[2]}")
                else:
                    status = "啟用" if result else "停用"
                    print(f"✅ 排程 {parts[2]} 已{status}")
                return True

            print("⚠️ 用法: /sched list|add|del|toggle")
            return True

        print("⚠️ 未知控制指令，輸入 /help 查看可用指令。")
        return True

    def _handle_agent_turn(self, clean_input: str) -> bool:
        print("\n🧠 Agent 思考中...")
        result = execute_text_command(self.agent, clean_input)

        if result.error:
            print(f"⚠️ [系統錯誤碼]: {result.error}")
        print(f"🔊 [語音回覆]: {result.raw_reply}")
        say(self.speech, result.raw_reply, self.tts_enabled)

        if result.should_shutdown:
            return True

        print_dashboard(self.state)
        if result.should_standby:
            self.is_standby = True
            print("💤 === 系統進入待機模式 ===")
        return False