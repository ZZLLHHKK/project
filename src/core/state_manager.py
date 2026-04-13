from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StateManager:
    """Keep device state and a small amount of conversation state."""

    def __init__(self) -> None:
        self.temperature: int = 25
        self.fan: str = "off"
        self.light: dict[str, str] = {
            "KITCHEN": "off",
            "LIVING": "off",
            "GUEST": "off",
        }
        self.mode: str = "normal"
        self.needs_clarification: bool = False
        self.clarification_message: str | None = None
        self.ambient_temp: int | None = None
        self.ambient_humidity: int | None = None

        project_root = Path(__file__).resolve().parents[2]
        self._state_file = project_root / "data" / "memory" / "device_state.json"
        self.load_state()

    @property
    def setpoint_temp(self) -> int:
        return self.temperature

    @setpoint_temp.setter
    def setpoint_temp(self, value: int) -> None:
        self.temperature = int(value)

    @property
    def fan_state(self) -> str:
        return self.fan

    @fan_state.setter
    def fan_state(self, value: str) -> None:
        self.fan = str(value).lower()

    @property
    def led_states(self) -> dict[str, str]:
        return self.light

    @led_states.setter
    def led_states(self, value: dict[str, str]) -> None:
        self.light = dict(value)

    def load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            return

        if isinstance(data, dict):
            self.temperature = int(data.get("temperature", data.get("setpoint_temp", 25)))
            self.fan = str(data.get("fan", data.get("fan_state", "off"))).lower()
            self.light = dict(
                data.get(
                    "light",
                    data.get(
                        "led_states",
                        {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"},
                    ),
                )
            )
            self.mode = str(data.get("mode", "normal"))

    def save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "temperature": self.temperature,
            "fan": self.fan,
            "light": self.light,
            "mode": self.mode,
        }
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_from_actions(self, actions: list[dict[str, Any]]) -> None:
        changed = False
        for action in actions:
            action_type = str(action.get("type", "")).upper()
            if action_type == "SET_TEMP":
                self.temperature = int(action.get("value", self.temperature))
                changed = True
            elif action_type == "FAN":
                self.fan = str(action.get("state", self.fan)).lower()
                changed = True
            elif action_type == "LED":
                location = str(action.get("location", "")).upper()
                if location in self.light:
                    self.light[location] = str(action.get("state", "off")).lower()
                    changed = True
        if changed:
            self.save_state()

    def set_state(self, **kwargs: Any) -> None:
        changed = False
        for key, value in kwargs.items():
            if key == "setpoint_temp":
                self.temperature = int(value)
                changed = True
            elif key == "fan_state":
                self.fan = str(value).lower()
                changed = True
            elif key == "led_states":
                self.light = dict(value)
                changed = True
            elif hasattr(self, key):
                setattr(self, key, value)
        if changed:
            self.save_state()

    def reset_conversation(self) -> None:
        self.needs_clarification = False
        self.clarification_message = None

    def get_state(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "fan": self.fan,
            "light": dict(self.light),
            "mode": self.mode,
            "needs_clarification": self.needs_clarification,
            "clarification_message": self.clarification_message,
            "ambient_temp": self.ambient_temp,
            "ambient_humidity": self.ambient_humidity,
        }
