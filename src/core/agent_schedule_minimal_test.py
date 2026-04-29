import tempfile
import shutil
import os
from pathlib import Path
from src.core.agent import SmartHomeAgent
from src.core.scheduler import ScheduleManager
from src.core.parser.schedule_parser import ScheduleFastPathParser

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
def run_case(desc, text, lang=None):
    try:
        r = agent.handle(text, lang)
        results.append((desc, text, r["reply"]))
    except Exception as e:
        results.append((desc, text, f"EXCEPTION: {e}"))

# 5 add
run_case("add1", "22:00 開燈")
run_case("add2", "晚上10點開燈")
run_case("add3", "tomorrow 8:00 turn on light", "en")
run_case("add4", "08:00 廚房燈開、客廳燈開、客房燈開")
run_case("add5", "7:30 開燈", "zh")

# 5 list
run_case("list1", "查詢排程")
run_case("list2", "list schedule", "en")
run_case("list3", "查詢排程", "zh")
run_case("list4", "list schedule")
run_case("list5", "list schedule", "en")

# 5 delete
run_case("delete1", "刪除1")
run_case("delete2", "delete 2", "en")
run_case("delete3", "刪除3", "zh")
run_case("delete4", "delete 4")
run_case("delete5", "delete 5", "en")

# 5 toggle
run_case("toggle1", "啟用1")
run_case("toggle2", "停用2")
run_case("toggle3", "enable 3", "en")
run_case("toggle4", "disable 4")
run_case("toggle5", "enable 5", "en")

for desc, text, reply in results:
    print(f"[{desc}] {text} => {reply}")

shutil.rmtree(_temp_dir)
