# src/utils/file_io.py
import os
import json
import time
import re
from typing import List, Dict, Any, Tuple, Optional

from src.utils.config import INPUT_FILE, OUTPUT_FILE, HISTORY_FILE, RULES_FILE, HISTORY_KEEP

def ensure_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("")

def append_line_unique(path: str, line: str) -> None:
    ensure_file(path)
    line = line.strip()
    if not line:
        return
    existing = read_text(path)
    lines = [x.strip() for x in existing.splitlines() if x.strip()]
    if line in lines:
        return
    with open(path, "a", encoding="utf-8") as f:
        if lines:
            f.write("\n")
        f.write(line)

def load_history() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_FILE):
        return []
    out: List[Dict[str, Any]] = []
    with open(HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    return out

def save_history(records: List[Dict[str, Any]]) -> None:
    records = records[-HISTORY_KEEP:]
    ensure_file(HISTORY_FILE)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def push_history(user_text: str, result: Any) -> None:
    records = load_history()
    records.append({"ts": int(time.time()), "user": user_text, "result": result})
    save_history(records)

def format_history_for_prompt() -> str:
    records = load_history()[-HISTORY_KEEP:]
    if not records:
        return "(no recent history)"
    lines = []
    for r in records:
        u = (r.get("user") or "").strip()
        res = r.get("result")
        lines.append(f"- user: {u}\n  parsed: {json.dumps(res, ensure_ascii=False)}")
    return "\n".join(lines)

RULE_LINE_RE = re.compile(r"^RULE:\s*When user says '(.+?)', it means '(.+?)'\.\s*$")


def _ensure_rules_file() -> None:
    """Ensure rules file exists and defaults to JSON structure."""
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump({"rules": []}, f, ensure_ascii=False, indent=2)


def save_rule(trigger: str, meaning: str) -> bool:
    """Save one memory rule into JSON, return True when inserted (False if duplicate)."""
    trigger = (trigger or "").strip()
    meaning = (meaning or "").strip()
    if not trigger or not meaning:
        return False

    rules = load_rules()
    if (trigger, meaning) in rules:
        return False

    rules.append((trigger, meaning))
    _ensure_rules_file()
    payload = {
        "rules": [{"trigger": t, "meaning": m} for t, m in rules]
    }
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return True


def format_rules_for_prompt() -> str:
    """Render rules into concise prompt-friendly text."""
    rules = load_rules()
    if not rules:
        return "(empty)"
    return "\n".join(f"- '{t}' => '{m}'" for t, m in rules)

def load_rules() -> List[Tuple[str, str]]:
    """
    Load memory rules from JSON file.
    Backward compatible: if file still contains legacy RULE lines, parse them too.
    """
    _ensure_rules_file()
    txt = read_text(RULES_FILE)
    rules: List[Tuple[str, str]] = []

    if not txt:
        return rules

    # Preferred format: {"rules": [{"trigger": "...", "meaning": "..."}]}
    try:
        data = json.loads(txt)
        items = data.get("rules", []) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            trigger = str(item.get("trigger", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            if trigger and meaning:
                rules.append((trigger, meaning))
        if rules:
            return rules
    except Exception:
        pass

    # Legacy fallback format: RULE: When user says 'X', it means 'Y'.
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = RULE_LINE_RE.match(ln)
        if not m:
            continue
        rules.append((m.group(1), m.group(2)))
    return rules

def write_text_file(path: str, content: str):
    """寫入文字檔（覆蓋模式）"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content + "\n")
        print(f"成功寫入檔案：{path}")
    except Exception as e:
        print(f"寫檔失敗：{e}")
    
def read_text(path: str) -> str:
    """
    讀取文字檔並返回內容
    如果失敗，返回空字串或拋出例外（依需求）
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()  # strip() 移除前後空白與換行
        return content
    except FileNotFoundError:
        print(f"檔案不存在：{path}")
        return ""
    except Exception as e:
        print(f"讀檔失敗：{e}")
        return ""
