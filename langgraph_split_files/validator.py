"""
Validation & normalization for actions.

This is the safety layer: it clamps temperature, normalizes states, and
rejects unknown devices/fields.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import math

import config
from actions_schema import ActionDict

def _to_int_round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _norm_state(s: Any) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip().lower()
    if t in ("on", "open", "1", "true"):
        return "on"
    if t in ("off", "close", "0", "false"):
        return "off"
    return None

def _norm_location(loc: Any) -> Optional[str]:
    if loc is None:
        return None
    t = str(loc).strip().upper()
    # allow color aliases if someone uses them
    if t in ("RED", "KITCHEN"):
        return config.LOC_KITCHEN
    if t in ("GREEN", "LIVING"):
        return config.LOC_LIVING
    if t in ("YELLOW", "GUEST"):
        return config.LOC_GUEST
    if t in (config.LOC_KITCHEN, config.LOC_LIVING, config.LOC_GUEST):
        return t
    return None

def validate_action(a: ActionDict) -> Optional[ActionDict]:
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
        v = _clamp(v, config.MIN_TEMP, config.MAX_TEMP)
        vi = _to_int_round_half_up(v)
        vi = int(_clamp(vi, int(config.MIN_TEMP), int(config.MAX_TEMP)))
        return {"type": "SET_TEMP", "value": vi}

    if t == "FAN":
        st = _norm_state(a.get("state"))
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
        loc = _norm_location(a.get("location"))
        st = _norm_state(a.get("state"))
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

def validate_actions(actions: List[ActionDict]) -> List[ActionDict]:
    out: List[ActionDict] = []
    for a in actions or []:
        va = validate_action(a)
        if va is not None:
            out.append(va)
    return out
