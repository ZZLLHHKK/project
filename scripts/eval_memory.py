"""
Phase 4 Memory Evaluation Script
執行 memory_test_cases.csv 中的每一筆測試，量測：
  - 習慣觸發成功率
  - 記憶前後成功率差異 (SEQ_04)
  - 排程新增 / 刪除 / 衝突偵測 / 上限拒絕正確率
  - 定時執行偏差 (SEQ_09, 預設跳過)

Usage (在 project/ 根目錄執行):
    python scripts/eval_memory.py
    python scripts/eval_memory.py --skip-timing          # 跳過等待 SEQ_09
    python scripts/eval_memory.py --out results/mem.json # 自訂輸出路徑
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.scheduler import ScheduleManager
from src.utils.config import RULES_FILE, SHORT_TERM


# ---------------------------------------------------------------------------
# Precondition helpers
# ---------------------------------------------------------------------------

def _reset_rules(memory: MemoryAgent) -> None:
    Path(RULES_FILE).write_text(
        json.dumps({"rules": []}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    st = Path(SHORT_TERM)
    if st.exists():
        st.write_text(
            json.dumps({"interactions": [], "updated_at": int(time.time())},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _reset_schedules(scheduler: ScheduleManager) -> None:
    scheduler._write([])


def _apply_precondition(cond: str, memory: MemoryAgent, scheduler: ScheduleManager) -> None:
    if cond == "reset_rules":
        _reset_rules(memory)
    elif cond == "reset_schedules":
        _reset_schedules(scheduler)
    elif cond.startswith("add_rule:"):
        pair = cond[len("add_rule:"):]
        if "=" in pair:
            trigger, meaning = pair.split("=", 1)
            memory.save_rule(trigger.strip(), meaning.strip())
    elif cond.startswith("delete_rule:"):
        memory.delete_rule(cond[len("delete_rule:"):].strip())


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _parse_actions(raw: str) -> list[dict]:
    raw = raw.strip()
    if not raw or raw in ("-", "[]", ""):
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _actions_match(actual: list[dict], expected: list[dict]) -> bool:
    def _key(a: dict) -> str:
        return json.dumps({k: v for k, v in a.items() if k != "success"}, sort_keys=True, ensure_ascii=False)
    return {_key(a) for a in actual} == {_key(e) for e in expected}


def _count_rules(memory: MemoryAgent) -> int:
    return len(memory.load_rules())


def _count_schedules(scheduler: ScheduleManager) -> int:
    return len(scheduler.list_all())


# ---------------------------------------------------------------------------
# Pass / fail judge
# ---------------------------------------------------------------------------

def _judge(
    expected_result: str,
    expected_actions: list[dict],
    actual_actions: list[dict],
    rules_before: int,
    rules_after: int,
    sched_before: int,
    sched_after: int,
    reply: str,
) -> tuple[bool, str]:
    if expected_result == "no_action":
        ok = not actual_actions
        return ok, "ok" if ok else f"got actions: {actual_actions}"

    if expected_result == "success":
        ok = _actions_match(actual_actions, expected_actions)
        return ok, "ok" if ok else f"mismatch — got {actual_actions}, expected {expected_actions}"

    if expected_result == "rule_saved":
        if rules_after > rules_before:
            return True, "ok"
        # 允許更新（count 不變但 reply 包含學習關鍵字）
        if any(k in reply for k in ("記住", "更新", "Got it", "Updated")):
            return True, "ok (rule updated)"
        return False, f"rule count unchanged: {rules_before} → {rules_after}"

    if expected_result == "rule_deleted":
        ok = rules_after < rules_before
        return ok, "ok" if ok else f"rule count unchanged: {rules_before} → {rules_after}"

    if expected_result == "schedule_saved":
        ok = sched_after > sched_before
        return ok, "ok" if ok else f"schedule count unchanged: {sched_before} → {sched_after}"

    if expected_result == "list_returned":
        ok = any(k in reply for k in ("排程", "schedule", "No schedules", "目前"))
        return ok, "ok" if ok else f"reply doesn't look like a list: {reply[:60]}"

    if expected_result == "schedule_deleted":
        ok = sched_after < sched_before
        return ok, "ok" if ok else f"schedule count unchanged: {sched_before} → {sched_after}"

    if expected_result == "schedule_conflict":
        if sched_after > sched_before:
            return False, "schedule was added despite conflict"
        return True, "ok (not added)"

    if expected_result == "schedule_fail":
        if sched_after > sched_before:
            return False, "schedule was added despite limit"
        return True, "ok (rejected)"

    if expected_result in ("schedule_timing", "timing_recorded"):
        return True, "skipped (timing — see SEQ_09)"

    return False, f"unknown expected_result: {expected_result}"


# ---------------------------------------------------------------------------
# SEQ_09 — timing deviation test
# ---------------------------------------------------------------------------

def _run_timing_seq(
    agent: SmartHomeAgent,
    scheduler: ScheduleManager,
    rows: list[dict],
) -> list[dict]:
    _reset_schedules(scheduler)
    results: list[dict] = []
    now = datetime.now()
    target = now + timedelta(minutes=2)

    # M_032: add once-schedule at now+2min
    input_text = f"今天{target.hour}點{target.minute:02d}分開客廳燈"
    sched_before = _count_schedules(scheduler)
    r = agent.handle(input_text, lang="zh")
    sched_after = _count_schedules(scheduler)
    passed = sched_after > sched_before
    results.append({
        **rows[0],
        "actual_input": input_text,
        "actual_reply": r.get("reply", ""),
        "sched_before": sched_before,
        "sched_after": sched_after,
        "passed": passed,
        "reason": "added" if passed else "NOT added",
        "target_time": target.strftime("%H:%M"),
    })

    # M_033: wait for scheduler_runtime to execute (poll until 2min past target)
    print(f"\n⏳ SEQ_09: 等待排程執行（目標 {target.strftime('%H:%M')}，最多等到 +2 分）...")
    exec_time: datetime | None = None
    deadline = target + timedelta(minutes=2)
    while datetime.now() < deadline:
        time.sleep(10)
        if _count_schedules(scheduler) < sched_after:
            exec_time = datetime.now()
            break

    if exec_time:
        dev = abs((exec_time - target).total_seconds())
        timing_ok = dev <= 120
        reason = f"executed at {exec_time.strftime('%H:%M:%S')}, deviation {dev:.0f}s"
    else:
        dev = None
        timing_ok = False
        reason = "schedule not auto-deleted within deadline"

    results.append({
        **rows[1],
        "actual_input": "(wait)",
        "actual_reply": "",
        "target_time": target.strftime("%H:%M:%S"),
        "exec_time": exec_time.strftime("%H:%M:%S") if exec_time else None,
        "deviation_sec": dev,
        "passed": timing_ok,
        "reason": reason,
    })

    # M_034: once schedule should be gone from list
    list_result = agent.handle("查看排程", lang="zh")
    still_exists = _count_schedules(scheduler) >= sched_after
    results.append({
        **rows[2],
        "actual_input": "查看排程",
        "actual_reply": list_result.get("reply", ""),
        "passed": not still_exists,
        "reason": "auto-deleted" if not still_exists else "still in list",
    })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/eval/memory_test_cases.csv")
    parser.add_argument("--out", default="data/eval/memory_results.json")
    parser.add_argument("--skip-timing", action="store_true",
                        help="Skip SEQ_09 (waiting ~4 min for scheduler)")
    args = parser.parse_args()

    csv_path = PROJECT_ROOT / args.csv
    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    memory = MemoryAgent()
    scheduler = ScheduleManager()
    agent = SmartHomeAgent(memory=memory, scheduler=scheduler)

    with csv_path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    results: list[dict] = []
    timing_rows: list[dict] = []

    for row in rows:
        test_id = row["test_id"]
        seq_id = row["sequence_id"]
        phase = row["phase"]
        precond = row.get("precondition", "none").strip()
        input_text = row.get("input_text", "").strip()
        expected_route = row.get("expected_route", "").strip()
        expected_result = row.get("expected_result", "").strip()
        expected_actions = _parse_actions(row.get("expected_actions_json", ""))
        note = row.get("note", "").strip()

        # SEQ_09 handled separately
        if seq_id == "SEQ_09":
            timing_rows.append(row)
            continue

        print(f"\n{'─'*60}")
        print(f"[{test_id}] {seq_id}  phase={phase}  precond={precond}")

        if precond not in ("none", "wait_execution", ""):
            _apply_precondition(precond, memory, scheduler)
            print(f"  ✔ precondition: {precond}")

        # Rows with no input (precondition-only)
        if not input_text or input_text == "-":
            results.append({
                "test_id": test_id, "sequence_id": seq_id, "phase": phase,
                "note": note, "skipped": True, "passed": True,
                "reason": "precondition-only row",
            })
            print("  → skip (no input)")
            continue

        print(f"  input: {input_text}")
        rules_before = _count_rules(memory)
        sched_before = _count_schedules(scheduler)

        result = agent.handle(input_text, lang="zh")
        actual_actions = result.get("actions_executed") or []
        reply = result.get("reply") or ""

        rules_after = _count_rules(memory)
        sched_after = _count_schedules(scheduler)

        passed, reason = _judge(
            expected_result, expected_actions, actual_actions,
            rules_before, rules_after, sched_before, sched_after, reply,
        )

        print(f"  reply: {reply[:80]}")
        print(f"  actions: {actual_actions}")
        print(f"  {'✅ PASS' if passed else '❌ FAIL'} — {reason}")

        results.append({
            "test_id": test_id,
            "sequence_id": seq_id,
            "phase": phase,
            "expected_route": expected_route,
            "expected_result": expected_result,
            "expected_actions": expected_actions,
            "actual_actions": actual_actions,
            "actual_reply": reply,
            "rules_before": rules_before,
            "rules_after": rules_after,
            "sched_before": sched_before,
            "sched_after": sched_after,
            "passed": passed,
            "reason": reason,
            "note": note,
        })

    # SEQ_09
    if timing_rows:
        if args.skip_timing:
            print("\n⚠️  SEQ_09 skipped (--skip-timing)")
            for row in timing_rows:
                results.append({
                    "test_id": row["test_id"], "sequence_id": "SEQ_09",
                    "phase": row["phase"], "passed": None,
                    "reason": "skipped", "note": row.get("note", ""),
                })
        else:
            results.extend(_run_timing_seq(agent, scheduler, timing_rows))

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    active = [r for r in results if not r.get("skipped") and r.get("passed") is not None]
    passed_n = sum(1 for r in active if r["passed"])
    print(f"\n{'═'*60}")
    print(f"Saved → {out_path}")
    print(f"Result: {passed_n}/{len(active)} passed")


if __name__ == "__main__":
    main()
