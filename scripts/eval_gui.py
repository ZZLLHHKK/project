"""
GUI 互動量測腳本
透過 monkey-patch SmartHomeApp 的關鍵方法，在正常使用過程中自動記錄：
  - UI 更新延遲（從送出指令到 _apply_command_result 被呼叫的毫秒數）
  - 狀態同步一致率（GUI 顯示的裝置狀態 vs device_state.json 實際內容）
  - 操作步數與完成時間（每條指令視為一步，記錄總步數與每步耗時）

使用方式 (在 project/ 根目錄執行):
    python scripts/eval_gui.py
    python scripts/eval_gui.py --out data/eval/gui_results.json

執行流程：
  1. 腳本啟動，GUI 視窗正常出現
  2. 你正常操作 GUI（說話 / 輸入指令）
  3. 關閉視窗後，腳本自動輸出量測報告
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 引入 GUI app ──────────────────────────────────────────────────────────────
from src.gui.app import DashboardApp as SmartHomeApp
from src.utils.config import DATA_DIR


# ---------------------------------------------------------------------------
# Event log (in-process shared list)
# ---------------------------------------------------------------------------

class _EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event_type: str, **kwargs: Any) -> None:
        self.events.append({
            "ts": time.time(),
            "event": event_type,
            **kwargs,
        })


_log = _EventLog()
_DEVICE_STATE_FILE = DATA_DIR / "memory" / "device_state.json"


def _read_device_state_file() -> dict:
    try:
        raw = _DEVICE_STATE_FILE.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Monkey-patch SmartHomeApp
# ---------------------------------------------------------------------------

_orig_submit = SmartHomeApp._submit_command
_orig_apply = SmartHomeApp._apply_command_result


def _patched_submit(self, raw: str, speaker: str) -> None:
    ts = time.time()
    _log.record("command_sent", text=raw, ts_sent=ts)
    # Store per-instance so _apply can compute latency
    if not hasattr(self, "_eval_pending"):
        self._eval_pending = {}
    self._eval_pending[raw] = ts
    _orig_submit(self, raw, speaker)


def _patched_apply(self, result: Any) -> None:
    ts_done = time.time()
    _orig_apply(self, result)

    # Latency
    pending = getattr(self, "_eval_pending", {})
    if pending:
        # Pick the oldest in-flight command
        oldest_text, ts_sent = min(pending.items(), key=lambda x: x[1])
        latency_ms = (ts_done - ts_sent) * 1000
        pending.pop(oldest_text, None)
    else:
        oldest_text = ""
        latency_ms = None

    # State sync check: compare agent state vs device_state.json
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


def _check_state_sync(agent_state: dict, file_state: dict) -> bool:
    """
    簡易同步判斷：比對 LED 與 FAN 的 on/off 狀態是否一致。
    agent_state 格式：{"LED_LIVING": "on", "FAN": "off", ...}
    file_state 格式：{"led_living": "on", ...} 或 {"LED_LIVING": "on", ...}
    """
    if not file_state:
        return True  # 檔案不存在時視為 OK（裝置未初始化）

    def _normalise(d: dict) -> dict[str, str]:
        return {k.upper(): str(v).lower() for k, v in d.items()}

    a = _normalise(agent_state)
    f = _normalise(file_state)

    # 只比對兩者都有的 key
    common = set(a) & set(f)
    if not common:
        return True
    for key in common:
        if a[key] != f[key]:
            return False
    return True


# Apply patches
SmartHomeApp._submit_command = _patched_submit  # type: ignore[method-assign]
SmartHomeApp._apply_command_result = _patched_apply  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _analyse(events: list[dict], out_path: Path | None) -> None:
    sent_events = [e for e in events if e["event"] == "command_sent"]
    done_events = [e for e in events if e["event"] == "command_done"]

    total_cmds = len(sent_events)
    latencies = [e["latency_ms"] for e in done_events if e.get("latency_ms") is not None]
    sync_results = [e["state_sync_ok"] for e in done_events]

    print("\n" + "═" * 58)
    print("  GUI 互動量測報告")
    print("═" * 58)

    # 操作步數與完成時間
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

    # UI 更新延遲
    print("\n── UI 更新延遲 ─────────────────────────────────────────")
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        max_lat = max(latencies)
        min_lat = min(latencies)
        print(f"  平均: {avg_lat:.0f} ms")
        print(f"  最短: {min_lat:.0f} ms")
        print(f"  最長: {max_lat:.0f} ms")
        print(f"  樣本數: {len(latencies)}")
    else:
        print("  (無量測資料)")

    # 狀態同步一致率
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

    # 各指令延遲明細
    if done_events:
        print("\n── 各指令延遲明細 ──────────────────────────────────────")
        for i, e in enumerate(done_events, 1):
            lat = e.get("latency_ms")
            lat_str = f"{lat:.0f} ms" if lat is not None else "N/A"
            sync = "✅" if e.get("state_sync_ok") else "❌"
            text = e.get("text", "")[:40]
            print(f"  #{i:02d}  {lat_str:>8}  {sync}  {text}")

    print()

    # Save JSON
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

    if out_path:
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
    print("  GUI 量測模式已啟動")
    print("  正常操作 GUI，關閉視窗後顯示量測報告")
    print("=" * 58)

    # Launch the app (blocks until window is closed)
    app = SmartHomeApp()
    app.mainloop()

    # After window closes, analyse
    _analyse(_log.events, out_path)
