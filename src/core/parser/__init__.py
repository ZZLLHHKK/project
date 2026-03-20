"""Parser package initialization.

Provides:
- Stable exports for parser classes/functions.
- A small facade for `fastpath -> gemini fallback` flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .fastpath_parser import (
	DeviceCommandParser,
	FastPathParser,
	HistoryRecorder,
	RuleApplier,
	RuleLearner,
	TemperatureParser,
	apply_memory_rules,
	extract_explicit_temp,
	parse_fastpath,
	try_learn_rule,
)
from .gemini_parser import GeminiParser, PromptBuilder, ResponseParser, parse_with_gemini
import random
import re

@dataclass(slots=True)
class ParserFacade: 
	"""Unified parser entrypoint for application use.

	Flow:
	1) learn_rule (if user teaches a new phrase)
	2) fastpath parse (explicit commands)
	3) gemini fallback (fuzzy/complex commands)
	"""

	fastpath: FastPathParser
	gemini: GeminiParser

	def parse(
		self,
		user_text: str,
		current_temp: Optional[int] = None,
		ambient_temp: Optional[int] = None,
		ambient_humidity: Optional[int] = None,
		fan_state: str = "off",
		led_states: Optional[dict] = None,
		return_reply: bool = False,
	):

		learned = self.fastpath.learn_rule(user_text)
		if learned is not None:
			if return_reply:
				return [], "好的，我已經記住這條規則。"
			return []

		fast_actions = self.fastpath.parse(user_text)
		if fast_actions:
			if return_reply:
				if re.search(r'[A-Za-z]', user_text):
					reply_text = random.choice(["Got it.", "Right away.", "Done."])
				else:
					reply_text = random.choice(["好的，馬上為您處理。", "沒問題，幫您執行。", "收到。"])
					
				return fast_actions, reply_text, "command"
		
			return fast_actions

		return self.gemini.parse(
			user_text=user_text,
			current_temp=current_temp,
			ambient_temp=ambient_temp,
			ambient_humidity=ambient_humidity,
			fan_state=fan_state,
			led_states=led_states,
			return_reply=return_reply,
		)


def init_parser_facade() -> ParserFacade:
	"""Factory for a default parser facade instance."""
	return ParserFacade(fastpath=FastPathParser(), gemini=GeminiParser())


DEFAULT_PARSER = init_parser_facade()


__all__ = [
	"DeviceCommandParser",
	"FastPathParser",
	"GeminiParser",
	"HistoryRecorder",
	"ParserFacade",
	"PromptBuilder",
	"ResponseParser",
	"RuleApplier",
	"RuleLearner",
	"TemperatureParser",
	"DEFAULT_PARSER",
	"apply_memory_rules",
	"extract_explicit_temp",
	"init_parser_facade",
	"parse_fastpath",
	"parse_with_gemini",
	"try_learn_rule",
]
