from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schedule_path() -> Path:
    return _project_root() / "data" / "memory" / "schedules.json"


def _load_schedules(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("schedules.json must be a JSON array")
    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _save_schedules(path: Path, schedules: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedules, ensure_ascii=False, indent=2), encoding="utf-8")


def backup_schedules(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"schedules.json.phase2_backup_{timestamp}")
    if path.exists():
        shutil.copy2(path, backup_path)
    else:
        backup_path.write_text("[]\n", encoding="utf-8")
    return backup_path


def restore_schedules(path: Path, backup_path: Path) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    shutil.copy2(backup_path, path)


def add_demo_schedule(path: Path) -> dict[str, Any]:
    schedules = _load_schedules(path)
    run_time = datetime.now() + timedelta(minutes=1)

    schedule = {
        "id": uuid.uuid4().hex[:8],
        "name": "查詢排程",
        "hour": run_time.hour,
        "minute": run_time.minute,
        "second": 0,
        "actions": [],
        "enabled": True,
        "recurrence": "daily",
        "last_triggered": None,
        "last_executed": None,
        "last_result": None,
    }

    schedules.append(schedule)
    _save_schedules(path, schedules)
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 scheduler demo helper")
    parser.add_argument("--restore", action="store_true", help="restore schedules.json from backup")
    parser.add_argument("--backup", type=str, default="", help="backup file path for restore")
    args = parser.parse_args()

    schedule_path = _schedule_path()

    if args.restore:
        if not args.backup:
            raise SystemExit("請提供 --backup /path/to/schedules.json.phase2_backup_xxx")
        restore_schedules(schedule_path, Path(args.backup).expanduser().resolve())
        print(f"[OK] 已還原: {schedule_path}")
        return

    backup_path = backup_schedules(schedule_path)
    schedule = add_demo_schedule(schedule_path)

    print("[OK] 已建立 backup")
    print(str(backup_path))
    print("[OK] 已新增測試排程")
    print(json.dumps(schedule, ensure_ascii=False, indent=2))
    print("[NEXT] 請立即啟動 GUI，等待 1 分鐘觸發")
    print("[RESTORE] 測試後執行:")
    print(f"python scripts/test_scheduler_phase2.py --restore --backup {backup_path}")


if __name__ == "__main__":
    main()
