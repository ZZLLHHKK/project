#!/usr/bin/env python3
"""
hardware_dht11.py - DHT11 sensor reader (temperature/humidity)

This module tries multiple common Python libraries in order:
1) adafruit-circuitpython-dht (recommended)  -> import adafruit_dht, board
2) Adafruit_DHT (legacy)                    -> import Adafruit_DHT

Public API:
- read_once() -> (temp_c: float|None, humidity: float|None)
- DHT11Reader: background thread that keeps latest readings
"""

from __future__ import annotations

import time
import threading
from typing import Optional, Tuple

import src.utils.config as config

# -------------------------
# Library detection
# -------------------------
_BACKEND = "none"

# Backend A: adafruit-circuitpython-dht
_ada_dht = None
_board = None
_device = None

try:
    import adafruit_dht  # type: ignore
    import board  # type: ignore

    _ada_dht = adafruit_dht
    _board = board
    _BACKEND = "adafruit_circuitpython_dht"
except Exception:
    _ada_dht = None
    _board = None

# Backend B: Adafruit_DHT (legacy)
_legacy = None
try:
    import Adafruit_DHT  # type: ignore

    _legacy = Adafruit_DHT
    if _BACKEND == "none":
        _BACKEND = "adafruit_dht_legacy"
except Exception:
    _legacy = None


def _board_pin_from_bcm(bcm: int):
    """
    Map BCM pin number to board.Dxx constant if available.
    board uses GPIO naming like board.D4 == BCM4.
    """
    if _board is None:
        return None
    name = f"D{int(bcm)}"
    return getattr(_board, name, None)


def _safe_round_temp(temp_c: Optional[float]) -> Optional[int]:
    if temp_c is None:
        return None
    try:
        # DHT11 often reports integer-ish values; keep stable rounding
        return int(float(temp_c) + 0.5)
    except Exception:
        return None


def read_once() -> Tuple[Optional[float], Optional[float]]:
    """
    Read one sample from DHT11.

    Returns (temp_c, humidity). Either can be None.
    """
    pin = int(config.DHT11_PIN)

    # --- Backend A ---
    if _BACKEND == "adafruit_circuitpython_dht" and _ada_dht is not None and _board is not None:
        global _device
        try:
            if _device is None:
                bp = _board_pin_from_bcm(pin)
                if bp is None:
                    # Cannot map pin; fall back to legacy backend if present
                    raise RuntimeError(f"board has no attribute D{pin}")
                _device = _ada_dht.DHT11(bp)

            # Adafruit lib raises RuntimeError frequently; just retry next loop
            temp_c = _device.temperature
            hum = _device.humidity
            return (float(temp_c) if temp_c is not None else None,
                    float(hum) if hum is not None else None)
        except Exception:
            return (None, None)

    # --- Backend B ---
    if _BACKEND == "adafruit_dht_legacy" and _legacy is not None:
        try:
            hum, temp_c = _legacy.read_retry(_legacy.DHT11, pin)  # BCM pin
            return (float(temp_c) if temp_c is not None else None,
                    float(hum) if hum is not None else None)
        except Exception:
            return (None, None)

    return (None, None)


class DHT11Reader:
    """
    Background reader. Use:
      r = DHT11Reader(); r.start()
      t = r.get_temp_int()
      r.stop()
    """

    def __init__(self, interval_sec: float = None):
        self.interval_sec = float(interval_sec if interval_sec is not None else config.DHT11_READ_INTERVAL_SEC)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_temp_c: Optional[float] = None
        self._last_humidity: Optional[float] = None
        self._last_ok_ts: float = 0.0

    def start(self) -> None:
        if not config.DHT11_ENABLED:
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass

        # try to release resources for adafruit_dht
        global _device
        if _device is not None:
            try:
                _device.exit()
            except Exception:
                pass
            _device = None

    def _loop(self) -> None:
        # DHT11 needs a short warm-up
        time.sleep(0.8)
        while self._running:
            temp_c, hum = read_once()
            if temp_c is not None:
                with self._lock:
                    self._last_temp_c = temp_c
                    self._last_humidity = hum
                    self._last_ok_ts = time.time()
            time.sleep(max(0.5, self.interval_sec))

    def get_temp_c(self) -> Optional[float]:
        with self._lock:
            return self._last_temp_c

    def get_temp_int(self) -> Optional[int]:
        with self._lock:
            return _safe_round_temp(self._last_temp_c)

    def get_humidity(self) -> Optional[float]:
        with self._lock:
            return self._last_humidity

    def last_ok_age_sec(self) -> float:
        with self._lock:
            if self._last_ok_ts <= 0:
                return 1e9
            return time.time() - self._last_ok_ts
