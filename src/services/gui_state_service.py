from __future__ import annotations

from typing import Any, Callable


def display_state_value(value: Any, tr: Callable[[str], str], ensure_text: Callable[[Any], str]) -> str:
    normalized = ensure_text(value).strip().lower()
    if normalized == "on":
        return tr("on")
    if normalized == "off":
        return tr("off")
    if not normalized:
        return tr("unknown")
    return ensure_text(value)


def display_location(value: Any, tr: Callable[[str], str], ensure_text: Callable[[Any], str]) -> str:
    key = ensure_text(value).strip().upper()
    mapping = {
        "KITCHEN": tr("kitchen"),
        "LIVING": tr("living"),
        "GUEST": tr("guest"),
    }
    return mapping.get(key, ensure_text(value) or tr("unknown"))


def format_device_state_content(state: dict[str, Any], tr: Callable[[str], str], ensure_text: Callable[[Any], str]) -> str:
    light_state = state.get("light", {}) if isinstance(state.get("light", {}), dict) else {}
    light_lines = [
        f"- {display_location(location, tr, ensure_text)}: {display_state_value(status, tr, ensure_text)}"
        for location, status in light_state.items()
    ]
    if not light_lines:
        light_lines = [f"- {tr('no_data')}"]

    lines = [
        f"{tr('temperature')}: {state.get('temperature', tr('unknown'))}",
        f"{tr('fan')}: {display_state_value(state.get('fan'), tr, ensure_text)}",
        f"{tr('ambient_temp')}: {state.get('ambient_temp', tr('unknown'))}",
        f"{tr('ambient_humidity')}: {state.get('ambient_humidity', tr('unknown'))}",
        "",
        f"{tr('light')}:",
        *light_lines,
    ]
    return "\n".join(lines)


def format_queue_item(item: dict[str, Any], index: int, tr: Callable[[str], str], ensure_text: Callable[[Any], str]) -> str:
    source = item.get("source") or item.get("raw_command") or item.get("command") or tr("unknown")
    status = item.get("status") or item.get("state") or tr("unknown")
    run_time = item.get("run_at") or item.get("time") or item.get("scheduled_for") or tr("unknown")
    device = item.get("device") or item.get("location") or tr("unknown")
    action = item.get("action") or item.get("type") or tr("unknown")

    lines = [
        f"{tr('queue_item')} {index}",
        f"{tr('queue_device')}: {display_location(device, tr, ensure_text)}",
        f"{tr('queue_action')}: {ensure_text(action)}",
        f"{tr('queue_time')}: {ensure_text(run_time)}",
        f"{tr('queue_status')}: {ensure_text(status)}",
        f"{tr('queue_source')}: {ensure_text(source)}",
    ]
    return "\n".join(lines)


def format_queue_content(queue_items: list[dict[str, Any]], tr: Callable[[str], str], ensure_text: Callable[[Any], str]) -> str:
    if not queue_items:
        return tr("queue_empty")

    formatted = [format_queue_item(item, index, tr, ensure_text) for index, item in enumerate(queue_items, start=1)]
    return "\n\n".join(formatted)