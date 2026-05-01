#!/usr/bin/env python3
"""summarize_pipeline_results.py - Re-summarize pipeline_timing.csv

PC 與 Pi 的區分方式：
  tts_ms == 0  → PC（執行時未加 --with-tts）
  tts_ms  > 0  → Pi（執行時加了 --with-tts）
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize pipeline timing results")
    p.add_argument("--input",  default="data/eval/pipeline_timing.csv")
    p.add_argument("--output", default="data/eval/pipeline_summary.csv")
    return p.parse_args()


def build_scope_row(scope: str, frame: pd.DataFrame, include_tts: bool) -> dict:
    segments = ["stt_ms", "parse_ms", "action_ms", "end_to_end_ms"]
    if include_tts:
        segments = ["stt_ms", "parse_ms", "action_ms", "tts_ms", "end_to_end_ms"]

    row: dict = {"scope": scope, "samples": len(frame)}
    total_mean = float(frame["end_to_end_ms"].mean()) if len(frame) else 0.0

    for seg in segments:
        mean = float(frame[seg].mean()) if len(frame) else 0.0
        p95  = float(frame[seg].quantile(0.95)) if len(frame) else 0.0
        row[f"{seg}_mean"] = round(mean, 2)
        row[f"{seg}_p95"]  = round(p95, 2)
        if seg != "end_to_end_ms" and total_mean > 0:
            row[f"{seg}_pct"] = round(mean / total_mean * 100, 1)

    return row


def summarize(label: str, df: pd.DataFrame, include_tts: bool) -> list[dict]:
    rows = []
    rows.append(build_scope_row(f"{label}:overall", df, include_tts))
    for route in sorted(df["route_used"].astype(str).unique()):
        sub = df[df["route_used"] == route]
        rows.append(build_scope_row(f"{label}:route:{route}", sub, include_tts))
    return rows


def print_summary(label: str, df: pd.DataFrame, include_tts: bool) -> None:
    segments = ["stt_ms", "parse_ms", "action_ms", "end_to_end_ms"]
    if include_tts:
        segments = ["stt_ms", "parse_ms", "action_ms", "tts_ms", "end_to_end_ms"]

    print(f"\n{'='*50}")
    print(f"  {label}  （{len(df)} 筆）")
    print(f"{'='*50}")
    total_mean = df["end_to_end_ms"].mean()
    for seg in segments:
        mean = df[seg].mean()
        p95  = df[seg].quantile(0.95)
        pct  = mean / total_mean * 100 if seg != "end_to_end_ms" and total_mean > 0 else 100
        marker = " ◀ 瓶頸" if seg != "end_to_end_ms" and pct >= 40 else ""
        print(f"  {seg:>15}: mean={mean:8.1f}ms  p95={p95:8.1f}ms  占比={pct:5.1f}%{marker}")

    print(f"\n  依路由分組：")
    for route in sorted(df["route_used"].astype(str).unique()):
        sub = df[df["route_used"] == route]
        print(f"    route:{route:<10} 樣本={len(sub):3d}  end_to_end mean={sub['end_to_end_ms'].mean():8.1f}ms  p95={sub['end_to_end_ms'].quantile(0.95):8.1f}ms")


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    if df.empty:
        print("結果檔案為空。")
        return

    pc_df = df[df["tts_ms"] < 1].copy()
    pi_df = df[df["tts_ms"] >= 1].copy()

    print(f"資料讀取完成：總計 {len(df)} 筆（PC: {len(pc_df)} 筆，Pi: {len(pi_df)} 筆）")

    all_rows = []

    if not pc_df.empty:
        print_summary("PC 結果（不含 TTS）", pc_df, include_tts=False)
        all_rows.extend(summarize("pc", pc_df, include_tts=False))

    if not pi_df.empty:
        print_summary("Pi 結果（含 TTS）", pi_df, include_tts=True)
        all_rows.extend(summarize("pi", pi_df, include_tts=True))

    summary_df = pd.DataFrame(all_rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n彙總寫入：{args.output}")


if __name__ == "__main__":
    main()
