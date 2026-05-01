#!/usr/bin/env python3
"""summarize_pipeline_results.py - Re-summarize pipeline_timing.csv"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize pipeline timing results")
    p.add_argument("--input",  default="data/eval/pipeline_timing.csv")
    p.add_argument("--output", default="data/eval/pipeline_summary.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    if df.empty:
        print("結果檔案為空。")
        return

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

    summary_df = pd.DataFrame(rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"彙總寫入: {args.output}\n")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
