"""
GUI 互動量測結果整理
讀取 eval_gui.py 產出的 gui_results.json，輸出兩份 CSV：
  - gui_summary.csv  : 各量測指標彙總
  - gui_details.csv  : 每一筆指令的詳細延遲與同步結果

Usage (在 project/ 根目錄執行):
    python scripts/summarize_gui_results.py
    python scripts/summarize_gui_results.py --in data/eval/gui_results.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", default="data/eval/gui_results.json")
    parser.add_argument("--out-dir", default="data/eval")
    args = parser.parse_args()

    in_path = PROJECT_ROOT / args.infile
    out_dir = PROJECT_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        print(f"找不到結果檔：{in_path}")
        print("請先執行 python scripts/eval_gui.py")
        return

    data: dict = json.loads(in_path.read_text(encoding="utf-8"))
    events: list[dict] = data.get("events", [])
    done_events = [e for e in events if e["event"] == "command_done"]
    total_cmds = data.get("total_commands", len([e for e in events if e["event"] == "command_sent"]))

    latencies = [e["latency_ms"] for e in done_events if e.get("latency_ms") is not None]
    sync_results = [e["state_sync_ok"] for e in done_events]
    sync_ok = sum(1 for v in sync_results if v)

    # ── gui_summary.csv ───────────────────────────────────────────────────────

    summary_rows = []

    # 操作步數
    summary_rows.append({
        "category": "操作步數與完成時間",
        "metric": "總指令數（步數）",
        "value": total_cmds,
        "unit": "步",
        "note": "",
    })

    if done_events:
        first_ts = done_events[0]["ts"] - (done_events[0].get("latency_ms") or 0) / 1000
        last_ts = done_events[-1]["ts"]
        session_sec = round(last_ts - first_ts, 1) if last_ts > first_ts else 0
        avg_per_cmd = round(session_sec / len(done_events), 1) if done_events else 0
        summary_rows.append({
            "category": "操作步數與完成時間",
            "metric": "測試時長",
            "value": session_sec,
            "unit": "秒",
            "note": "",
        })
        summary_rows.append({
            "category": "操作步數與完成時間",
            "metric": "平均每步耗時",
            "value": avg_per_cmd,
            "unit": "秒/步",
            "note": "",
        })

    # UI 更新延遲
    if latencies:
        avg_lat = round(sum(latencies) / len(latencies), 1)
        summary_rows.append({
            "category": "UI 更新延遲",
            "metric": "平均延遲",
            "value": avg_lat,
            "unit": "ms",
            "note": f"樣本數 {len(latencies)}",
        })
        summary_rows.append({
            "category": "UI 更新延遲",
            "metric": "最短延遲",
            "value": round(min(latencies), 1),
            "unit": "ms",
            "note": "",
        })
        summary_rows.append({
            "category": "UI 更新延遲",
            "metric": "最長延遲",
            "value": round(max(latencies), 1),
            "unit": "ms",
            "note": "",
        })

    # 狀態同步一致率
    total_sync = len(sync_results)
    sync_rate = round(100 * sync_ok / total_sync, 1) if total_sync else 0
    summary_rows.append({
        "category": "狀態同步一致率",
        "metric": "同步一致率",
        "value": sync_rate,
        "unit": "%",
        "note": f"{sync_ok}/{total_sync}",
    })

    summary_path = out_dir / "gui_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "metric", "value", "unit", "note"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Summary -> {summary_path}")

    # ── gui_details.csv ───────────────────────────────────────────────────────

    detail_rows = []
    for i, e in enumerate(done_events, 1):
        detail_rows.append({
            "step": i,
            "command": e.get("text", ""),
            "latency_ms": e.get("latency_ms", ""),
            "state_sync": "PASS" if e.get("state_sync_ok") else "FAIL",
            "reply": str(e.get("reply", ""))[:100],
        })

    details_path = out_dir / "gui_details.csv"
    with details_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["step", "command", "latency_ms", "state_sync", "reply"])
        writer.writeheader()
        writer.writerows(detail_rows)

    print(f"Details -> {details_path}")

    # ── 終端機預覽 ────────────────────────────────────────────────────────────

    print("\n" + "─" * 50)
    print(f"  {'量測指標':<22} {'數值':>10} {'單位':<8}")
    print("─" * 50)
    for row in summary_rows:
        print(f"  {row['metric']:<22} {str(row['value']):>10} {row['unit']:<8}  {row['note']}")
    print("─" * 50)


if __name__ == "__main__":
    main()
