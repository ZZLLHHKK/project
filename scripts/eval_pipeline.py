#!/usr/bin/env python3
"""
eval_pipeline.py - Phase 3: End-to-end latency & bottleneck analysis

Segments measured:
  record_ms      - pre-recorded audio duration (speaking time proxy)
  stt_ms         - Whisper transcription time
  parse_ms       - fastpath / gemini parsing time
  action_ms      - action execution (mock validation on PC, GPIO on Pi)
  tts_ms         - TTS generation + playback (0 if --no-tts)
  end_to_end_ms  - stt_ms + parse_ms + action_ms + tts_ms

Compatible with PC (desktop) and Raspberry Pi (hardware).
Default: --repeat 3, Gemini enabled, TTS disabled.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.parser.fastpath_parser import FastPathParser
from src.core.parser.gemini_parser import GeminiParser

SUPPORTED_ACTIONS = {"LED", "FAN", "SET_TEMP"}

FIELDNAMES = [
    "timestamp", "run_id", "test_id", "repeat_index",
    "stt_text", "route_used",
    "record_ms", "stt_ms", "parse_ms", "action_ms", "tts_ms", "end_to_end_ms",
    "success", "fail_stage", "note",
]


# ── Eval stubs ─────────────────────────────────────────────────────────────────

class EvalMemory:
    def load_rules(self) -> list:
        return []

    def get_recent_context(self, limit: int = 5) -> str:
        return "(eval mode)"

    def add_interaction(self, user: str, assistant: str) -> None:
        return None


class EvalState:
    def __init__(self) -> None:
        self.temperature = 25
        self.fan = "off"
        self.light = {"KITCHEN": "off", "LIVING": "off", "GUEST": "off"}
        self.needs_clarification = False
        self.clarification_message = None
        self.ambient_temp: Optional[int] = None
        self.ambient_humidity: Optional[int] = None

    def get_state(self) -> dict:
        return {
            "temperature": self.temperature,
            "fan": self.fan,
            "light": dict(self.light),
            "needs_clarification": self.needs_clarification,
            "clarification_message": self.clarification_message,
            "ambient_temp": self.ambient_temp,
            "ambient_humidity": self.ambient_humidity,
        }


# ── Segment runners ────────────────────────────────────────────────────────────

def wav_duration_ms(wav_path: str) -> float:
    try:
        with wave.open(wav_path, "rb") as wf:
            return wf.getnframes() / wf.getframerate() * 1000.0
    except Exception:
        return 0.0


def run_stt(wav_path: str) -> Tuple[str, float]:
    from src.utils.whisper_local import transcribe_latest_wav
    t0 = time.perf_counter()
    text = transcribe_latest_wav(input_wav=wav_path, language="zh", model_name=None)
    ms = (time.perf_counter() - t0) * 1000.0
    return ("" if text == "[無辨識結果]" else text.strip()), ms


def run_parse(
    text: str,
    fastpath: FastPathParser,
    gemini: GeminiParser,
    memory: EvalMemory,
    state: EvalState,
    enable_gemini: bool,
) -> Tuple[str, list, str, float]:
    t0 = time.perf_counter()
    rules = memory.load_rules()
    fast_actions = fastpath.parse(text, rules=rules)

    if fast_actions:
        route_used = "fastpath"
        actions = fast_actions
        reply = "好的，已為您處理。"
    elif enable_gemini and text:
        route_used = "gemini"
        payload = gemini.parse(text, state, memory)
        actions = payload.get("actions", []) if isinstance(payload, dict) else []
        reply = str(payload.get("reply", "")) if isinstance(payload, dict) else ""
    else:
        route_used = "none"
        actions = []
        reply = ""

    ms = (time.perf_counter() - t0) * 1000.0
    return route_used, actions, reply, ms


def run_action(actions: list) -> Tuple[bool, float]:
    t0 = time.perf_counter()
    success = True

    try:
        from src.devices.device_controller import DeviceController
        ctrl = DeviceController()
        ctrl.setup()
        for action in actions:
            atype = str(action.get("type", "")).upper()
            if atype == "LED":
                ctrl.set_led(action.get("location", ""), action.get("state", "off"))
            elif atype == "FAN":
                ctrl.set_fan(action.get("state", "off"))
            elif atype == "SET_TEMP":
                ctrl.set_temp(int(action.get("value", 25)))
    except Exception:
        for action in actions:
            if str(action.get("type", "")).upper() not in SUPPORTED_ACTIONS:
                success = False
                break

    ms = (time.perf_counter() - t0) * 1000.0
    return success, ms


def run_tts(reply: str, enabled: bool) -> float:
    if not enabled or not reply:
        return 0.0
    t0 = time.perf_counter()
    try:
        from src.utils.tts import speak
        speak(reply)
    except Exception:
        return 0.0
    return (time.perf_counter() - t0) * 1000.0


# ── Output ─────────────────────────────────────────────────────────────────────

def ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def write_summary(df: pd.DataFrame, path: Path) -> None:
    segments = ["stt_ms", "parse_ms", "action_ms", "tts_ms", "end_to_end_ms"]
    rows = []

    def build_row(scope: str, frame: pd.DataFrame) -> dict:
        row: dict = {"scope": scope, "samples": len(frame)}
        total_mean = float(frame["end_to_end_ms"].mean()) if len(frame) else 0.0
        for seg in segments:
            mean = float(frame[seg].mean()) if len(frame) else 0.0
            p95 = float(frame[seg].quantile(0.95)) if len(frame) else 0.0
            row[f"{seg}_mean"] = round(mean, 2)
            row[f"{seg}_p95"] = round(p95, 2)
            if seg != "end_to_end_ms" and total_mean > 0:
                row[f"{seg}_pct"] = round(mean / total_mean * 100, 1)
        return row

    rows.append(build_row("overall", df))
    for route in sorted(df["route_used"].astype(str).unique()):
        rows.append(build_row(f"route:{route}", df[df["route_used"] == route]))

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


# ── CLI & main ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 3: end-to-end pipeline timing")
    p.add_argument("--cases",          default="data/eval/test_cases.csv")
    p.add_argument("--audio-dir",      default="data/recordings/eval")
    p.add_argument("--output",         default="data/eval/pipeline_timing.csv")
    p.add_argument("--summary",        default="data/eval/pipeline_summary.csv")
    p.add_argument("--repeat",         type=int, default=3, help="Runs per case (default 3)")
    p.add_argument("--limit",          type=int, default=0, help="Only run first N cases")
    p.add_argument("--overwrite",      action="store_true")
    p.add_argument("--disable-gemini", action="store_true", help="Disable Gemini fallback")
    p.add_argument("--with-tts",       action="store_true", help="Enable TTS playback measurement")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    case_path = Path(args.cases)
    audio_dir = Path(args.audio_dir)
    output_path = Path(args.output)
    summary_path = Path(args.summary)
    enable_gemini = not args.disable_gemini
    tts_enabled = args.with_tts

    cases_df = pd.read_csv(case_path)
    if args.limit > 0:
        cases_df = cases_df.head(args.limit)

    if args.overwrite and output_path.exists():
        output_path.unlink()
    ensure_header(output_path)

    fastpath = FastPathParser()
    gemini = GeminiParser()
    memory = EvalMemory()
    state = EvalState()

    print(f"[設定] repeat={args.repeat}, gemini={'on' if enable_gemini else 'off'}, tts={'on' if tts_enabled else 'off'}")
    print(f"[設定] 案例數={len(cases_df)}, 音檔目錄={audio_dir}\n")

    rows: List[Dict[str, Any]] = []

    for _, case in cases_df.iterrows():
        test_id = str(case["test_id"])
        audio_file = str(case.get("audio_file", ""))
        note = str(case.get("note", ""))
        wav_path = str(audio_dir / audio_file)

        if not Path(wav_path).exists():
            print(f"[skip] {test_id}: 找不到音檔 {wav_path}")
            continue

        rec_ms = wav_duration_ms(wav_path)

        for repeat_idx in range(1, args.repeat + 1):
            fail_stage = ""

            stt_text, stt_ms = run_stt(wav_path)
            if not stt_text:
                fail_stage = "stt"

            route_used, actions, reply, parse_ms = run_parse(
                stt_text, fastpath, gemini, memory, state, enable_gemini
            )
            if not fail_stage and route_used == "none":
                fail_stage = "parse"

            success, action_ms = run_action(actions)
            if not fail_stage and not success:
                fail_stage = "action"

            tts_ms = run_tts(reply, tts_enabled)

            end_to_end_ms = stt_ms + parse_ms + action_ms + tts_ms

            row = {
                "timestamp":     datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "run_id":        f"P_{uuid.uuid4().hex[:10]}",
                "test_id":       test_id,
                "repeat_index":  repeat_idx,
                "stt_text":      stt_text,
                "route_used":    route_used,
                "record_ms":     round(rec_ms, 1),
                "stt_ms":        round(stt_ms, 1),
                "parse_ms":      round(parse_ms, 3),
                "action_ms":     round(action_ms, 3),
                "tts_ms":        round(tts_ms, 1),
                "end_to_end_ms": round(end_to_end_ms, 1),
                "success":       int(not fail_stage),
                "fail_stage":    fail_stage,
                "note":          note,
            }
            rows.append(row)

            print(
                f"[{test_id}] r={repeat_idx} route={route_used:<9} "
                f"stt={stt_ms:6.0f}ms parse={parse_ms:7.1f}ms "
                f"action={action_ms:5.1f}ms tts={tts_ms:5.0f}ms "
                f"total={end_to_end_ms:7.0f}ms"
                + (f" FAIL:{fail_stage}" if fail_stage else "")
            )

    if not rows:
        print("沒有任何案例被執行。")
        return

    with output_path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writerows(rows)

    result_df = pd.DataFrame(rows)
    write_summary(result_df, summary_path)

    print("\n=== Pipeline Timing Summary ===")
    total_mean = result_df["end_to_end_ms"].mean()
    for seg in ["stt_ms", "parse_ms", "action_ms", "tts_ms"]:
        mean = result_df[seg].mean()
        p95 = result_df[seg].quantile(0.95)
        pct = mean / total_mean * 100 if total_mean > 0 else 0
        print(f"  {seg:>12}: mean={mean:7.1f}ms  p95={p95:7.1f}ms  占比={pct:5.1f}%")
    print(f"  {'end_to_end':>12}: mean={total_mean:7.1f}ms  p95={result_df['end_to_end_ms'].quantile(0.95):7.1f}ms")
    print(f"\n結果寫入: {output_path}")
    print(f"彙總寫入: {summary_path}")


if __name__ == "__main__":
    main()
