"""
GUI 互動量測腳本（全自動）
自動依序送出 TEST_COMMANDS，等每筆回應後再送下一筆，全部完成後自動關閉視窗並輸出報告。

使用方式 (在 project/ 根目錄執行):
    python scripts/eval_gui.py
    python scripts/eval_gui.py --out data/eval/gui_results.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.gui.app import DashboardApp as SmartHomeApp
from src.utils.config import DATA_DIR

# ---------------------------------------------------------------------------
# 從 CSV 讀取測試資料
# ---------------------------------------------------------------------------

_TEST_CSV = PROJECT_ROOT / "data" / "eval" / "gui_test.csv"


def _load_test_commands(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到測試資料：{csv_path}")
    commands: list[str] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cmd = row.get("command", "").strip()
            if cmd:
                commands.append(cmd)
    return commands

# 每筆指令回應後的等待間隔（秒），避免連發太快
_INTER_CMD_DELAY_MS = 1500


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

class _EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event_type: str, **kwargs: Any) -> None:
        self.events.append({"ts": time.time(), "event": event_type, **kwargs})


_log = _EventLog()
_DEVICE_STATE_FILE = DATA_DIR / "memory" / "device_state.json"


def _read_device_state_file() -> dict:
    try:
        raw = _DEVICE_STATE_FILE.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Auto-runner（event-driven，等回應後才送下一筆）
# ---------------------------------------------------------------------------

class _AutoRunner:
    def __init__(self, app: SmartHomeApp, commands: list[str]) -> None:
        self._app = app
        self._commands = list(commands)
        self._queue = list(commands)
        self._waiting = False   # True = 已送出，等 _apply 回來

    def start(self) -> None:
        self._app.after(1500, self._send_next)

    def _send_next(self) -> None:
        if not self._queue:
            total = len(self._commands)
            print(f"\n[AutoRunner] 所有 {total} 筆指令已完成，關閉視窗...")
            self._app.destroy()
            return
        cmd = self._queue.pop(0)
        idx = len(self._commands) - len(self._queue)
        total = len(self._commands)
        print(f"[AutoRunner] #{idx:02d}/{total}  送出：{cmd}")
        self._waiting = True
        self._app._submit_command(cmd, "auto")

    def on_command_done(self) -> None:
        if not self._waiting:
            return
        self._waiting = False
        # 等 _INTER_CMD_DELAY_MS 後送下一筆
        self._app.after(_INTER_CMD_DELAY_MS, self._send_next)


_runner: _AutoRunner | None = None


# ---------------------------------------------------------------------------
# Monkey-patch
# ---------------------------------------------------------------------------

_orig_submit = SmartHomeApp._submit_command
_orig_apply = SmartHomeApp._apply_command_result


def _patched_submit(self: SmartHomeApp, raw: str, speaker: str) -> None:
    ts = time.time()
    _log.record("command_sent", text=raw, ts_sent=ts)
    if not hasattr(self, "_eval_pending"):
        self._eval_pending = {}
    self._eval_pending[raw] = ts
    _orig_submit(self, raw, speaker)


def _patched_apply(self: SmartHomeApp, result: Any) -> None:
    ts_done = time.time()
    _orig_apply(self, result)

    pending = getattr(self, "_eval_pending", {})
    if pending:
        oldest_text, ts_sent = min(pending.items(), key=lambda x: x[1])
        latency_ms = (ts_done - ts_sent) * 1000
        pending.pop(oldest_text, None)
    else:
        oldest_text = ""
        latency_ms = None

    agent_state = self.app_state.get_state() if hasattr(self, "app_state") else {}
    file_state = _read_device_state_file()
    sync_ok = _check_state_sync(agent_state, file_state)
    actions = getattr(result, "actions_executed", None) or []

    _log.record(
        "command_done",
        text=oldest_text,
        latency_ms=round(latency_ms, 1) if latency_ms is not None else None,
        reply=str(getattr(result, "formatted_reply", ""))[:120],
        actions=actions,
        state_sync_ok=sync_ok,
        agent_state=agent_state,
        file_state=file_state,
    )

    if _runner is not None:
        _runner.on_command_done()


def _check_state_sync(agent_state: dict, file_state: dict) -> bool:
    if not file_state:
        return True

    def _normalise(d: dict) -> dict[str, str]:
        return {k.upper(): str(v).lower() for k, v in d.items()}

    a = _normalise(agent_state)
    f = _normalise(file_state)
    common = set(a) & set(f)
    if not common:
        return True
    return all(a[k] == f[k] for k in common)


SmartHomeApp._submit_command = _patched_submit      # type: ignore[method-assign]
SmartHomeApp._apply_command_result = _patched_apply  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _analyse(events: list[dict], out_path: Path) -> None:
    sent_events = [e for e in events if e["event"] == "command_sent"]
    done_events = [e for e in events if e["event"] == "command_done"]

    total_cmds = len(sent_events)
    latencies = [e["latency_ms"] for e in done_events if e.get("latency_ms") is not None]
    sync_results = [e["state_sync_ok"] for e in done_events]

    print("\n" + "═" * 58)
    print("  GUI 互動量測報告")
    print("═" * 58)

    print("\n── 操作步數與完成時間 ──────────────────────────────────")
    print(f"  總指令數 (步數): {total_cmds}")
    if done_events:
        first_ts = done_events[0]["ts"] - (done_events[0].get("latency_ms") or 0) / 1000
        last_ts = done_events[-1]["ts"]
        session_sec = last_ts - first_ts if last_ts > first_ts else 0
        avg_per_cmd = session_sec / len(done_events) if done_events else 0
        print(f"  測試時長: {session_sec:.1f} 秒")
        print(f"  平均每步耗時: {avg_per_cmd:.1f} 秒/步")
    else:
        print("  (無完成事件)")

    print("\n── UI 更新延遲 ─────────────────────────────────────────")
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        print(f"  平均: {avg_lat:.0f} ms")
        print(f"  最短: {min(latencies):.0f} ms")
        print(f"  最長: {max(latencies):.0f} ms")
        print(f"  樣本數: {len(latencies)}")
    else:
        print("  (無量測資料)")

    print("\n── 狀態同步一致率 ──────────────────────────────────────")
    if sync_results:
        sync_ok = sum(1 for v in sync_results if v)
        total_sync = len(sync_results)
        print(f"  一致: {sync_ok}/{total_sync}  ({100 * sync_ok / total_sync:.1f}%)")
        if sync_ok < total_sync:
            print("  不一致的事件：")
            for e in done_events:
                if not e.get("state_sync_ok"):
                    print(f"    指令: {e.get('text', '')[:60]}")
                    print(f"    agent_state: {e.get('agent_state')}")
                    print(f"    file_state : {e.get('file_state')}")
    else:
        print("  (無量測資料)")

    if done_events:
        print("\n── 各指令延遲明細 ──────────────────────────────────────")
        for i, e in enumerate(done_events, 1):
            lat = e.get("latency_ms")
            lat_str = f"{lat:.0f} ms" if lat is not None else "N/A"
            sync = "✅" if e.get("state_sync_ok") else "❌"
            text = e.get("text", "")[:40]
            print(f"  #{i:02d}  {lat_str:>8}  {sync}  {text}")

    print()

    summary = {
        "total_commands": total_cmds,
        "latency_ms": {
            "avg": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "min": round(min(latencies), 1) if latencies else None,
            "max": round(max(latencies), 1) if latencies else None,
            "samples": len(latencies),
        },
        "state_sync": {
            "ok": sum(1 for v in sync_results if v),
            "total": len(sync_results),
        },
        "events": events,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  結果已儲存 → {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/eval/gui_results.json")
    args = parser.parse_args()

    out_path = PROJECT_ROOT / args.out

    print("=" * 58)
    print("  GUI 自動量測模式")
    print("  視窗開啟後自動開始，全部完成後自動關閉")
    print("=" * 58)

    test_commands = _load_test_commands(_TEST_CSV)
    print(f"  讀取測試資料：{_TEST_CSV.name}  共 {len(test_commands)} 筆")

    app = SmartHomeApp()

    _runner = _AutoRunner(app, test_commands)
    _runner.start()

    app.mainloop()

    _analyse(_log.events, out_path)
