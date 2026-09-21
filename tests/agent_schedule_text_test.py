import tempfile
import shutil
import os
from pathlib import Path
from src.core.agent import SmartHomeAgent
from src.core.scheduler import ScheduleManager
from src.core.parser.schedule_parser import ScheduleFastPathParser

def main():
    # 建立臨時 schedule json 路徑
    _temp_dir = tempfile.mkdtemp()
    _temp_sched = os.path.join(_temp_dir, "schedules.json")

    # monkeypatch ScheduleManager._path (Path 物件)
    class TestScheduleManager(ScheduleManager):
        def __init__(self):
            super().__init__()
            self._path = Path(_temp_sched)
            if not self._path.exists():
                self._write([])

    class TestAgent(SmartHomeAgent):
        def __init__(self):
            super().__init__(scheduler=TestScheduleManager())
            self.schedule_parser = ScheduleFastPathParser()

    agent = TestAgent()
    results = []
    schedule_ids = []

    def run_case(desc, text, lang=None, expect=None, store_id=False):
        try:
            r = agent.handle(text, lang)
            reply = r["reply"]
            # 若需存 id
            if store_id:
                # 從 scheduler 取最新 id
                rules = agent.scheduler.list_all()
                if rules:
                    schedule_ids.append(rules[-1]["id"])
            # 驗證
            passed = True
            if expect is not None and expect not in reply:
                passed = False
            results.append((desc, text, reply, passed))
        except Exception as e:
            results.append((desc, text, f"EXCEPTION: {e}", False))

    # 1. add
    run_case("add1", "22:00 開燈", store_id=True)
    run_case("add2", "晚上10點開風扇", store_id=True)
    run_case("add3", "tomorrow 8:00 turn on light", store_id=True)
    run_case("add4", "07:30 turn off fan", store_id=True)
    run_case("add5", "明天 9:00 關燈", store_id=True)
    # 若 schedule_ids 不足 5，補 add
    add_fill = 0
    while len(schedule_ids) < 5 and add_fill < 5:
        run_case(f"add_fill{add_fill+1}", f"{8+add_fill}:00 測試排程", store_id=True)
        add_fill += 1

    # 2. list
    run_case("list1", "查詢排程", expect="排程" if not results[0][2].startswith("Schedule") else "schedule")
    run_case("list2", "列出排程", expect="排程")
    run_case("list3", "list schedule", expect="schedule")
    run_case("list4", "show schedules", expect="schedule")
    run_case("list5", "schedules", expect="schedule")

    # 3. delete
    # 用 schedule_ids[0]~[4]
    if len(schedule_ids) >= 5:
        run_case("delete1", f"刪除{schedule_ids[0]}", expect="刪除" if not results[0][2].startswith("Schedule") else "deleted")
        run_case("delete2", f"delete {schedule_ids[1]}", expect="deleted")
        run_case("delete3", f"刪除{schedule_ids[2]}", expect="刪除" if not results[0][2].startswith("Schedule") else "deleted")
        run_case("delete4", f"delete {schedule_ids[3]}", expect="deleted")
        run_case("delete5", "delete notfoundid", expect="not found")
    else:
        for i in range(5):
            results.append((f"delete{i+1}", "(skipped)", "no id", False))

    # 4. toggle
    if len(schedule_ids) >= 5:
        run_case("toggle1", f"啟用{schedule_ids[4]}", expect="啟用" if not results[0][2].startswith("Schedule") else "enabled")
        run_case("toggle2", f"停用{schedule_ids[4]}", expect="停用" if not results[0][2].startswith("Schedule") else "disabled")
        run_case("toggle3", f"enable {schedule_ids[4]}", expect="enabled")
        run_case("toggle4", f"disable {schedule_ids[4]}", expect="disabled")
        run_case("toggle5", "enable notfoundid", expect="not found")
    else:
        for i in range(5):
            results.append((f"toggle{i+1}", "(skipped)", "no id", False))

    # 輸出結果
    all_passed = True
    for desc, text, reply, passed in results:
        print(f"[{desc}] {text} => {reply} {'✅' if passed else '❌'}")
        if not passed:
            all_passed = False

    shutil.rmtree(_temp_dir)
    if not all_passed:
        print("\n有失敗的 case，請檢查上方標記 ❌ 的項目。建議先檢查 schedule_parser.py 或 agent.py schedule CRUD 接線。")
    else:
        print("\n全部通過。")

if __name__ == "__main__":
    main()
