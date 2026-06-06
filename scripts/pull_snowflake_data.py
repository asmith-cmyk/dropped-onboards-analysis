from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.snowflake_client import (
    fetch_query_dataframe,
    load_full_site_history_query,
)


def run(
    input_dropped_csv: Path | None = None,
    input_returned_csv: Path | None = None,
    input_starts_csv: Path | None = None,
    input_site_history_csv: Path | None = None,
    force_api: bool = False,
) -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)

    site_history_path = settings.raw_data_dir / "snowflake_site_history.csv"

    legacy_inputs = [input_dropped_csv, input_returned_csv, input_starts_csv]
    if any(legacy_inputs) and not input_site_history_csv:
        raise RuntimeError(
            "The rebuilt dashboard uses one full site-history dataset. "
            "Pass --input-site-history-csv instead of dropped/returned/start CSVs."
        )

    if input_site_history_csv:
        write_csv(read_csv(input_site_history_csv), site_history_path)

    should_fetch = force_api or not site_history_path.exists()
    if should_fetch:
        site_history = fetch_query_dataframe(settings, load_full_site_history_query())
        write_csv(site_history, site_history_path)

    print(f"Wrote {site_history_path}")
    print(f"Full site-history rows: {len(read_csv(site_history_path))}")
    return site_history_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Snowflake full site-history lifecycle data.")
    parser.add_argument("--input-site-history-csv", type=Path)
    parser.add_argument("--input-dropped-csv", type=Path, help="Deprecated; use --input-site-history-csv.")
    parser.add_argument("--input-returned-csv", type=Path, help="Deprecated; use --input-site-history-csv.")
    parser.add_argument("--input-starts-csv", type=Path, help="Deprecated; use --input-site-history-csv.")
    parser.add_argument("--force-api", action="store_true")
    args = parser.parse_args()
    run(
        args.input_dropped_csv,
        args.input_returned_csv,
        input_starts_csv=args.input_starts_csv,
        input_site_history_csv=args.input_site_history_csv,
        force_api=args.force_api,
    )


if __name__ == "__main__":
    main()
