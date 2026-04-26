#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.parser.fastpath_parser import FastPathParser
from src.core.parser.gemini_parser import GeminiParser

SUPPORTED_ACTIONS = {"LED", "FAN", "SET_TEMP"}


class EvalMemory:
    """In-memory memory adapter for evaluation runs."""

    def load_rules(self) -> list[dict[str, str]]:
        return []

    def get_recent_context(self, limit: int = 5) -> str:
        return "(evaluation mode: no context)"

    def add_interaction(self, user: str, assistant: str) -> None:
        return None


class EvalState:
    """Minimal state adapter expected by Gemini parser prompt builder."""

    def __init__(self) -> None:
        self.temperature = 25
        self.fan = "off"
        self.light = {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"}
        self.needs_clarification = False
        self.clarification_message = None
        self.ambient_temp = None
        self.ambient_humidity = None

    def get_state(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "fan": self.fan,
            "light": dict(self.light),
            "needs_clarification": self.needs_clarification,
            "clarification_message": self.clarification_message,
            "ambient_temp": self.ambient_temp,
            "ambient_humidity": self.ambient_humidity,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate command understanding route and action correctness."
    )
    parser.add_argument("--cases", default="data/eval/nlu_test_cases.csv", help="NLU test case CSV path")
    parser.add_argument("--output", default="data/eval/nlu_results.csv", help="Output CSV path")
    parser.add_argument("--summary", default="data/eval/nlu_summary.csv", help="Summary CSV path")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per case")
    parser.add_argument(
        "--enable-gemini",
        action="store_true",
        help="Enable Gemini fallback when fastpath has no match",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output CSV instead of append",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only run first N cases (0=all)")
    return parser.parse_args()


def normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    action_type = str(action.get("type", "")).upper()
    normalized: dict[str, Any] = {"type": action_type}
    if action_type == "LED":
        normalized["location"] = str(action.get("location", "")).upper()
        normalized["state"] = str(action.get("state", "")).lower()
    elif action_type == "FAN":
        normalized["state"] = str(action.get("state", "")).lower()
    elif action_type == "SET_TEMP":
        try:
            normalized["value"] = int(action.get("value", 0))
        except Exception:
            normalized["value"] = action.get("value")
    return normalized


def action_sort_key(action: dict[str, Any]) -> str:
    return json.dumps(action, ensure_ascii=False, sort_keys=True)


def normalize_actions(actions: List[dict[str, Any]]) -> List[dict[str, Any]]:
    normalized = [normalize_action(item) for item in actions if isinstance(item, dict)]
    return sorted(normalized, key=action_sort_key)


def parse_expected_actions(raw: Any) -> List[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def execute_actions(actions: List[dict[str, Any]]) -> tuple[bool, str]:
    for action in actions:
        action_type = str(action.get("type", "")).upper()
        if action_type not in SUPPORTED_ACTIONS:
            return False, f"unsupported_action:{action_type or 'UNKNOWN'}"
    return True, ""


def ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp",
                "run_id",
                "test_id",
                "input_text",
                "expected_route",
                "route_used",
                "route_match",
                "fastpath_hit",
                "expected_actions_json",
                "predicted_actions_json",
                "action_match",
                "execution_success",
                "intent",
                "error_code",
                "reply",
                "parse_ms",
                "execute_ms",
                "total_ms",
                "repeat_index",
                "gemini_enabled",
            ]
        )


def load_cases(path: Path, limit: int) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Case file not found: {path}")
    df = pd.read_csv(path)
    required = {"test_id", "input_text", "expected_actions_json"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in case CSV: {sorted(missing)}")
    if "expected_route" not in df.columns:
        df["expected_route"] = ""
    if limit > 0:
        df = df.head(limit)
    return df


def evaluate_row(
    input_text: str,
    expected_route: str,
    expected_actions: List[dict[str, Any]],
    fastpath: FastPathParser,
    gemini: GeminiParser,
    memory: EvalMemory,
    state: EvalState,
    enable_gemini: bool,
) -> Dict[str, Any]:
    started = time.perf_counter()

    route_used = "none"
    error_code = ""
    reply = ""
    intent = "command"

    parse_started = time.perf_counter()
    rules = memory.load_rules()
    fast_actions = fastpath.parse(input_text, rules=rules)

    if fast_actions:
        route_used = "fastpath"
        predicted_actions = fast_actions
        reply = "好的，已為您處理。"
    else:
        predicted_actions = []
        if enable_gemini:
            route_used = "gemini"
            gemini_payload = gemini.parse(input_text, state, memory)
            predicted_actions = gemini_payload.get("actions", []) if isinstance(gemini_payload, dict) else []
            intent = str(gemini_payload.get("intent", "command")) if isinstance(gemini_payload, dict) else "error"
            reply = str(gemini_payload.get("reply", "")) if isinstance(gemini_payload, dict) else ""
            if intent == "error":
                error_code = "gemini_error"
        else:
            route_used = "none"
            intent = "unparsed"
            error_code = "no_route"

    parse_ms = (time.perf_counter() - parse_started) * 1000.0

    execute_started = time.perf_counter()
    execution_success, exec_error = execute_actions(
        [item for item in predicted_actions if isinstance(item, dict)]
    )
    execute_ms = (time.perf_counter() - execute_started) * 1000.0
    if exec_error and not error_code:
        error_code = exec_error

    total_ms = (time.perf_counter() - started) * 1000.0

    expected_norm = normalize_actions(expected_actions)
    predicted_norm = normalize_actions([item for item in predicted_actions if isinstance(item, dict)])
    action_match = int(expected_norm == predicted_norm)

    expected_route_clean = (expected_route or "").strip().lower()
    route_match = 1 if not expected_route_clean else int(route_used == expected_route_clean)

    return {
        "route_used": route_used,
        "route_match": route_match,
        "fastpath_hit": int(bool(fast_actions)),
        "predicted_actions": predicted_norm,
        "expected_actions": expected_norm,
        "action_match": action_match,
        "execution_success": int(execution_success),
        "intent": intent,
        "error_code": error_code,
        "reply": reply,
        "parse_ms": round(parse_ms, 3),
        "execute_ms": round(execute_ms, 3),
        "total_ms": round(total_ms, 3),
    }


def write_summary(df: pd.DataFrame, output_path: Path) -> None:
    scopes = []

    def build_scope(scope_name: str, frame: pd.DataFrame) -> dict[str, Any]:
        return {
            "scope": scope_name,
            "samples": int(len(frame)),
            "route_match_rate": float(frame["route_match"].mean()) if len(frame) else 0.0,
            "action_match_rate": float(frame["action_match"].mean()) if len(frame) else 0.0,
            "execution_success_rate": float(frame["execution_success"].mean()) if len(frame) else 0.0,
            "fastpath_hit_rate": float(frame["fastpath_hit"].mean()) if len(frame) else 0.0,
            "mean_parse_ms": float(frame["parse_ms"].mean()) if len(frame) else 0.0,
            "p95_parse_ms": float(frame["parse_ms"].quantile(0.95)) if len(frame) else 0.0,
            "mean_total_ms": float(frame["total_ms"].mean()) if len(frame) else 0.0,
            "p95_total_ms": float(frame["total_ms"].quantile(0.95)) if len(frame) else 0.0,
        }

    scopes.append(build_scope("overall", df))
    for route in sorted(df["route_used"].astype(str).unique()):
        route_df = df[df["route_used"] == route]
        scopes.append(build_scope(f"route:{route}", route_df))

    summary_df = pd.DataFrame(scopes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    case_path = Path(args.cases)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    cases_df = load_cases(case_path, args.limit)

    if args.overwrite and output_path.exists():
        output_path.unlink()
    ensure_header(output_path)

    fastpath = FastPathParser()
    gemini = GeminiParser()
    memory = EvalMemory()
    state = EvalState()

    rows: List[Dict[str, Any]] = []
    for _, row in cases_df.iterrows():
        test_id = str(row["test_id"])
        input_text = str(row["input_text"])
        expected_route = str(row.get("expected_route", ""))
        expected_actions = parse_expected_actions(row.get("expected_actions_json", ""))

        for repeat_index in range(1, args.repeat + 1):
            result = evaluate_row(
                input_text=input_text,
                expected_route=expected_route,
                expected_actions=expected_actions,
                fastpath=fastpath,
                gemini=gemini,
                memory=memory,
                state=state,
                enable_gemini=args.enable_gemini,
            )

            row_data = {
                "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "run_id": f"N_{uuid.uuid4().hex[:10]}",
                "test_id": test_id,
                "input_text": input_text,
                "expected_route": expected_route,
                "route_used": result["route_used"],
                "route_match": result["route_match"],
                "fastpath_hit": result["fastpath_hit"],
                "expected_actions_json": json.dumps(result["expected_actions"], ensure_ascii=False),
                "predicted_actions_json": json.dumps(result["predicted_actions"], ensure_ascii=False),
                "action_match": result["action_match"],
                "execution_success": result["execution_success"],
                "intent": result["intent"],
                "error_code": result["error_code"],
                "reply": result["reply"],
                "parse_ms": result["parse_ms"],
                "execute_ms": result["execute_ms"],
                "total_ms": result["total_ms"],
                "repeat_index": repeat_index,
                "gemini_enabled": int(args.enable_gemini),
            }
            rows.append(row_data)

            print(
                f"[run] test_id={test_id} repeat={repeat_index} route={row_data['route_used']} "
                f"route_match={row_data['route_match']} action_match={row_data['action_match']} "
                f"parse_ms={row_data['parse_ms']}"
            )

    if rows:
        with output_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writerows(rows)

    result_df = pd.DataFrame(rows)
    if result_df.empty:
        print("No cases were evaluated.")
        return

    write_summary(result_df, summary_path)

    print("\n=== NLU Summary (overall) ===")
    print(
        {
            "route_match_rate": round(float(result_df["route_match"].mean()), 4),
            "action_match_rate": round(float(result_df["action_match"].mean()), 4),
            "execution_success_rate": round(float(result_df["execution_success"].mean()), 4),
            "fastpath_hit_rate": round(float(result_df["fastpath_hit"].mean()), 4),
        }
    )
    print(f"\nResults written to: {output_path}")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()
