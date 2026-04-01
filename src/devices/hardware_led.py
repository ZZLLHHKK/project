"""
LED executor (red/yellow/green) unified in one module.

LangGraph node usage:
    led = LedController()
    led.setup()
    led.set_led("KITCHEN", "on")
    led.cleanup()
"""
from __future__ import annotations

from typing import Optional

import src.utils.config as config

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:  # pragma: no cover
    class _MockGPIO:
        BCM = OUT = HIGH = LOW = 0
        def setwarnings(self, *_): pass
        def setmode(self, *_): pass
        def setup(self, *_): pass
        def output(self, *_): pass
        def cleanup(self): pass
    GPIO = _MockGPIO()  # type: ignore


class LedController:
    def setup(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for pin in config.LED_LOCATION_TO_PIN.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, config.LED_OFF)

    @staticmethod
    def _norm_color_or_location(x: str) -> Optional[str]:
        t = (x or "").strip().upper()
        if t in ("RED", "KITCHEN"):
            return config.LOC_KITCHEN
        if t in ("GREEN", "LIVING"):
            return config.LOC_LIVING
        if t in ("YELLOW", "GUEST"):
            return config.LOC_GUEST
        if t in (config.LOC_KITCHEN, config.LOC_LIVING, config.LOC_GUEST):
            return t
        return None

    def set_led(self, color: str, state: str) -> None:
        """
        color: "red"/"yellow"/"green" OR location: "KITCHEN"/"LIVING"/"GUEST"
        state: "on"/"off"
        """
        loc = self._norm_color_or_location(color)
        if loc is None:
            raise ValueError(f"Unknown LED color/location: {color}")

        st = (state or "").strip().lower()
        if st not in ("on", "off"):
            raise ValueError(f"Invalid LED state: {state}")

        pin = config.LED_LOCATION_TO_PIN[loc]
        GPIO.output(pin, config.LED_ON if st == "on" else config.LED_OFF)

    def all_off(self) -> None:
        for pin in config.LED_LOCATION_TO_PIN.values():
            GPIO.output(pin, config.LED_OFF)

    def cleanup(self) -> None:
        try:
            self.all_off()
        except Exception:
            pass
