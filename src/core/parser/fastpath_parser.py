"""
Fast-path parsing & rule learning/application.

This module aims to avoid LLM calls when the user intent is explicit.
It also preserves the "rule learning" capability from temp_7seg_fuzzy_memory.py:
- Learn rules like: 當我說 X 代表 Y
- Store to rules.json as: RULE: When user says 'X', it means 'Y'.
- Apply those rules by rewriting user text before parsing.
"""
from __future__ import annotations

import re
import math
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Allow direct execution: python test_area/core/parser/fastpath_parser.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import utils.config as config
    from core.actions_schema import ActionDict
    from utils.file_io import push_history, load_rules, append_line_unique
except ModuleNotFoundError:
    # Fallback for direct file runs when src package optional deps are missing.
    SRC_ROOT = PROJECT_ROOT / "src"
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    import utils.config as config
    from core.actions_schema import ActionDict
    from utils.file_io import push_history, load_rules, append_line_unique

# -------------------------
# Math helpers
# -------------------------
def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# -------------------------
# Memory learning rules
# -------------------------
LEARN_PATTERNS = [
    re.compile(r"^\s*當我說\s*(.+?)\s*(?:的時候|時|時候)?\s*[，,]?\s*代表\s*(.+?)\s*$"),
    re.compile(r"^\s*(?:以後|之後)\s*我說\s*(.+?)\s*(?:就|代表)\s*(.+?)\s*$"),
    re.compile(r"^\s*如果我說\s*(.+?)\s*[，,]?\s*(?:請|就)\s*(.+?)\s*$"),
]

# -------------------------
# Fast local extraction
# -------------------------
NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:度|°|c|℃)?", re.IGNORECASE)

# Chinese/English keyword sets
KW_ON  = ("開", "打開", "開啟", "on", "turn on", "open")
KW_OFF = ("關", "關掉", "關閉", "off", "turn off", "close")

class RuleLearner:
    """責任：處理 LEARN_PATTERNS、try_learn_rule"""
    """做「是否為教學句」與「產生/儲存 rule」"""
    """辨識教學句並寫入rules.json"""

    def __init__(
        self,
        patterns: Optional[List[re.Pattern[str]]] = None,
        rules_file: str = config.RULES_FILE,
        append_unique_fn=append_line_unique,
        push_history_fn=push_history,
    ) -> None:
        self.patterns = patterns or LEARN_PATTERNS
        self.rules_file = rules_file
        self.append_unique_fn = append_unique_fn
        self.push_history_fn = push_history_fn

    def _normalize_phrase(self, text: str) -> str:
        return (text or "").strip().strip("「」\"'")

    def _extract_rule(self, user_text: str) -> Optional[Tuple[str, str]]:
        t = (user_text or "").strip()
        for pat in self.patterns:
            m = pat.match(t)
            if not m:
                continue
            trigger = self._normalize_phrase(m.group(1))
            meaning = self._normalize_phrase(m.group(2))
            if trigger and meaning:
                return trigger, meaning
        return None

    def learn(self, user_text: str) -> Optional[Dict[str, Any]]:
        extracted = self._extract_rule(user_text)
        if not extracted:
            return None

        trigger, meaning = extracted
        rule_line = f"RULE: When user says '{trigger}', it means '{meaning}'."
        self.append_unique_fn(self.rules_file, rule_line)
        out = {"intent": "learn_rule", "saved_rule": {"trigger": trigger, "meaning": meaning}}
        self.push_history_fn(user_text, out)
        return out

class RuleApplier:
    """責任：apply_memory_rules"""
    """只做規則套用，不做裝置解析"""

    def __init__(self, load_rules_fn=load_rules) -> None:
        self.load_rules_fn = load_rules_fn

    def _apply_one(self, text: str, trigger: str, meaning: str) -> str:
        if not trigger:
            return text
        return text.replace(trigger, meaning)

    def apply(self, user_text: str) -> str:
        text = user_text or ""
        for trigger, meaning in self.load_rules_fn():
            text = self._apply_one(text, trigger, meaning)
        return text

class TemperatureParser:
    """責任：NUM_RE、extract_explicit_temp、round/clamp 到 SET_TEMP action"""

    def __init__(
        self,
        min_temp: float = config.MIN_TEMP,
        max_temp: float = config.MAX_TEMP,
        num_re: re.Pattern[str] = NUM_RE,
    ) -> None:
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.num_re = num_re

    def extract_explicit_temp(self, user_text: str) -> Optional[float]:
        matches = self.num_re.findall(user_text or "")
        if not matches:
            return None
        for s in matches:
            try:
                v = float(s)
            except Exception:
                continue
            if 0.0 <= v <= 60.0:
                return v
        return None

    def parse(self, text: str) -> Optional[List[ActionDict]]:
        v = self.extract_explicit_temp(text)
        if v is None:
            return None

        temp_f = clamp(float(v), self.min_temp, self.max_temp)
        temp_i = round_half_up(temp_f)
        temp_i = int(clamp(temp_i, int(self.min_temp), int(self.max_temp)))
        return [{"type": "SET_TEMP", "value": temp_i}]

class DeviceCommandParser:
    """責任：風扇、燈、全部關閉等裝置語句解析"""
    """可再拆成 FanParser、LightParser（你規則再多時很有用）"""

    def __init__(
        self,
        loc_map: Optional[Dict[str, Tuple[str, ...]]] = None,
        kw_on: Tuple[str, ...] = KW_ON,
        kw_off: Tuple[str, ...] = KW_OFF,
    ) -> None:
        self.loc_map = loc_map or {
            config.LOC_KITCHEN: ("廚房", "kitchen"),
            config.LOC_LIVING: ("客廳", "living"),
            config.LOC_GUEST: ("客房", "guest"),
        }
        self.kw_on = kw_on
        self.kw_off = kw_off

    def _contains_any(self, text: str, keywords: Tuple[str, ...]) -> bool:
        t = (text or "").lower()
        return any(k.lower() in t for k in keywords)

    def _parse_all_off(self, t: str) -> Optional[List[ActionDict]]:
        if not (("全部" in t or "all" in t) and self._contains_any(t, self.kw_off)):
            return None
        return [
            {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
            {"type": "LED", "location": config.LOC_LIVING, "state": "off"},
            {"type": "LED", "location": config.LOC_GUEST, "state": "off"},
            {"type": "FAN", "state": "off"},
        ]

    def _parse_fan(self, t: str) -> Optional[List[ActionDict]]:
        if ("風扇" not in t) and ("fan" not in t):
            return None
        if self._contains_any(t, self.kw_on) and not self._contains_any(t, self.kw_off):
            return [{"type": "FAN", "state": "on"}]
        if self._contains_any(t, self.kw_off) and not self._contains_any(t, self.kw_on):
            return [{"type": "FAN", "state": "off"}]
        return None

    def _parse_lights_by_location(self, t: str) -> Optional[List[ActionDict]]:
        if not any(k in t for keys in self.loc_map.values() for k in keys):
            return None
        if self._contains_any(t, self.kw_on) and not self._contains_any(t, self.kw_off):
            state = "on"
        elif self._contains_any(t, self.kw_off) and not self._contains_any(t, self.kw_on):
            state = "off"
        else:
            return None

        actions_loc: List[ActionDict] = []
        for loc, keys in self.loc_map.items():
            if any(k in t for k in keys):
                actions_loc.append({"type": "LED", "location": loc, "state": state})
        return actions_loc or None

    def _parse_lights_with_explicit_word(self, t: str) -> Optional[List[ActionDict]]:
        found_any = False
        actions_out: List[ActionDict] = []
        for loc, keys in self.loc_map.items():
            if any(k in t for k in keys) and ("燈" in t or "light" in t or "lamp" in t):
                found_any = True
                if self._contains_any(t, self.kw_on) and not self._contains_any(t, self.kw_off):
                    actions_out.append({"type": "LED", "location": loc, "state": "on"})
                elif self._contains_any(t, self.kw_off) and not self._contains_any(t, self.kw_on):
                    actions_out.append({"type": "LED", "location": loc, "state": "off"})
                else:
                    return None
        if found_any and actions_out:
            return actions_out
        return None

    def _parse_lights_global(self, t: str) -> Optional[List[ActionDict]]:
        if not ("燈" in t or "light" in t or "lamp" in t):
            return None
        if self._contains_any(t, self.kw_on) and not self._contains_any(t, self.kw_off):
            return [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "on"},
                {"type": "LED", "location": config.LOC_LIVING, "state": "on"},
                {"type": "LED", "location": config.LOC_GUEST, "state": "on"},
            ]
        if self._contains_any(t, self.kw_off) and not self._contains_any(t, self.kw_on):
            return [
                {"type": "LED", "location": config.LOC_KITCHEN, "state": "off"},
                {"type": "LED", "location": config.LOC_LIVING, "state": "off"},
                {"type": "LED", "location": config.LOC_GUEST, "state": "off"},
            ]
        return None

    def parse(self, text: str) -> Optional[List[ActionDict]]:
        t = (text or "").lower()

        actions = self._parse_all_off(t)
        if actions:
            return actions

        if ("風扇" in t) or ("fan" in t):
            return self._parse_fan(t)

        actions = self._parse_lights_by_location(t)
        if actions:
            return actions

        actions = self._parse_lights_with_explicit_word(t)
        if actions:
            return actions

        return self._parse_lights_global(t)

class HistoryRecorder:
    """責任：push_history 的包裝"""
    """讓 parser 本體不直接碰 I/O 細節"""

    def __init__(self, push_history_fn=push_history) -> None:
        self.push_history_fn = push_history_fn

    def record_fastpath(self, user_text: str, actions: List[ActionDict]) -> None:
        self.push_history_fn(user_text, {"fastpath": True, "actions": actions})

class FastPathParser:
    """規則基礎的快速解析器，嘗試從使用者輸入中直接提取明確指令，避免不必要的 LLM 呼叫。"""

    def __init__(
        self,
        rule_learner: Optional[RuleLearner] = None,
        rule_applier: Optional[RuleApplier] = None,
        temperature_parser: Optional[TemperatureParser] = None,
        device_parser: Optional[DeviceCommandParser] = None,
        history_recorder: Optional[HistoryRecorder] = None,
    ) -> None:
        """初始化 FastPathParser，目前無需額外參數。"""
        self.history_recorder = history_recorder or HistoryRecorder()
        self.rule_learner = rule_learner or RuleLearner(push_history_fn=self.history_recorder.push_history_fn)
        self.rule_applier = rule_applier or RuleApplier()
        self.temperature_parser = temperature_parser or TemperatureParser()
        self.device_parser = device_parser or DeviceCommandParser()

    def learn_rule(self, user_text: str) -> Optional[Dict[str, Any]]:
        """處理教學句規則學習，成功時回傳 learning 結果。"""
        return self.rule_learner.learn(user_text)

    def parse(self, user_text: str) -> Optional[List[ActionDict]]:
        """嘗試從 user_text 中提取明確指令，返回 ActionDict 列表或 None。"""
        if not user_text or not user_text.strip():
            return None

        text = self.rule_applier.apply(user_text)

        actions = self.temperature_parser.parse(text)
        if actions:
            self.history_recorder.record_fastpath(user_text, actions)
            return actions

        actions = self.device_parser.parse(text)
        if actions:
            self.history_recorder.record_fastpath(user_text, actions)
            return actions

        return None
    
    def match_action(self, user_text: str, action_type: str) -> bool:
        """判斷 user_text 是否明確包含特定類型的指令，例如 "SET_TEMP"、"FAN"、"LED"。"""
        actions = self.parse(user_text)
        if not actions:
            return False
        for act in actions:
            if act.get("type") == action_type:
                return True
        return False
    
    def match_location(self, user_text: str, location: str) -> bool:
        """判斷 user_text 是否明確包含特定位置的指令，例如 "KITCHEN"、"LIVING"、"GUEST"。"""
        actions = self.parse(user_text)
        if not actions:
            return False
        for act in actions:
            if act.get("location") == location:
                return True
        return False


_DEFAULT_FASTPATH_PARSER = FastPathParser()


def try_learn_rule(user_text: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible function wrapper."""
    return _DEFAULT_FASTPATH_PARSER.learn_rule(user_text)


def apply_memory_rules(user_text: str) -> str:
    """Backward-compatible function wrapper."""
    return _DEFAULT_FASTPATH_PARSER.rule_applier.apply(user_text)


def extract_explicit_temp(user_text: str) -> Optional[float]:
    """Backward-compatible function wrapper."""
    return _DEFAULT_FASTPATH_PARSER.temperature_parser.extract_explicit_temp(user_text)


def parse_fastpath(user_text: str) -> Optional[List[ActionDict]]:
    """Backward-compatible function wrapper."""
    return _DEFAULT_FASTPATH_PARSER.parse(user_text)


if __name__ == "__main__":
    # 測試區域：預設只做解析測試，不寫入 rules/history。
    print("=== FastPathParser Test Area ===")

    parser = FastPathParser()
    samples = [
        "把溫度調到 26 度",
        "幫我關掉全部",
        "開客廳燈",
        "turn on fan",
        "幫我把燈都關掉",
        "我只是聊天",
    ]

    print("\n[1] Parse samples")
    for text in samples:
        actions = parser.parse(text)
        print(f"input={text!r} -> actions={actions}")

    print("\n[2] Match helpers")
    print("match_action('開風扇', 'FAN'):", parser.match_action("開風扇", "FAN"))
    print("match_location('開客廳燈', 'LIVING'):", parser.match_location("開客廳燈", "LIVING"))

    # 若你要測試規則學習，改成 True。
    # 注意：會寫入 rules.json 與 history.jsonl。
    ENABLE_LEARN_RULE_TEST = False
    if ENABLE_LEARN_RULE_TEST:
        print("\n[3] Learn rule test")
        out = parser.learn_rule("當我說晚安，代表關掉全部")
        print("learn_rule output:", out)
        rewritten = apply_memory_rules("晚安")
        print("after rewrite:", rewritten)