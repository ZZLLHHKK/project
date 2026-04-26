#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audio.speech_processor import SpeechProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record evaluation audio from test_cases.csv with automatic filenames."
    )
    parser.add_argument(
        "--cases",
        default="data/eval/test_cases.csv",
        help="Path to test cases CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/recordings/eval",
        help="Directory to store recorded wav files.",
    )
    parser.add_argument(
        "--start-id",
        default="",
        help="Start recording from this test_id (inclusive).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=6,
        help="Max recording seconds for VAD recorder.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing wav files.",
    )
    return parser.parse_args()


def load_cases(cases_path: Path) -> list[dict[str, str]]:
    if not cases_path.exists():
        raise FileNotFoundError(f"Cases file not found: {cases_path}")

    with cases_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"test_id", "ground_truth_text", "audio_file"}
        missing = required.difference(set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Missing required columns in cases CSV: {sorted(missing)}")

        rows = []
        for row in reader:
            rows.append(
                {
                    "test_id": str(row.get("test_id", "")).strip(),
                    "ground_truth_text": str(row.get("ground_truth_text", "")).strip(),
                    "audio_file": str(row.get("audio_file", "")).strip(),
                    "noise_level": str(row.get("noise_level", "")).strip(),
                }
            )
        return rows


def should_start(case_id: str, start_id: str, started: bool) -> bool:
    if started:
        return True
    if not start_id:
        return True
    return case_id == start_id


def main() -> None:
    args = parse_args()

    cases_path = Path(args.cases)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = load_cases(cases_path)
    if not cases:
        print("No cases found in CSV.")
        return

    speech = SpeechProcessor(default_duration=args.duration)
    print(f"Output folder: {output_dir}")
    print("Controls: [Enter]=record, s=skip, q=quit, r=record again")
    print("During recording: press Enter to stop early (desktop/ffmpeg mode).")

    started = False
    recorded = 0
    skipped = 0

    for idx, case in enumerate(cases, start=1):
        test_id = case["test_id"]
        if not test_id:
            continue

        if not should_start(test_id, args.start_id, started):
            continue
        started = True

        audio_file = case["audio_file"] or f"{test_id}.wav"
        target_path = output_dir / audio_file

        if target_path.exists() and not args.overwrite:
            print(f"[{idx}/{len(cases)}] {test_id} exists -> skip ({target_path.name})")
            skipped += 1
            continue

        prompt = case["ground_truth_text"]
        noise = case["noise_level"] or "unknown"

        while True:
            print("\n" + "-" * 60)
            print(f"[{idx}/{len(cases)}] {test_id}  noise={noise}")
            print(f"Please read: {prompt}")
            print(f"Target file: {target_path}")
            cmd = input("Action [Enter/s/q]: ").strip().lower()

            if cmd == "q":
                print("Stop recording session.")
                print(f"Recorded: {recorded}, Skipped: {skipped}")
                return
            if cmd == "s":
                skipped += 1
                break

            saved = speech.record_wav_file(
                target_path,
                duration=args.duration,
                allow_manual_stop=True,
            )
            if not saved:
                retry = input("No speech detected. retry? [Enter=yes / s=skip / q=quit]: ").strip().lower()
                if retry == "q":
                    print("Stop recording session.")
                    print(f"Recorded: {recorded}, Skipped: {skipped}")
                    return
                if retry == "s":
                    skipped += 1
                    break
                continue

            print(f"Saved: {saved}")
            recorded += 1
            again = input("Record again for this item? [r=again / Enter=next]: ").strip().lower()
            if again == "r":
                continue
            break

    print("\nRecording session completed.")
    print(f"Recorded: {recorded}, Skipped: {skipped}")
    print(f"Audio folder: {output_dir}")


if __name__ == "__main__":
    main()
