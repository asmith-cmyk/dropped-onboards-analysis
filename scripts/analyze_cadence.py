from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analysis import cohort_summary
from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    master = read_csv(settings.output_dir / "master_creator_lifecycle.csv")
    analysis = cohort_summary(master, "Macro Cadence", "macro_cadence")
    output_path = settings.output_dir / "cadence_analysis.csv"
    write_csv(analysis, output_path)
    print(f"Wrote {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze follow-up macro cadence.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
