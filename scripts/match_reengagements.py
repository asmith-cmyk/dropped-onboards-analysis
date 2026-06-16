from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv_if_exists, write_csv
from utils.matching import match_dropped_to_returning
import pandas as pd


def run(fuzzy_threshold: int = 88) -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    dropped = read_csv_if_exists(settings.processed_data_dir / "dropped_normalized.csv")
    returning = read_csv_if_exists(settings.processed_data_dir / "returning_normalized.csv")

    for frame in (dropped, returning):
        for date_column in ("dropped_date", "scheduled_install_date", "install_date", "returned_date"):
            if date_column in frame.columns:
                frame[date_column] = pd.to_datetime(frame[date_column].replace("", None), errors="coerce")

    matches = match_dropped_to_returning(dropped, returning, fuzzy_threshold=fuzzy_threshold)
    output_path = settings.processed_data_dir / "reengagement_matches.csv"
    write_csv(matches, output_path)
    reengaged_count = matches["reengaged"].astype(bool).sum() if "reengaged" in matches.columns else 0
    print(f"Wrote {output_path} ({reengaged_count} matches / {len(matches)} dropped)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Match dropped creators to returning creators.")
    parser.add_argument("--fuzzy-threshold", type=int, default=88)
    args = parser.parse_args()
    run(args.fuzzy_threshold)


if __name__ == "__main__":
    main()
