from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.utils.config import LONG_TERM, RULES_FILE, SHORT_TERM


class MemoryAgent:
    """Manage short-term context, long-term history, and user rules."""

    def __init__(self, keep: int = 10) -> None:
        self.keep = keep
        self.short_term_path = Path(SHORT_TERM)
        self.long_term_path = Path(LONG_TERM)
        self.rules_path = Path(RULES_FILE)

        self.short_term_path.parent.mkdir(parents=True, exist_ok=True)
        self.long_term_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.short_term_path.exists():
            self._write_short({"interactions": [], "updated_at": int(time.time())})
        if not self.long_term_path.exists():
            self.long_term_path.write_text("", encoding="utf-8")
        if not self.rules_path.exists():
            self.rules_path.write_text(
                json.dumps({"rules": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _read_short(self) -> dict[str, Any]:
        try:
            raw = self.short_term_path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
            if not isinstance(data, dict):
                return {"interactions": [], "updated_at": int(time.time())}
            interactions = data.get("interactions")
            if not isinstance(interactions, list):
                data["interactions"] = []
            return data
        except Exception:
            return {"interactions": [], "updated_at": int(time.time())}

    def _write_short(self, data: dict[str, Any]) -> None:
        self.short_term_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_interaction(self, user: str, assistant: str) -> None:
        record = {
            "ts": int(time.time()),
            "user": (user or "").strip(),
            "assistant": (assistant or "").strip(),
        }

        data = self._read_short()
        interactions = data.get("interactions", [])
        interactions.append(record)
        data["interactions"] = interactions[-self.keep :]
        data["updated_at"] = int(time.time())
        self._write_short(data)

        with self.long_term_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_recent_context(self, limit: int = 5) -> str:
        rows = self._read_short().get("interactions", [])[-max(1, limit) :]
        if not rows:
            return "(no recent memory)"

        lines: list[str] = []
        for row in rows:
            lines.append(f"User: {row.get('user', '')}")
            lines.append(f"Assistant: {row.get('assistant', '')}")
        return "\n".join(lines)

    def load_rules(self) -> list[dict[str, str]]:
        try:
            raw = self.rules_path.read_text(encoding="utf-8")
            if not raw.strip():
                return []
            data = json.loads(raw)
        except Exception:
            return []

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            rules = data.get("rules", [])
            if isinstance(rules, list):
                return [item for item in rules if isinstance(item, dict)]

        return []

    def save_rule(self, trigger: str, meaning: str) -> bool:
        trigger = (trigger or "").strip()
        meaning = (meaning or "").strip()
        if not trigger or not meaning:
            return False

        rules = self.load_rules()
        for rule in rules:
            if rule.get("trigger") == trigger:
                rule["meaning"] = meaning
                self.rules_path.write_text(
                    json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return True

        rules.append({"trigger": trigger, "meaning": meaning})
        self.rules_path.write_text(
            json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def delete_rule(self, trigger: str) -> bool:
        trigger = (trigger or "").strip()
        if not trigger:
            return False
        rules = self.load_rules()
        new_rules = [r for r in rules if r.get("trigger") != trigger]
        if len(new_rules) == len(rules):
            return False
        self.rules_path.write_text(
            json.dumps({"rules": new_rules}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def reset_conversation(self) -> None:
        self._write_short({"interactions": [], "updated_at": int(time.time())})

    def clear_memory(self) -> None:
        self.reset_conversation()

    def save_interaction(self, user_input: str, response: str) -> None:
        self.add_interaction(user_input, response)

    def get_context(self, limit: int = 5) -> str:
        return self.get_recent_context(limit=limit)
