"""
Action validation & normalization for src.
"""
from typing import List, Any, Optional
import math
import src.utils.config as config
from src.core.actions_schema import ActionDict

class ActionValidator:	
	@staticmethod
	def _to_int_round_half_up(x: float) -> int:
		return int(math.floor(x + 0.5))

	@staticmethod
	def _clamp(x: float, lo: float, hi: float) -> float:
		return max(lo, min(hi, x))

	@staticmethod
	def _norm_state(s: Any) -> Optional[str]:
		if s is None:
			return None
		t = str(s).strip().lower()
		if t in ("on", "open", "1", "true"):
			return "on"
		if t in ("off", "close", "0", "false"):
			return "off"
		return None

	@staticmethod
	def _norm_location(loc: Any) -> Optional[str]:
		if loc is None:
			return None
		t = str(loc).strip().upper()
		if t in ("RED", "KITCHEN"):
			return config.LOC_KITCHEN
		if t in ("GREEN", "LIVING"):
			return config.LOC_LIVING
		if t in ("YELLOW", "GUEST"):
			return config.LOC_GUEST
		if t in (config.LOC_KITCHEN, config.LOC_LIVING, config.LOC_GUEST):
			return t
		return None

	@staticmethod
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
			v = ActionValidator._clamp(v, config.MIN_TEMP, config.MAX_TEMP)
			vi = ActionValidator._to_int_round_half_up(v)
			vi = int(ActionValidator._clamp(vi, int(config.MIN_TEMP), int(config.MAX_TEMP)))
			return {"type": "SET_TEMP", "value": vi}
		if t == "FAN":
			st = ActionValidator._norm_state(a.get("state"))
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
			loc = ActionValidator._norm_location(a.get("location"))
			st = ActionValidator._norm_state(a.get("state"))
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

	@staticmethod
	def validate_actions(actions: List[ActionDict]) -> List[ActionDict]:
		out: List[ActionDict] = []
		for a in actions or []:
			va = ActionValidator.validate_action(a)
			if va is not None:
				out.append(va)
		return out


def validate_actions(actions: List[ActionDict]) -> List[ActionDict]:
	"""Backward-compatible wrapper for modules importing validate_actions directly."""
	return ActionValidator.validate_actions(actions)
