from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, read_csv_if_exists, write_csv
from utils.lifecycle import build_master_creator_lifecycle


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    matches = read_csv(settings.processed_data_dir / "reengagement_matches.csv")
    classifications = read_csv_if_exists(settings.processed_data_dir / "cancellation_reasons.csv")
    zendesk = read_csv_if_exists(settings.raw_data_dir / "zendesk_onboarding_followups.csv")
    slack = read_csv_if_exists(settings.raw_data_dir / "slack_interventions.csv")
    manual_overrides = read_csv_if_exists(settings.data_dir / "manual_lifecycle_overrides.csv")
    snowflake_dropped = read_csv_if_exists(settings.raw_data_dir / "snowflake_dropped_2025.csv")
    snowflake_returned = read_csv_if_exists(settings.raw_data_dir / "snowflake_returned_2026.csv")

    master = build_master_creator_lifecycle(
        matches,
        classifications,
        zendesk,
        slack,
        manual_overrides,
        snowflake_dropped,
        snowflake_returned,
    )
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
