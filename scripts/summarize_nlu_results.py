#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "route_used",
    "route_match",
    "action_match",
    "execution_success",
    "fastpath_hit",
    "parse_ms",
    "total_ms",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize NLU evaluation results")
    parser.add_argument("--input", default="data/eval/nlu_results.csv", help="Input CSV path")
    parser.add_argument("--output", default="data/eval/nlu_summary.csv", help="Output summary CSV path")
    return parser.parse_args()


def build_scope(scope: str, frame: pd.DataFrame) -> dict:
    return {
        "scope": scope,
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


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    rows = [build_scope("overall", df)]
    for route in sorted(df["route_used"].astype(str).unique()):
        rows.append(build_scope(f"route:{route}", df[df["route_used"] == route]))

    summary_df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(summary_df.to_string(index=False))
    print(f"\nSummary written to: {output_path}")


if __name__ == "__main__":
    main()
