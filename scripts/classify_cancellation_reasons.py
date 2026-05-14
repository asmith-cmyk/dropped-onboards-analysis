from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai import classify_cancellation_reason
from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv
from utils.text import normalize_creator_name


def run(limit: int | None = None) -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    dropped = read_csv(settings.processed_data_dir / "dropped_normalized.csv")
    if limit:
        dropped = dropped.head(limit)

    rows = []
    for _, row in dropped.iterrows():
        result = classify_cancellation_reason(
            row.get("description", ""),
            row.get("cancelled_reason", ""),
            model=settings.openai_model,
            use_openai=settings.use_openai_classification,
        )
        rows.append(
            {
                "creator": row.get("creator", ""),
                "creator_key": normalize_creator_name(row.get("creator", "")),
                "raw_description": row.get("description", ""),
                "raw_cancelled_reason": row.get("cancelled_reason", ""),
                **result,
            }
        )

    classifications = pd.DataFrame(rows)
    output_path = settings.processed_data_dir / "cancellation_reasons.csv"
    write_csv(classifications, output_path)
    print(f"Wrote {output_path} ({len(classifications)} rows)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify cancellation reasons.")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    run(args.limit)


if __name__ == "__main__":
    main()

