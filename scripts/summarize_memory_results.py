"""
Phase 4 Memory Results Summary
讀取 eval_memory.py 產出的 JSON，輸出兩份 CSV：
  - memory_summary.csv  : 各量測指標的通過率彙總
  - memory_details.csv  : 每一筆測試案例的詳細結果

Usage (在 project/ 根目錄執行):
    python scripts/summarize_memory_results.py
    python scripts/summarize_memory_results.py --in data/eval/memory_results.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "N/A"
    return f"{100 * n / d:.1f}%"


def _rate(n: int, d: int) -> float | None:
    if d == 0:
        return None
    return round(100 * n / d, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", default="data/eval/memory_results.json")
    parser.add_argument("--out-dir", default="data/eval")
    args = parser.parse_args()

    in_path = PROJECT_ROOT / args.infile
    out_dir = PROJECT_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        print(f"找不到結果檔：{in_path}")
        print("請先執行 python scripts/eval_memory.py")
        return

    results: list[dict] = json.loads(in_path.read_text(encoding="utf-8"))
    active = [r for r in results if not r.get("skipped")]

    # ── 彙總指標計算 ──────────────────────────────────────────────────────────

    summary_rows: list[dict] = []

    def _add(category: str, metric: str, passed: int, total: int,
             note: str = "") -> None:
        summary_rows.append({
            "category": category,
            "metric": metric,
            "passed": passed,
            "total": total,
            "pass_rate": _pct(passed, total),
            "note": note,
        })

    # 整體
    counted = [r for r in active if r.get("passed") is not None]
    p_all = sum(1 for r in counted if r["passed"])
    _add("整體", "總通過率", p_all, len(counted))

    # 各序列
    seqs: dict[str, list[dict]] = {}
    for r in active:
        seqs.setdefault(r.get("sequence_id", "?"), []).append(r)
    for sid in sorted(seqs):
        rows = [r for r in seqs[sid] if r.get("passed") is not None]
        p = sum(1 for r in rows if r["passed"])
        _add("各序列通過率", sid, p, len(rows))

    # 習慣觸發成功率
    trigger_rows = [
        r for r in active
        if r.get("phase") in ("after_rule", "after_update", "multi_rule")
        and r.get("expected_result") == "success"
        and r.get("passed") is not None
    ]
    tp = sum(1 for r in trigger_rows if r["passed"])
    _add("記憶功能", "習慣觸發成功率", tp, len(trigger_rows),
         "after_rule / after_update / multi_rule 階段")

    # 記憶前後比較 (SEQ_04)
    before_rows = [
        r for r in active
        if r.get("sequence_id") == "SEQ_04"
        and r.get("phase") == "before_rule"
        and r.get("passed") is not None
    ]
    after_rows_04 = [
        r for r in active
        if r.get("sequence_id") == "SEQ_04"
        and r.get("phase") == "after_rule"
        and r.get("passed") is not None
    ]
    b_ok = sum(1 for r in before_rows if r["passed"])
    a_ok = sum(1 for r in after_rows_04 if r["passed"])
    _add("記憶功能", "記憶前正確率（不觸發）", b_ok, len(before_rows), "SEQ_04 before_rule")
    _add("記憶功能", "記憶後正確率（應觸發）", a_ok, len(after_rows_04), "SEQ_04 after_rule")

    if before_rows and after_rows_04:
        b_rate = _rate(b_ok, len(before_rows)) or 0
        a_rate = _rate(a_ok, len(after_rows_04)) or 0
        diff = round(a_rate - b_rate, 1)
        summary_rows.append({
            "category": "記憶功能",
            "metric": "記憶前後成功率差異",
            "passed": "",
            "total": "",
            "pass_rate": f"{diff:+.1f}%",
            "note": "記憶後 − 記憶前",
        })

    # 規則學習 / 刪除
    for er, label in [("rule_saved", "規則學習成功率"), ("rule_deleted", "規則刪除成功率")]:
        rows_er = [r for r in active if r.get("expected_result") == er and r.get("passed") is not None]
        p = sum(1 for r in rows_er if r["passed"])
        _add("記憶功能", label, p, len(rows_er))

    # 排程功能
    sched_labels = {
        "schedule_saved": "排程新增正確率",
        "list_returned": "排程查詢正確率",
        "schedule_deleted": "排程刪除正確率",
        "schedule_conflict": "衝突偵測正確率",
        "schedule_fail": "上限拒絕正確率",
    }
    for er, label in sched_labels.items():
        rows_er = [r for r in active if r.get("expected_result") == er and r.get("passed") is not None]
        if rows_er:
            p = sum(1 for r in rows_er if r["passed"])
            _add("排程功能", label, p, len(rows_er))

    # 定時偏差 (SEQ_09)
    timing = [r for r in results if r.get("sequence_id") == "SEQ_09"]
    if timing and not any(r.get("reason") == "skipped" for r in timing):
        dev_row = next((r for r in timing if r.get("deviation_sec") is not None), None)
        if dev_row:
            summary_rows.append({
                "category": "排程功能",
                "metric": "定時執行偏差 (秒)",
                "passed": "",
                "total": "",
                "pass_rate": f"{dev_row['deviation_sec']:.0f}s",
                "note": f"目標 {dev_row.get('target_time','')} / 實際 {dev_row.get('exec_time','')}",
            })
        t_ok = sum(1 for r in timing if r.get("passed") is True)
        _add("排程功能", "定時測試通過率", t_ok, len(timing), "SEQ_09")
    else:
        summary_rows.append({
            "category": "排程功能",
            "metric": "定時執行偏差 (秒)",
            "passed": "",
            "total": "",
            "pass_rate": "N/A",
            "note": "SEQ_09 未執行或已跳過",
        })

    # ── 寫入 memory_summary.csv ───────────────────────────────────────────────

    summary_path = out_dir / "memory_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "metric", "passed", "total", "pass_rate", "note"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Summary -> {summary_path}")

    # ── 寫入 memory_details.csv ───────────────────────────────────────────────

    detail_fields = [
        "test_id", "sequence_id", "phase", "expected_result",
        "passed", "reason", "actual_reply", "note",
    ]
    details_path = out_dir / "memory_details.csv"
    with details_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "test_id": r.get("test_id", ""),
                "sequence_id": r.get("sequence_id", ""),
                "phase": r.get("phase", ""),
                "expected_result": r.get("expected_result", ""),
                "passed": "PASS" if r.get("passed") is True
                          else ("FAIL" if r.get("passed") is False
                          else "SKIP"),
                "reason": r.get("reason", ""),
                "actual_reply": str(r.get("actual_reply", ""))[:120],
                "note": r.get("note", ""),
            })

    print(f"Details -> {details_path}")

    # ── 終端機預覽 ────────────────────────────────────────────────────────────

    print("\n" + "─" * 58)
    print(f"{'量測指標':<28} {'通過/總數':>10} {'通過率':>8}")
    print("─" * 58)
    for row in summary_rows:
        if row["passed"] == "":
            print(f"  {row['metric']:<26} {'':>10} {row['pass_rate']:>8}  {row['note']}")
        else:
            frac = f"{row['passed']}/{row['total']}"
            print(f"  {row['metric']:<26} {frac:>10} {row['pass_rate']:>8}")
    print("─" * 58)


if __name__ == "__main__":
    main()
