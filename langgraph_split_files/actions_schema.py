"""
Action schema shared across LangGraph nodes/executors.

We standardize on Python dict-like actions (easy for LangGraph state),
but also provide compatibility serialization to actions.txt lines.

Canonical action dict format:
- {"type": "SET_TEMP", "value": 26}
- {"type": "FAN", "state": "on", "duration": 3}          # duration optional
- {"type": "LED", "location": "KITCHEN", "state": "on"}  # location in {KITCHEN,LIVING,GUEST}
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Union, Any, Dict, List

# ---- Dataclasses (optional, but convenient) ----
@dataclass(frozen=True)
class SetTempAction:
    value: int  # Celsius integer
    type: str = "SET_TEMP"

@dataclass(frozen=True)
class FanAction:
    state: str  # "on" | "off"
    duration: Optional[int] = None
    type: str = "FAN"

@dataclass(frozen=True)
class LedAction:
    location: str  # "KITCHEN" | "LIVING" | "GUEST"
    state: str     # "on" | "off"
    duration: Optional[int] = None
    type: str = "LED"

Action = Union[SetTempAction, FanAction, LedAction]
ActionDict = Dict[str, Any]

# ---- Conversion helpers ----
def action_to_dict(action: Union[Action, ActionDict]) -> ActionDict:
    if isinstance(action, dict):
        return dict(action)
    return asdict(action)

def dict_to_action(d: ActionDict) -> ActionDict:
    # Keep as dict (LangGraph-friendly). Validator will normalize.
    return dict(d)

# ---- actions.txt compatibility ----
def action_to_line(action: Union[Action, ActionDict]) -> str:
    d = action_to_dict(action)
    t = (d.get("type") or "").upper()

    if t == "SET_TEMP":
        return f"SET_TEMP {int(d['value'])}"

    if t == "FAN":
        state = str(d.get("state", "")).upper()
        out = f"FAN {state}"
        dur = d.get("duration", None)
        if dur is not None:
            out += f" DURATION={int(dur)}"
        return out

    if t == "LED":
        # Keep legacy controller format: LIGHT <LOCATION> <STATE>
        loc = str(d.get("location", "")).upper()
        state = str(d.get("state", "")).upper()
        out = f"LIGHT {loc} {state}"
        dur = d.get("duration", None)
        if dur is not None:
            out += f" DURATION={int(dur)}"
        return out

    raise ValueError(f"Unknown action type: {t}")

def actions_to_text(actions: List[Union[Action, ActionDict]]) -> str:
    return "\n".join(action_to_line(a) for a in actions) + ("\n" if actions else "")

def parse_action_line(line: str) -> Optional[ActionDict]:
    """
    Parse legacy action line:
      SET_TEMP 26
      FAN ON [DURATION=3]
      LIGHT KITCHEN OFF [DURATION=3]
    Returns an ActionDict or None.
    """
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None

    parts = [p for p in line.split() if p.strip()]
    if not parts:
        return None

    # extract DURATION=xx
    duration = None
    kept = []
    for p in parts:
        if p.upper().startswith("DURATION="):
            try:
                duration = int(p.split("=", 1)[1])
            except Exception:
                duration = None
        else:
            kept.append(p)
    parts = kept

    head = parts[0].upper()

    if head == "SET_TEMP" and len(parts) >= 2:
        try:
            return {"type": "SET_TEMP", "value": int(float(parts[1]))}
        except Exception:
            return None

    if head == "FAN" and len(parts) >= 2:
        st = parts[1].lower()
        if st in ("on", "off"):
            d = {"type": "FAN", "state": st}
            if duration is not None:
                d["duration"] = duration
            return d
        return None

    if head == "LIGHT" and len(parts) >= 3:
        loc = parts[1].upper()
        st = parts[2].lower()
        if st in ("on", "off"):
            d = {"type": "LED", "location": loc, "state": st}
            if duration is not None:
                d["duration"] = duration
            return d
        return None

    return None
