from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_csv(path)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def clean_blank(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return text


def coalesce(*values: Any) -> str:
    for value in values:
        cleaned = clean_blank(value)
        if cleaned:
            return cleaned
    return ""


def parse_boolish(value: Any) -> bool:
    text = clean_blank(value).lower()
    return text in {"1", "true", "yes", "y", "installed", "converted", "booked"}

