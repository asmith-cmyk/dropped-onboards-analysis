from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

from utils.io import clean_blank


@dataclass
class MatchResult:
    returning_index: int | None
    match_method: str
    match_score: float


def populated(value: object) -> bool:
    return bool(clean_blank(value))


def date_eligible(dropped_date, returned_date) -> bool:
    if pd.isna(dropped_date) or pd.isna(returned_date):
        return True
    return returned_date >= dropped_date - pd.Timedelta(days=30)


def choose_best(
    candidates: list[tuple[int, str, float]],
    dropped_row: pd.Series,
    returning: pd.DataFrame,
) -> MatchResult:
    eligible: list[tuple[int, str, float]] = []
    for index, method, score in candidates:
        returned_date = returning.loc[index, "returned_date"] if "returned_date" in returning.columns else pd.NaT
        if date_eligible(dropped_row.get("dropped_date"), returned_date):
            eligible.append((index, method, score))
    if not eligible:
        return MatchResult(None, "", 0.0)

    def sort_key(item: tuple[int, str, float]):
        idx, _method, score = item
        returned = returning.loc[idx, "returned_date"] if "returned_date" in returning.columns else pd.NaT
        returned_sort = returned if pd.notna(returned) else pd.Timestamp.max
        return (-score, returned_sort)

    idx, method, score = sorted(eligible, key=sort_key)[0]
    return MatchResult(idx, method, score)


def match_one(dropped_row: pd.Series, returning: pd.DataFrame, fuzzy_threshold: int = 88) -> MatchResult:
    candidates: list[tuple[int, str, float]] = []
    exact_fields = [
        ("salesforce_project_id", "salesforce_project_id", "salesforce_project_id", 100.0),
        ("salesforce_account_id", "salesforce_account_id", "salesforce_account_id", 99.0),
        ("creator_key", "creator_key", "project_name", 98.0),
        ("domain_key", "domain_key", "domain", 96.0),
        ("lead_key", "lead_key", "lead_contact", 92.0),
    ]
    for dropped_field, returning_field, method, score in exact_fields:
        value = dropped_row.get(dropped_field)
        if not populated(value) or returning_field not in returning.columns:
            continue
        matches = returning.index[returning[returning_field] == value].tolist()
        candidates.extend((idx, method, score) for idx in matches)

    if "creator_key" in returning.columns and populated(dropped_row.get("creator_key")):
        choices = returning["creator_key"].fillna("").tolist()
        if process is not None and fuzz is not None:
            fuzzy_matches = process.extract(
                dropped_row["creator_key"],
                choices,
                scorer=fuzz.token_sort_ratio,
                limit=5,
            )
            for _choice, score, pos in fuzzy_matches:
                if score >= fuzzy_threshold:
                    candidates.append((returning.index[pos], "fuzzy_project_name", float(score)))
        else:
            target_tokens = sorted(str(dropped_row["creator_key"]).split())
            target = " ".join(target_tokens)
            scored = []
            for pos, choice in enumerate(choices):
                candidate = " ".join(sorted(str(choice).split()))
                score = SequenceMatcher(None, target, candidate).ratio() * 100
                scored.append((score, pos))
            for score, pos in sorted(scored, reverse=True)[:5]:
                if score >= fuzzy_threshold:
                    candidates.append((returning.index[pos], "fuzzy_project_name", float(score)))

    return choose_best(candidates, dropped_row, returning)


def match_dropped_to_returning(
    dropped: pd.DataFrame, returning: pd.DataFrame, fuzzy_threshold: int = 88
) -> pd.DataFrame:
    if dropped.empty:
        return dropped.copy()

    out = dropped.copy().reset_index(drop=True)
    returning = returning.copy().reset_index(drop=True)
    out["returning_row_index"] = ""
    out["match_method"] = ""
    out["match_score"] = 0.0

    returning_prefix = {
        column: f"returning_{column}"
        for column in returning.columns
        if not column.startswith("returning_")
    }
    for prefixed in returning_prefix.values():
        out[prefixed] = ""

    for idx, row in out.iterrows():
        result = match_one(row, returning, fuzzy_threshold=fuzzy_threshold)
        if result.returning_index is None:
            continue
        out.at[idx, "returning_row_index"] = result.returning_index
        out.at[idx, "match_method"] = result.match_method
        out.at[idx, "match_score"] = round(result.match_score, 2)
        for column, prefixed in returning_prefix.items():
            out.at[idx, prefixed] = returning.at[result.returning_index, column]

    out["reengaged"] = out["match_method"].astype(str).str.len() > 0
    return out
