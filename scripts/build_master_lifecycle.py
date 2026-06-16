from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, read_csv_if_exists, write_csv
from utils.lifecycle import apply_manual_overrides
from utils.site_history_lifecycle import build_master_from_site_history


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    site_history_path = settings.raw_data_dir / "snowflake_site_history.csv"
    if not site_history_path.exists():
        raise RuntimeError(
            "Full site-history source is missing. Import or pull data/raw/snowflake_site_history.csv first."
        )

    master = build_master_from_site_history(read_csv(site_history_path))
    manual_overrides = read_csv_if_exists(settings.data_dir / "manual_lifecycle_overrides.csv")
    if not manual_overrides.empty:
        master = apply_manual_overrides(master, manual_overrides)
    processed_path = settings.processed_data_dir / "master_creator_lifecycle.csv"
    output_path = settings.output_dir / "master_creator_lifecycle.csv"
    write_csv(master, processed_path)
    write_csv(master, output_path)
    print(f"Wrote {processed_path} and {output_path} ({len(master)} rows)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the master onboarding lifecycle dataset.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
