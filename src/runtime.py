from __future__ import annotations

import os
from dataclasses import dataclass

from src.core.agent import SmartHomeAgent
from src.core.memory_agent import MemoryAgent
from src.core.state_manager import StateManager
from src.devices.device_controller import DeviceController


@dataclass(slots=True)
class AppRuntime:
    mode: str
    state: StateManager
    memory: MemoryAgent
    agent: SmartHomeAgent
    device: DeviceController | None = None


def _apply_desktop_defaults(state: StateManager) -> None:
    state.ambient_temp = int(os.environ.get("DESKTOP_AMBIENT_TEMP", state.ambient_temp or 26))
    state.ambient_humidity = int(os.environ.get("DESKTOP_AMBIENT_HUMIDITY", state.ambient_humidity or 60))


def _sync_device_from_state(device: DeviceController, state: StateManager) -> None:
    device.set_temp(state.temperature)
    device.set_fan(state.fan)
    for location, light_state in state.light.items():
        device.set_led(location, light_state)


def build_runtime(
    *,
    mode: str,
    memory_keep: int | None = None,
    with_device: bool = False,
    setup_device: bool = False,
) -> AppRuntime:
    if setup_device and not with_device:
        raise ValueError("setup_device=True requires with_device=True")

    runtime_mode = (mode or "desktop").strip().lower()
    memory_kwargs: dict[str, int] = {}
    if memory_keep is not None:
        memory_kwargs["keep"] = memory_keep

    state = StateManager()
    memory = MemoryAgent(**memory_kwargs)

    if runtime_mode == "desktop":
        _apply_desktop_defaults(state)

    device: DeviceController | None = None
    if with_device:
        device = DeviceController()
        if setup_device:
            device.setup()
            _sync_device_from_state(device, state)

    agent = SmartHomeAgent(memory=memory, state=state, device_controller=device)
    return AppRuntime(mode=runtime_mode, state=state, memory=memory, agent=agent, device=device)