"""
7-seg display executor.

Because 7-seg multiplexing needs continuous refresh, this module exposes a
SevenSegDisplay class that runs a small background refresh thread.

LangGraph node usage pattern:
- disp = SevenSegDisplay(); disp.setup(); disp.start()
- disp.set_number(25)  # or set_temp(25)
- ...
- disp.cleanup()
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import src.utils.config as config

# Optional GPIO fallback for non-Raspberry Pi environments.
try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:  # pragma: no cover
    class _MockGPIO:  # minimal mock
        BCM = OUT = HIGH = LOW = 0
        def setwarnings(self, *_): pass
        def setmode(self, *_): pass
        def setup(self, *_): pass
        def output(self, *_): pass
        def cleanup(self): pass
    GPIO = _MockGPIO()  # type: ignore

class SevenSegDisplay:
    def __init__(self, per_digit_sec: float = 0.002):
        self.per_digit_sec = per_digit_sec
        self._lock = threading.Lock()
        self._value_str = "  "  # two chars
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def setup(self) -> None:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        for pin in config.SEGMENTS.values():
            GPIO.setup(pin, GPIO.OUT)
            # common-anode: HIGH means off
            GPIO.output(pin, GPIO.HIGH)

        for pin in config.DIGITS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, config.DIGIT_OFF)

    def _all_digits_off(self) -> None:
        for d in config.DIGITS:
            GPIO.output(d, config.DIGIT_OFF)

    def _set_segments(self, char: str) -> None:
        pattern = config.NUM_MAP.get(char, config.NUM_MAP[" "])
        for i, seg in enumerate(["a", "b", "c", "d", "e", "f", "g"]):
            GPIO.output(config.SEGMENTS[seg], pattern[i])

    def _show_once(self, s2: str) -> None:
        # multiplex two digits
        for idx, d in enumerate(config.DIGITS):
            self._all_digits_off()
            self._set_segments(s2[idx])
            GPIO.output(d, config.DIGIT_ON)
            time.sleep(self.per_digit_sec)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            with self._lock:
                s2 = self._value_str
            self._show_once(s2)

    def set_number(self, n: int) -> None:
        n = int(n)
        if n < 0:
            s = "  "
        else:
            s = f"{n:02d}"[-2:]
        with self._lock:
            self._value_str = s

    def set_temp(self, temp: int) -> None:
        self.set_number(temp)

    def clear(self) -> None:
        with self._lock:
            self._value_str = "  "

    def cleanup(self) -> None:
        self._running = False
        try:
            self._all_digits_off()
        except Exception:
            pass
        try:
            GPIO.cleanup()
        except Exception:
            pass
