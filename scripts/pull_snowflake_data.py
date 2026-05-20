from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.snowflake_client import DROPPED_2025_QUERY, RETURNED_2026_QUERY, fetch_query_dataframe


def run(
    input_dropped_csv: Path | None = None,
    input_returned_csv: Path | None = None,
    force_api: bool = False,
) -> tuple[Path, Path]:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)

    dropped_path = settings.raw_data_dir / "snowflake_dropped_2025.csv"
    returned_path = settings.raw_data_dir / "snowflake_returned_2026.csv"

    if input_dropped_csv:
        write_csv(read_csv(input_dropped_csv), dropped_path)
    if input_returned_csv:
        write_csv(read_csv(input_returned_csv), returned_path)

    should_fetch = force_api or not (dropped_path.exists() and returned_path.exists())
    if should_fetch:
        dropped = fetch_query_dataframe(settings, DROPPED_2025_QUERY)
        returned = fetch_query_dataframe(settings, RETURNED_2026_QUERY)
        write_csv(dropped, dropped_path)
        write_csv(returned, returned_path)

    print(f"Wrote {dropped_path}")
    print(f"Wrote {returned_path}")
    print(f"Dropped 2025 rows: {len(read_csv(dropped_path))}")
    print(f"Returned 2026 rows: {len(read_csv(returned_path))}")
    return dropped_path, returned_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Snowflake dropped and returned site cohorts.")
    parser.add_argument("--input-dropped-csv", type=Path)
    parser.add_argument("--input-returned-csv", type=Path)
    parser.add_argument("--force-api", action="store_true")
    args = parser.parse_args()
    run(args.input_dropped_csv, args.input_returned_csv, args.force_api)


if __name__ == "__main__":
    main()
