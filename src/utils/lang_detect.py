"""Language detection utility.

Heuristic:
- If any CJK chars appear, treat as Traditional Chinese (zh).
- Else if ASCII letters >= 2, treat as English (en).
- Fallback to zh.
"""

from __future__ import annotations


def detect_lang(text: str) -> str:
    """Detect dominant language and return 'zh' or 'en'."""
    clean = (text or "").strip()
    if not clean:
        return "zh"

    cjk_chars = sum(1 for c in clean if ("\u4e00" <= c <= "\u9fff") or ("\u3400" <= c <= "\u4dbf"))
    if cjk_chars > 0:
        return "zh"

    ascii_letters = sum(1 for c in clean if c.isalpha() and ord(c) < 128)
    if ascii_letters >= 2:
        return "en"
    return "zh"
