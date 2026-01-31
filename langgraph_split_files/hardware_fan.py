"""
Fan relay executor.

LangGraph node usage:
- setup()
- set_fan("on") / set_fan("off")
- cleanup()
"""
from __future__ import annotations

import config

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

def setup() -> None:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(config.RELAY_FAN, GPIO.OUT)
    # OFF by default
    GPIO.output(config.RELAY_FAN, config.RELAY_OFF)

def set_fan(state: str) -> None:
    st = (state or "").strip().lower()
    if st == "on":
        GPIO.output(config.RELAY_FAN, config.RELAY_ON)
    elif st == "off":
        GPIO.output(config.RELAY_FAN, config.RELAY_OFF)
    else:
        raise ValueError(f"Invalid fan state: {state}")

def cleanup() -> None:
    try:
        set_fan("off")
    finally:
        try:
            GPIO.cleanup()
        except Exception:
            pass
