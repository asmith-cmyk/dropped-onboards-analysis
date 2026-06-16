from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

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

    if dropped_raw.exists():
        dropped = canonicalize_dataframe(read_csv(dropped_raw), source="dropped")
    else:
        dropped = canonicalize_dataframe(pd.DataFrame(), source="dropped")
        print("Salesforce dropped raw CSV missing; continuing with empty Salesforce dropped source.")

    if returning_raw.exists():
        returning = canonicalize_dataframe(read_csv(returning_raw), source="returning")
    else:
        returning = canonicalize_dataframe(pd.DataFrame(), source="returning")
        print("Salesforce returning raw CSV missing; continuing with empty Salesforce returning source.")

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
