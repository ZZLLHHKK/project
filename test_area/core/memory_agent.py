from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import LONG_TERM, SHORT_TERM


class ConversationMemory:
    """Short-term memory: keep recent interactions in short_term.json."""

    def __init__(self, short_term_path: Path = SHORT_TERM, keep: int = 10) -> None:
        self.short_term_path = Path(short_term_path)
        self.keep = keep
        self.short_term_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.short_term_path.exists():
            self._write({"interactions": [], "updated_at": int(time.time())})

    # helper methods to read/write the short-term memory file
    def _read(self) -> dict[str, Any]:
        try:
            raw = self.short_term_path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
            if not isinstance(data, dict):
                return {"interactions": [], "updated_at": int(time.time())}
            if not isinstance(data.get("interactions"), list):
                data["interactions"] = []
            return data
        except Exception:
            return {"interactions": [], "updated_at": int(time.time())}

    def _write(self, data: dict[str, Any]) -> None:
        self.short_term_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 主要功能區
    def add(self, user_input: str, response: str) -> None:
        data = self._read()
        interactions = data.get("interactions", [])
        interactions.append(
            {
                "ts": int(time.time()),
                "user": (user_input or "").strip(),
                "assistant": (response or "").strip(),
            }
        )
        data["interactions"] = interactions[-self.keep :]
        data["updated_at"] = int(time.time())
        self._write(data)

    def get_recent(self, limit: int = 5) -> list[dict[str, Any]]:
        data = self._read()
        interactions = data.get("interactions", [])
        return interactions[-max(1, limit) :]

    def get_all(self) -> list[dict[str, Any]]:
        return self._read().get("interactions", [])

    def clear(self) -> None:
        """清空短期記憶，但保留長期記憶。"""
        self._write({"interactions": [], "updated_at": int(time.time())}) # "interactions": [] 清空對話


class MemoryAgent:
    """Facade for short-term and long-term memory operations."""

    def __init__(self, short_keep: int = 10, long_term_path: Path = LONG_TERM) -> None:
        self.conversation = ConversationMemory(keep=short_keep)
        self.long_term_path = Path(long_term_path)
        self.long_term_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.long_term_path.exists():
            self.long_term_path.write_text("", encoding="utf-8")

    def save_interaction(self, user_input: str, response: str) -> None:
        """保存一輪對話:短期記憶 + 長期記憶"""
        self.conversation.add(user_input, response)
        record = {
            "ts": int(time.time()),
            "user": (user_input or "").strip(),
            "assistant": (response or "").strip(),
        }
        with self.long_term_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_recent_memory(self, limit: int = 5) -> list[dict[str, Any]]:
        """取得近期對話記憶，預設5條。"""
        return self.conversation.get_recent(limit=limit)

    def clear_memory(self) -> None:
        """Clear short-term memory only (long-term is preserved)."""
        self.conversation.clear()

    def get_context(self, limit: int = 5) -> str:
        """整理近期記憶成為 LLM prompt context 的格式。"""
        rows = self.get_recent_memory(limit=limit)
        if not rows:
            return "(no recent memory)"

        lines: list[str] = []
        for row in rows:
            lines.append(f"User: {row.get('user', '')}")
            lines.append(f"Assistant: {row.get('assistant', '')}")
        return "\n".join(lines)


# 測試區域
if __name__ == "__main__":
    # Test area: run this file directly to verify memory behavior.
    agent = MemoryAgent(short_keep=3)

    print("=== Step 1: Save interactions ===")
    agent.save_interaction("開客廳燈", "好的，客廳燈已開")
    agent.save_interaction("風扇關掉", "好的，風扇已關")
    agent.save_interaction("溫度調到 24", "好的，溫度已設為 24 度")

    print("\n=== Step 2: Recent 2 interactions ===")
    recent = agent.get_recent_memory(limit=2)
    print(json.dumps(recent, ensure_ascii=False, indent=2))

    print("\n=== Step 3: Context for LLM ===")
    print(agent.get_context(limit=3))

    print("\n=== Step 4: 清除短期記憶 ===")
    agent.clear_memory()
    

"""
程式運作原理
1.ConversationMemory 負責「短期記憶」檔案（通常 short_term.json）。
2.MemoryAgent 是對外入口，呼叫 ConversationMemory，並可同時寫長期記憶（long_term.jsonl）。
3.每輪對話 save_interaction(user, response)：
- 寫到 short-term（保留最近 N 筆）
- append 一行到 long-term（累積歷史）
4.get_recent_memory(limit) 取最近幾筆給 LLM。
5.get_context(limit) 把最近幾筆整理成 prompt 字串。
6.clear_memory() 清空短期記憶（通常長期不清）。

"""


"""
程式目的:
(1)LLM 需要 context
(2)Agent 需要歷史
(3)LangGraph 需要 memory node

class 負責
MemoryAgent = 對外接口
ConversationMemory = 存對話資料

未來要加:
(1)LongTermMemory
(2)VectorMemory
(3)PreferenceMemory
"""

"""
class MemoryAgent 說明
- 系統的記憶管理中心
負責：
(1)管理對話記憶
(2)提供 context 給 LLM
(3)保存互動記錄
它 不直接存資料，而是呼叫下面的 memory。
"""

"""
class ConversationMemory 說明
- 真正存放對話資料
只做:
存
拿
清
"""

"""
架構圖
MemoryAgent
      │
      ▼
ConversationMemory
      │
      ▼
[
  (user_input, response),
  (user_input, response),
  ...
]

結論:
memory agent 負責
保存對話
提供 LLM context
管理 memory
"""