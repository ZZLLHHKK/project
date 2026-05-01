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

_GPIO_BACKEND = "RPi.GPIO"

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception as exc:  # pragma: no cover
    print(f"[GPIO ERROR] {exc}")
    print("[MOCK MODE ENABLED]")
    _GPIO_BACKEND = "mock"
    class _MockGPIO:
        BCM = OUT = HIGH = LOW = 0
        def setwarnings(self, *_): pass
        def setmode(self, *_): pass
        def setup(self, *_, **__): pass
        def output(self, *_): pass
        def cleanup(self): pass
    GPIO = _MockGPIO()  # type: ignore


class FanController:
    def setup(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config.RELAY_FAN, GPIO.OUT, initial=GPIO.LOW)
        print(f"[FAN GPIO] pin={config.RELAY_FAN} state=LOW backend={_GPIO_BACKEND}")

    def set_fan(self, state: str) -> None:
        st = (state or "").strip().lower()
        if st == "on":
            GPIO.output(config.RELAY_FAN, config.RELAY_ON)
            state_name = "HIGH" if config.RELAY_ON == getattr(GPIO, "HIGH", None) else "LOW"
            print(f"[FAN GPIO] pin={config.RELAY_FAN} state={state_name}")
        elif st == "off":
            GPIO.output(config.RELAY_FAN, config.RELAY_OFF)
            state_name = "HIGH" if config.RELAY_OFF == getattr(GPIO, "HIGH", None) else "LOW"
            print(f"[FAN GPIO] pin={config.RELAY_FAN} state={state_name}")
        else:
            raise ValueError(f"Invalid fan state: {state}")

    def cleanup(self) -> None:
        try:
            self.set_fan("off")
        except Exception:
            pass
