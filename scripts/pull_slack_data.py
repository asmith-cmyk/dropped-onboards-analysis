from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.slack_client import SlackPuller


def run(input_csv: Path | None = None) -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    output_path = settings.raw_data_dir / "slack_interventions.csv"

    if input_csv:
        raw = read_csv(input_csv)
    elif settings.has_slack_credentials:
        raw = SlackPuller().fetch_channels(settings.slack_channel_names, settings.slack_start_date)
    else:
        raw = pd.DataFrame(
            columns=[
                "channel_name",
                "channel_id",
                "message_ts",
                "event_at",
                "user",
                "text",
                "event_type",
                "thread_ts",
                "permalink",
            ]
        )

    write_csv(raw, output_path)
    print(f"Wrote {output_path} ({len(raw)} rows)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Slack intervention signals.")
    parser.add_argument("--input-csv", type=Path)
    args = parser.parse_args()
    run(args.input_csv)


if __name__ == "__main__":
    main()

