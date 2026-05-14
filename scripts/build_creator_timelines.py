from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_master_lifecycle import run as build_master_lifecycle


def run() -> Path:
    print("build_creator_timelines.py is now a compatibility alias for build_master_lifecycle.py.")
    return build_master_lifecycle()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build creator timelines from all sources.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
