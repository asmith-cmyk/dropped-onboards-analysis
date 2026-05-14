from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.salesforce_client import fetch_report_dataframe


def run(
    input_dropped_csv: Path | None = None,
    input_returning_csv: Path | None = None,
    force_api: bool = False,
) -> tuple[Path, Path]:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)

    dropped_path = settings.raw_data_dir / "salesforce_dropped_onboards.csv"
    returning_path = settings.raw_data_dir / "salesforce_returning_yoyo.csv"

    if input_dropped_csv:
        write_csv(read_csv(input_dropped_csv), dropped_path)
    if input_returning_csv:
        write_csv(read_csv(input_returning_csv), returning_path)

    should_fetch = force_api or not (dropped_path.exists() and returning_path.exists())
    if should_fetch:
        if not settings.has_salesforce_credentials:
            raise RuntimeError(
                "Salesforce credentials are missing and no local raw Salesforce CSVs exist. "
                "Provide SALESFORCE_* env vars or pass --input-dropped-csv and --input-returning-csv."
            )
        dropped = fetch_report_dataframe(
            settings,
            settings.salesforce_dropped_report_id,
            settings.raw_data_dir / "salesforce_dropped_report.json",
        )
        returning = fetch_report_dataframe(
            settings,
            settings.salesforce_returning_report_id,
            settings.raw_data_dir / "salesforce_returning_report.json",
        )
        write_csv(dropped, dropped_path)
        write_csv(returning, returning_path)

    print(f"Wrote {dropped_path}")
    print(f"Wrote {returning_path}")
    print(f"Dropped columns: {list(read_csv(dropped_path).columns)}")
    print(f"Returning columns: {list(read_csv(returning_path).columns)}")
    return dropped_path, returning_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Salesforce dropped and returning reports.")
    parser.add_argument("--input-dropped-csv", type=Path)
    parser.add_argument("--input-returning-csv", type=Path)
    parser.add_argument("--force-api", action="store_true")
    args = parser.parse_args()
    run(args.input_dropped_csv, args.input_returning_csv, args.force_api)


if __name__ == "__main__":
    main()

