from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_parent(path: str | Path) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def read_text(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return default


def write_text_file(path: str | Path, content: str) -> None:
    file_path = ensure_parent(path)
    file_path.write_text(content, encoding="utf-8")


def read_json_file(path: str | Path, default: Any = None) -> Any:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else default
    except Exception:
        return default


def write_json_file(path: str | Path, payload: Any) -> None:
    file_path = ensure_parent(path)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: str | Path, payload: Any) -> None:
    file_path = ensure_parent(path)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
