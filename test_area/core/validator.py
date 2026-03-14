"""
Validation & normalization for actions.

This is the safety layer: it clamps temperature, normalizes states, and
rejects unknown devices/fields.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import math

import src.utils.config as config
from src.nodes.langgraph_split_files.actions_schema import ActionDict

class ActionValidator:
    """Validate and normalize smart-home actions."""

    def __init__(
        self,
        min_temp: float = config.MIN_TEMP,
        max_temp: float = config.MAX_TEMP,
        kitchen_loc: str = config.LOC_KITCHEN,
        living_loc: str = config.LOC_LIVING,
        guest_loc: str = config.LOC_GUEST,
    ) -> None:
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.kitchen_loc = kitchen_loc
        self.living_loc = living_loc
        self.guest_loc = guest_loc

    def _to_int_round_half_up(self, x: float) -> int:
        return int(math.floor(x + 0.5))

    def _clamp(self, x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def _norm_state(self, s: Any) -> Optional[str]:
        if s is None:
            return None
        t = str(s).strip().lower()
        if t in ("on", "open", "1", "true"):
            return "on"
        if t in ("off", "close", "0", "false"):
            return "off"
        return None

    def _norm_location(self, loc: Any) -> Optional[str]:
        if loc is None:
            return None
        t = str(loc).strip().upper()
        # Allow color aliases used by legacy voice phrases.
        if t in ("RED", "KITCHEN"):
            return self.kitchen_loc
        if t in ("GREEN", "LIVING"):
            return self.living_loc
        if t in ("YELLOW", "GUEST"):
            return self.guest_loc
        if t in (self.kitchen_loc, self.living_loc, self.guest_loc):
            return t
        return None

    def validate_action(self, a: ActionDict) -> Optional[ActionDict]:
        if not isinstance(a, dict):
            return None

        t = str(a.get("type", "")).strip().upper()

        if t == "SET_TEMP":
            if "value" not in a:
                return None
            try:
                v = float(a["value"])
            except Exception:
                return None
            v = self._clamp(v, self.min_temp, self.max_temp)
            vi = self._to_int_round_half_up(v)
            vi = int(self._clamp(vi, int(self.min_temp), int(self.max_temp)))
            return {"type": "SET_TEMP", "value": vi}

        if t == "FAN":
            st = self._norm_state(a.get("state"))
            if st is None:
                return None
            out: ActionDict = {"type": "FAN", "state": st}
            dur = a.get("duration", None)
            if dur is not None:
                try:
                    di = int(dur)
                    if di >= 0:
                        out["duration"] = di
                except Exception:
                    pass
            return out

        if t == "LED":
            loc = self._norm_location(a.get("location"))
            st = self._norm_state(a.get("state"))
            if loc is None or st is None:
                return None
            out = {"type": "LED", "location": loc, "state": st}
            dur = a.get("duration", None)
            if dur is not None:
                try:
                    di = int(dur)
                    if di >= 0:
                        out["duration"] = di
                except Exception:
                    pass
            return out

        return None

    def validate_actions(self, actions: List[ActionDict]) -> List[ActionDict]:
        out: List[ActionDict] = []
        for a in actions or []:
            va = self.validate_action(a)
            if va is not None:
                out.append(va)
        return out


DEFAULT_VALIDATOR = ActionValidator()


def validate_action(a: ActionDict) -> Optional[ActionDict]:
    """Backward-compatible function wrapper."""
    return DEFAULT_VALIDATOR.validate_action(a)


def validate_actions(actions: List[ActionDict]) -> List[ActionDict]:
    """Backward-compatible function wrapper."""
    return DEFAULT_VALIDATOR.validate_actions(actions)
