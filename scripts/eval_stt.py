#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
from jiwer import cer as jiwer_cer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate faster-whisper STT models and write per-run results to CSV."
    )
    parser.add_argument(
        "--cases",
        default="data/eval/test_cases.csv",
        help="Path to test cases CSV.",
    )
    parser.add_argument(
        "--audio-dir",
        default="data/recordings",
        help="Directory containing WAV files.",
    )
    parser.add_argument(
        "--output",
        default="data/eval/results.csv",
        help="Path to output results CSV.",
    )
    parser.add_argument(
        "--models",
        default="tiny,base,small",
        help="Comma separated faster-whisper model sizes.",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Runs per case per model.")
    parser.add_argument("--device", default="cpu", help="Inference device.")
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="Compute type for faster-whisper.",
    )
    parser.add_argument("--threads", type=int, default=4, help="CPU threads.")
    parser.add_argument("--beam-size", type=int, default=1, help="Beam size.")
    parser.add_argument("--best-of", type=int, default=1, help="Best-of value.")
    parser.add_argument(
        "--language",
        default="auto",
        help="Language code. Use auto for automatic language detection.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of test cases to run (0 means all).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        default=True,
        help="Append new results to output file (default: true).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output file instead of appending.",
    )
    return parser.parse_args()


def get_audio_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            return 0.0
        return frames / float(frame_rate)


def normalize_sentence_for_match(text: str) -> str:
    simplified = "".join(ch.lower() for ch in str(text).strip() if ch.isalnum())
    return simplified


def get_first_existing_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def load_cases(cases_path: Path, limit: int) -> pd.DataFrame:
    if not cases_path.exists():
        raise FileNotFoundError(f"Cases file not found: {cases_path}")

    df = pd.read_csv(cases_path)
    if "test_id" not in df.columns:
        raise ValueError("Cases CSV must include a 'test_id' column.")

    ground_truth_col = get_first_existing_column(
        df,
        ["ground_truth_text", "ground_truth", "reference_text", "text", "transcript"],
    )
    if ground_truth_col is None:
        raise ValueError(
            "Cases CSV must include one of: ground_truth_text, ground_truth, reference_text, text, transcript"
        )

    if "audio_file" not in df.columns:
        df["audio_file"] = df["test_id"].astype(str) + ".wav"

    if "noise_level" not in df.columns:
        df["noise_level"] = "unknown"

    df = df.copy()
    df["ground_truth_text"] = df[ground_truth_col].astype(str)

    if limit > 0:
        df = df.head(limit)

    return df


def transcribe_once(
    model,
    audio_path: Path,
    language: str,
    beam_size: int,
    best_of: int,
) -> Dict[str, str]:
    normalized_language = None if language.strip().lower() in {"", "auto", "none"} else language
    started = time.perf_counter()
    segments, _info = model.transcribe(
        str(audio_path),
        beam_size=beam_size,
        best_of=best_of,
        language=normalized_language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=True,
        word_timestamps=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    predicted = " ".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip()).strip()
    return {"predicted_text": predicted, "inference_ms": elapsed_ms}


def ensure_output_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "timestamp",
                "run_id",
                "test_id",
                "model_size",
                "audio_file",
                "audio_duration_s",
                "noise_level",
                "ground_truth_text",
                "predicted_text",
                "sentence_correct",
                "cer",
                "inference_ms",
                "rtf",
                "startup_state",
                "repeat_index",
                "device",
                "compute_type",
                "beam_size",
                "best_of",
                "language",
            ]
        )


def append_rows(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writerows(rows)


def main() -> None:
    args = parse_args()

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError(
            "faster-whisper is not available. Install dependencies first."
        ) from exc

    cases_path = Path(args.cases)
    audio_dir = Path(args.audio_dir)
    output_path = Path(args.output)

    if not audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

    cases_df = load_cases(cases_path, args.limit)
    model_list = [item.strip() for item in args.models.split(",") if item.strip()]
    if not model_list:
        raise ValueError("At least one model must be provided in --models")

    if args.overwrite and output_path.exists():
        output_path.unlink()
    ensure_output_header(output_path)

    total_rows: List[Dict[str, object]] = []

    for model_size in model_list:
        print(f"\n[model] loading: {model_size}")
        model = WhisperModel(
            model_size,
            device=args.device,
            compute_type=args.compute_type,
            cpu_threads=args.threads,
            num_workers=1,
        )

        is_first_run_for_model = True

        for _, row in cases_df.iterrows():
            test_id = str(row["test_id"])
            ground_truth = str(row["ground_truth_text"])
            noise_level = str(row["noise_level"])
            audio_file = str(row["audio_file"])
            audio_path = audio_dir / audio_file

            if not audio_path.exists():
                print(f"[skip] missing audio file for {test_id}: {audio_path}")
                continue

            audio_duration_s = get_audio_duration_seconds(audio_path)
            if audio_duration_s <= 0:
                print(f"[skip] invalid duration for {test_id}: {audio_path}")
                continue

            for repeat_index in range(1, args.repeat + 1):
                startup_state = "Cold" if is_first_run_for_model else "Warm"
                run = transcribe_once(
                    model=model,
                    audio_path=audio_path,
                    language=args.language,
                    beam_size=args.beam_size,
                    best_of=args.best_of,
                )
                is_first_run_for_model = False

                predicted_text = run["predicted_text"]
                inference_ms = float(run["inference_ms"])
                rtf = inference_ms / (audio_duration_s * 1000.0)

                sentence_correct = int(
                    normalize_sentence_for_match(ground_truth)
                    == normalize_sentence_for_match(predicted_text)
                )
                cer_value = float(jiwer_cer(ground_truth, predicted_text))

                total_rows.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                        "run_id": f"R_{uuid.uuid4().hex[:10]}",
                        "test_id": test_id,
                        "model_size": model_size,
                        "audio_file": audio_file,
                        "audio_duration_s": round(audio_duration_s, 4),
                        "noise_level": noise_level,
                        "ground_truth_text": ground_truth,
                        "predicted_text": predicted_text,
                        "sentence_correct": sentence_correct,
                        "cer": round(cer_value, 6),
                        "inference_ms": round(inference_ms, 3),
                        "rtf": round(rtf, 6),
                        "startup_state": startup_state,
                        "repeat_index": repeat_index,
                        "device": args.device,
                        "compute_type": args.compute_type,
                        "beam_size": args.beam_size,
                        "best_of": args.best_of,
                        "language": args.language,
                    }
                )

                print(
                    f"[run] model={model_size} test_id={test_id} repeat={repeat_index} "
                    f"cer={cer_value:.4f} ms={inference_ms:.1f} startup={startup_state}"
                )

    append_rows(output_path, total_rows)

    if not total_rows:
        print("\nNo rows were written. Check test cases and audio files.")
        return

    result_df = pd.DataFrame(total_rows)
    summary = (
        result_df.groupby("model_size", as_index=False)
        .agg(
            samples=("run_id", "count"),
            mean_cer=("cer", "mean"),
            sentence_accuracy=("sentence_correct", "mean"),
            mean_inference_ms=("inference_ms", "mean"),
            p95_inference_ms=("inference_ms", lambda s: float(s.quantile(0.95))),
            mean_rtf=("rtf", "mean"),
        )
        .sort_values("model_size")
    )

    print("\n=== Summary by model ===")
    print(summary.to_string(index=False))
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
