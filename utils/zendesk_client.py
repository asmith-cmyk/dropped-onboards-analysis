from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

try:
    import requests
except ImportError:
    requests = None

from utils.io import clean_blank
from utils.text import normalize_creator_name, normalize_text


DAY_PATTERNS = {
    "macro_day_3": re.compile(r"(?:^|[_\-\s])(?:day[_\-\s]?3|3[_\-\s]?day|3d)(?:$|[_\-\s])"),
    "macro_day_5": re.compile(r"(?:^|[_\-\s])(?:day[_\-\s]?5|5[_\-\s]?day|5d)(?:$|[_\-\s])"),
    "macro_day_7": re.compile(r"(?:^|[_\-\s])(?:day[_\-\s]?7|7[_\-\s]?day|7d)(?:$|[_\-\s])"),
    "macro_day_10": re.compile(r"(?:^|[_\-\s])(?:day[_\-\s]?10|10[_\-\s]?day|10d)(?:$|[_\-\s])"),
}


def tags_to_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return clean_blank(value)


def infer_macro_flags(tags: str) -> dict[str, bool]:
    normalized = normalize_text(tags).replace(" ", "_")
    return {
        field: bool(pattern.search(f"_{normalized}_"))
        for field, pattern in DAY_PATTERNS.items()
    }


def infer_macro_cadence(row: pd.Series) -> str:
    day3 = bool(row.get("macro_day_3"))
    day5 = bool(row.get("macro_day_5"))
    day7 = bool(row.get("macro_day_7"))
    day10 = bool(row.get("macro_day_10"))
    if day3 and day5 and day7:
        return "3/5/7"
    if day3 and day7 and day10:
        return "3/7/10"
    if day3 or day5 or day7 or day10:
        return "Partial"
    return "None"


def normalize_zendesk_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "ticket_id",
                "creator",
                "lead_contact",
                "subject",
                "created_at",
                "updated_at",
                "solved_at",
                "tags",
                "macro_day_3",
                "macro_day_5",
                "macro_day_7",
                "macro_day_10",
                "macro_cadence",
                "cg_escalated",
                "meeting_offered",
                "ticket_reopened",
                "creator_key",
                "lead_key",
            ]
        )

    rename = {
        "id": "ticket_id",
        "Ticket ID": "ticket_id",
        "Requester": "lead_contact",
        "Requester name": "lead_contact",
        "Subject": "subject",
        "Created": "created_at",
        "Created at": "created_at",
        "Updated": "updated_at",
        "Updated at": "updated_at",
        "Solved": "solved_at",
        "Solved at": "solved_at",
        "Tags": "tags",
        "Ticket tags": "tags",
        "Project Name": "creator",
        "Creator": "creator",
    }
    out = df.rename(columns={column: rename.get(column, column) for column in df.columns}).copy()
    for column in ("ticket_id", "creator", "lead_contact", "subject", "created_at", "updated_at", "solved_at", "tags"):
        if column not in out.columns:
            out[column] = ""

    out["tags"] = out["tags"].map(tags_to_text)
    flags = out["tags"].map(infer_macro_flags).apply(pd.Series)
    for column in DAY_PATTERNS:
        if column in out.columns:
            out[column] = out[column].astype(str).str.lower().isin({"true", "1", "yes"}) | flags[column]
        else:
            out[column] = flags[column]

    text_blob = (out["tags"] + " " + out["subject"]).map(normalize_text)
    out["cg_escalated"] = text_blob.str.contains("creator growth|creator_growth|cg handoff|cg escalation|passed to cg", regex=True)
    out["meeting_offered"] = text_blob.str.contains("call link|meeting link|salesloft|book a call|schedule a call", regex=True)
    out["ticket_reopened"] = text_blob.str.contains("reopen|reopened", regex=True)
    out["macro_cadence"] = out.apply(infer_macro_cadence, axis=1)
    out["creator_key"] = out["creator"].map(normalize_creator_name)
    out["lead_key"] = out["lead_contact"].map(normalize_creator_name)
    return out


class ZendeskClient:
    def __init__(self, subdomain: str):
        if requests is None:
            raise RuntimeError("requests is not installed. Run `pip install -r requirements.txt`.")
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{os.environ['ZENDESK_EMAIL']}/token", os.environ["ZENDESK_API_TOKEN"])

    def search_tickets(self, query: str) -> pd.DataFrame:
        url = f"{self.base_url}/search.json"
        params = {"query": query, "sort_by": "created_at", "sort_order": "asc"}
        rows: list[dict[str, Any]] = []
        while url:
            response = requests.get(url, auth=self.auth, params=params, timeout=45)
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("results", []))
            url = payload.get("next_page")
            params = None
        return pd.DataFrame(rows)
