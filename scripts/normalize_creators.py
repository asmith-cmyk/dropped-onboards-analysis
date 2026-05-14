from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.columns import canonicalize_dataframe
from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv


def run() -> tuple[Path, Path]:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    dropped_raw = settings.raw_data_dir / "salesforce_dropped_onboards.csv"
    returning_raw = settings.raw_data_dir / "salesforce_returning_yoyo.csv"
    if not dropped_raw.exists() or not returning_raw.exists():
        raise RuntimeError("Salesforce raw CSVs are missing. Run pull_salesforce_reports.py first.")

    dropped = canonicalize_dataframe(read_csv(dropped_raw), source="dropped")
    returning = canonicalize_dataframe(read_csv(returning_raw), source="returning")

    dropped_path = settings.processed_data_dir / "dropped_normalized.csv"
    returning_path = settings.processed_data_dir / "returning_normalized.csv"
    write_csv(dropped, dropped_path)
    write_csv(returning, returning_path)
    print(f"Wrote {dropped_path} ({len(dropped)} rows)")
    print(f"Wrote {returning_path} ({len(returning)} rows)")
    return dropped_path, returning_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize creator identity fields.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()

