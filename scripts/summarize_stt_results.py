#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize STT evaluation results by model and export CSV."
    )
    parser.add_argument(
        "--input",
        default="data/eval/results.csv",
        help="Input results CSV path.",
    )
    parser.add_argument(
        "--output",
        default="data/eval/summary_by_model.csv",
        help="Output summary CSV path.",
    )
    parser.add_argument(
        "--warm-only",
        action="store_true",
        help="Only include startup_state=Warm rows in summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    required = {
        "model_size",
        "run_id",
        "cer",
        "sentence_correct",
        "inference_ms",
        "rtf",
        "startup_state",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {sorted(missing)}")

    if args.warm_only:
        df = df[df["startup_state"].astype(str).str.lower() == "warm"].copy()

    if df.empty:
        raise ValueError("No rows available for summary after filtering.")

    warm_df = df[df["startup_state"].astype(str).str.lower() == "warm"].copy()

    summary = (
        df.groupby("model_size", as_index=False)
        .agg(
            samples=("run_id", "count"),
            mean_cer=("cer", "mean"),
            median_cer=("cer", "median"),
            sentence_accuracy=("sentence_correct", "mean"),
            mean_inference_ms=("inference_ms", "mean"),
            p95_inference_ms=("inference_ms", lambda s: float(s.quantile(0.95))),
            mean_rtf=("rtf", "mean"),
        )
        .sort_values("model_size")
    )

    if not warm_df.empty:
        warm_summary = (
            warm_df.groupby("model_size", as_index=False)
            .agg(
                warm_samples=("run_id", "count"),
                mean_warm_inference_ms=("inference_ms", "mean"),
                p95_warm_inference_ms=("inference_ms", lambda s: float(s.quantile(0.95))),
            )
            .sort_values("model_size")
        )
        summary = summary.merge(warm_summary, on="model_size", how="left")
    else:
        summary["warm_samples"] = 0
        summary["mean_warm_inference_ms"] = 0.0
        summary["p95_warm_inference_ms"] = 0.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(summary.to_string(index=False))
    print(f"\nSummary written to: {output_path}")


if __name__ == "__main__":
    main()
