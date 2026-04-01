"""
Fan relay executor.

LangGraph node usage:
    fan = FanController()
    fan.setup()
    fan.set_fan("on")
    fan.cleanup()
"""
from __future__ import annotations

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


class FanController:
    def setup(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config.RELAY_FAN, GPIO.OUT, initial=GPIO.LOW)

    def set_fan(self, state: str) -> None:
        st = (state or "").strip().lower()
        if st == "on":
            GPIO.output(config.RELAY_FAN, config.RELAY_ON)
        elif st == "off":
            GPIO.output(config.RELAY_FAN, config.RELAY_OFF)
        else:
            raise ValueError(f"Invalid fan state: {state}")

    def cleanup(self) -> None:
        try:
            self.set_fan("off")
        except Exception:
            pass
