# compat/ — re-export shims
# 這些檔案把深層模組的公開介面集中暴露，方便外部直接從 src.compat 引用。
# 專案內部請直接引用真實路徑（src.core.agent、src.devices.device_controller 等）。
from src.compat.agent import ActionExecutionError, SmartHomeAgent
from src.compat.device_controller import DeviceController
from src.compat.fastpath_parser import FastPathParser, parse as parse_fastpath, parse_fastpath as parse_fastpath_fn, try_learn_rule
from src.compat.gemini_parser import GeminiParser, parse as parse_gemini, parse_with_gemini
from src.compat.memory_agent import MemoryAgent
from src.compat.state_manager import StateManager

__all__ = [
    "ActionExecutionError",
    "SmartHomeAgent",
    "DeviceController",
    "FastPathParser",
    "GeminiParser",
    "MemoryAgent",
    "StateManager",
    "try_learn_rule",
    "parse_with_gemini",
]
