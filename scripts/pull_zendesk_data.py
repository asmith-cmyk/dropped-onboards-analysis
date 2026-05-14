from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.zendesk_client import ZendeskClient, normalize_zendesk_dataframe


def run(input_csv: Path | None = None) -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    output_path = settings.raw_data_dir / "zendesk_onboarding_followups.csv"

    source_csv = input_csv or (Path(os.environ["ZENDESK_EXPORT_CSV"]) if os.getenv("ZENDESK_EXPORT_CSV") else None)
    if source_csv:
        raw = read_csv(source_csv)
    elif settings.has_zendesk_credentials:
        raw = ZendeskClient(settings.zendesk_subdomain).search_tickets(settings.zendesk_search_query)
    else:
        raw = pd.DataFrame()

    normalized = normalize_zendesk_dataframe(raw)
    write_csv(normalized, output_path)
    print(f"Wrote {output_path} ({len(normalized)} rows)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Zendesk onboarding follow-up data.")
    parser.add_argument("--input-csv", type=Path)
    args = parser.parse_args()
    run(args.input_csv)


if __name__ == "__main__":
    main()

