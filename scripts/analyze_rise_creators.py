from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analysis import build_rise_creator_analysis
from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    master = read_csv(settings.output_dir / "master_creator_lifecycle.csv")
    analysis = build_rise_creator_analysis(master)
    output_path = settings.output_dir / "rise_creator_analysis.csv"
    write_csv(analysis, output_path)
    print(f"Wrote {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Rise creator outcomes.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
