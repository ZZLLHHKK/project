from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.services.command_service import CommandResult, execute_text_command


@dataclass(slots=True)
class GuiCommandPresentation:
    raw_reply: str
    formatted_reply: str
    spoken_reply: str
    error: str | None
    should_shutdown: bool
    should_standby: bool
    should_speak: bool
    result: CommandResult


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def _to_english_reply(reply: str) -> str:
    direct = {
        "請告訴我你想控制的設備或需求。": "Please tell me which device or action you want.",
        "好的，我先休息囉，有需要請隨時叫我！": "Okay, entering standby. Wake me when needed.",
        "好的，系統關閉中，再見！": "Okay, shutting down. Goodbye!",
        "好的，已清除短期記憶。": "Okay, short-term memory has been cleared.",
        "抱歉，我現在無法處理，請稍後再試。": "Sorry, I can't process that right now. Please try again later.",
    }
    if reply in direct:
        return direct[reply]

    converted = reply
    replacements = [
        ("好的，", "Okay, "),
        ("好的", "Okay"),
        ("但有部分裝置沒有成功執行。", "but some devices did not execute successfully."),
        ("溫度已設定為", "temperature has been set to"),
        ("風扇已開啟", "fan turned on"),
        ("風扇已關閉", "fan turned off"),
        ("客廳燈已開啟", "living room light turned on"),
        ("客廳燈已關閉", "living room light turned off"),
        ("廚房燈已開啟", "kitchen light turned on"),
        ("廚房燈已關閉", "kitchen light turned off"),
        ("客房燈已開啟", "guest room light turned on"),
        ("客房燈已關閉", "guest room light turned off"),
    ]
    for source, target in replacements:
        converted = converted.replace(source, target)

    if _contains_cjk(converted):
        return f"{converted} (Original reply is partially Chinese.)"
    return converted


def format_reply_for_language(reply: str, language: str) -> str:
    if language == "en":
        return _to_english_reply(reply)
    return reply


def _sanitize_tts_reply(reply: str) -> str:
    text = reply or ""
    text = re.sub(r"\[[a-f0-9]{8}\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bID\s*[為:]?\s*[a-f0-9]{8}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[a-f0-9]{8}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_gui_command_presentation(result: CommandResult, language: str) -> GuiCommandPresentation:
    raw_reply = str(result.raw_reply or "")
    formatted_reply = format_reply_for_language(raw_reply, language)
    spoken_reply = _sanitize_tts_reply(raw_reply)
    should_speak = language == "zh" and bool(raw_reply)
    return GuiCommandPresentation(
        raw_reply=raw_reply,
        formatted_reply=formatted_reply,
        spoken_reply=spoken_reply,
        error=result.error,
        should_shutdown=result.should_shutdown,
        should_standby=result.should_standby,
        should_speak=should_speak,
        result=result,
    )


def execute_gui_text_command(agent: Any, text: str, language: str) -> GuiCommandPresentation:
    result = execute_text_command(agent, text, lang=language)
    return build_gui_command_presentation(result, language)