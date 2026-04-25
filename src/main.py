import os
import sys
import argparse
from pathlib import Path

from src.launch import run_desktop_console, run_gui_app


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter desktop GUI")
    args = parser.parse_args()

    if args.gui:
        run_gui_app()
        return

    run_desktop_console()

if __name__ == "__main__":
    main()
