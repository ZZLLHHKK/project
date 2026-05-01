#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize STT evaluation results by model and export CSV."
    )
    parser.add_argument("--input",    default="data/eval/results.csv")
    parser.add_argument("--output",   default="data/eval/summary_by_model.csv")
    parser.add_argument("--warm-only", action="store_true",
                        help="Only include startup_state=Warm rows in summary.")
    parser.add_argument("--pc-rows",  type=int, default=432,
                        help="Number of data rows belonging to PC (default 432).")
    return parser.parse_args()


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
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

    return summary


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    required = {"model_size", "run_id", "cer", "sentence_correct",
                "inference_ms", "rtf", "startup_state"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if args.warm_only:
        df = df[df["startup_state"].astype(str).str.lower() == "warm"].copy()

    if df.empty:
        raise ValueError("No rows available after filtering.")

    pc_df = df.iloc[:args.pc_rows].copy()
    pi_df = df.iloc[args.pc_rows:].copy()

    rows = []

    if not pc_df.empty:
        pc_summary = build_summary(pc_df)
        pc_summary.insert(0, "env", "pc")
        rows.append(pc_summary)
        print("=== PC 結果 ===")
        print(pc_summary.to_string(index=False))

    if not pi_df.empty:
        pi_summary = build_summary(pi_df)
        pi_summary.insert(0, "env", "pi")
        rows.append(pi_summary)
        print("\n=== Pi 結果 ===")
        print(pi_summary.to_string(index=False))

    combined = pd.concat(rows, ignore_index=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n彙總寫入：{output_path}")


if __name__ == "__main__":
    main()
