from __future__ import annotations

import os


def _apply_runtime_defaults(mode: str) -> None:
    runtime_mode = (mode or "desktop").strip().lower()
    os.environ["RUNTIME_MODE"] = runtime_mode

    if runtime_mode == "desktop":
        os.environ.setdefault("DHT11_ENABLED", "0")
        os.environ.setdefault("SPEECH_ENABLED", "1")
        os.environ.setdefault("WAKEWORD_ENABLED", "0")
        os.environ.setdefault("TTS_ENABLED", "1")
        return

    os.environ.setdefault("DHT11_ENABLED", "1")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("WAKEWORD_ENABLED", "1")
    os.environ.setdefault("TTS_ENABLED", "1")


def run_gui_app() -> None:
    try:
        from src.gui.app import run_gui
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            print("找不到 tkinter，請先安裝系統套件 python3-tk，再重新執行 --gui。")
            return
        raise

    run_gui()


def run_console_app(*, mode: str) -> None:
    _apply_runtime_defaults(mode)

    from src.true_main import run_console_app as run_console

    run_console()


def run_desktop_console() -> None:
    run_console_app(mode="desktop")


def run_hardware_console() -> None:
    run_console_app(mode="hardware")