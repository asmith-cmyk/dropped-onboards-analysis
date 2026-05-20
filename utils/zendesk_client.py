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


def infer_creator_from_subject(value: Any) -> str:
    subject = clean_blank(value)
    if not subject:
        return ""
    generic_subjects = {
        "your raptive application has been accepted",
        "eligibility for raptive rise",
        "amy test",
        "sum",
    }
    if normalize_text(subject) in generic_subjects:
        return ""
    text = re.sub(r"\.{3}$", "", subject).strip()
    text = re.sub(r"^(?:re|fw|fwd):\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.split(r"\s*--\s*", text, maxsplit=1)[0].strip()
    replacements = [
        r"\s+Raptive\s+Application\b.*$",
        r"\s+Raptive\s+Site\s+Analysis\b.*$",
        r"\s+Analysis\s+Follow[-\s]?up\b.*$",
        r"\s+Checking\s+In\s+On\s+Your\s+Raptive\b.*$",
        r"\s+Eligibility\s+For\s+Raptive\s+Rise\b.*$",
    ]
    for pattern in replacements:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    if normalize_text(text) in generic_subjects | {"checking in on your", "your"}:
        return ""
    return text


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
    days = []
    for day, column in (("3", "macro_day_3"), ("5", "macro_day_5"), ("7", "macro_day_7"), ("10", "macro_day_10")):
        if bool(row.get(column)):
            days.append(day)
    return "/".join(days) if days else "None"


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
        "Ticket subject": "subject",
        "Created": "created_at",
        "Created at": "created_at",
        "Ticket created - Date": "created_at",
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

    total_rows = (
        out["ticket_id"].map(normalize_text).eq("sum")
        | out["tags"].map(normalize_text).eq("sum")
        | out["subject"].map(normalize_text).eq("sum")
    )
    out = out.loc[~total_rows].copy()
    out["creator"] = out["creator"].where(out["creator"].map(clean_blank).astype(bool), out["subject"].map(infer_creator_from_subject))
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
    out = aggregate_zendesk_tickets(out)
    out["creator_key"] = out["creator"].map(normalize_creator_name)
    out["lead_key"] = out["lead_contact"].map(normalize_creator_name)
    return out


def aggregate_zendesk_tickets(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "ticket_id" not in df.columns:
        return df

    out = df.copy()
    out["_group_key"] = out["ticket_id"].map(clean_blank)
    out.loc[out["_group_key"].eq(""), "_group_key"] = out.index.astype(str)
    rows: list[dict[str, Any]] = []
    first_columns = [
        "ticket_id",
        "creator",
        "lead_contact",
        "subject",
        "created_at",
        "updated_at",
        "solved_at",
    ]
    bool_columns = [
        "macro_day_3",
        "macro_day_5",
        "macro_day_7",
        "macro_day_10",
        "cg_escalated",
        "meeting_offered",
        "ticket_reopened",
    ]
    for _, group in out.groupby("_group_key", sort=False):
        row: dict[str, Any] = {}
        for column in first_columns:
            row[column] = next((clean_blank(value) for value in group[column] if clean_blank(value)), "")
        tag_values = []
        for tags in group["tags"]:
            for tag in re.split(r"[,;\s]+", clean_blank(tags)):
                if tag and tag not in tag_values:
                    tag_values.append(tag)
        row["tags"] = " ".join(tag_values)
        for column in bool_columns:
            row[column] = bool(group[column].fillna(False).astype(bool).any())
        row["macro_cadence"] = infer_macro_cadence(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows)


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
