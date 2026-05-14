from __future__ import annotations

import os
from typing import Any

import pandas as pd

try:
    from simple_salesforce import Salesforce
except ImportError:
    Salesforce = None

from utils.config import Settings
from utils.io import write_json


def create_salesforce_client(settings: Settings) -> Salesforce:
    if Salesforce is None:
        raise RuntimeError("simple-salesforce is not installed. Run `pip install -r requirements.txt`.")
    session_id = os.getenv("SALESFORCE_SESSION_ID")
    instance_url = os.getenv("SALESFORCE_INSTANCE_URL")
    if session_id and instance_url:
        return Salesforce(
            instance_url=instance_url,
            session_id=session_id,
            version=settings.salesforce_api_version.replace("v", ""),
        )

    return Salesforce(
        username=os.environ["SALESFORCE_USERNAME"],
        password=os.environ["SALESFORCE_PASSWORD"],
        security_token=os.environ["SALESFORCE_SECURITY_TOKEN"],
        domain=settings.salesforce_domain,
        version=settings.salesforce_api_version.replace("v", ""),
    )


def cell_to_value(cell: dict[str, Any]) -> Any:
    value = cell.get("label")
    if value in (None, ""):
        value = cell.get("value")
    if isinstance(value, dict):
        return value.get("label") or value.get("value") or str(value)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


def parse_report_json(report_json: dict[str, Any]) -> pd.DataFrame:
    metadata = report_json.get("reportMetadata", {})
    extended = report_json.get("reportExtendedMetadata", {})
    detail_columns = metadata.get("detailColumns", [])
    detail_info = extended.get("detailColumnInfo", {})

    labels = [
        detail_info.get(column, {}).get("label")
        or detail_info.get(column, {}).get("name")
        or column
        for column in detail_columns
    ]

    rows: list[dict[str, Any]] = []
    for fact in report_json.get("factMap", {}).values():
        for row in fact.get("rows", []) or []:
            cells = row.get("dataCells", [])
            record = {
                labels[index] if index < len(labels) else f"column_{index + 1}": cell_to_value(cell)
                for index, cell in enumerate(cells)
            }
            rows.append(record)

    if not rows:
        return pd.DataFrame(columns=labels)
    return pd.DataFrame(rows).drop_duplicates()


def fetch_report_dataframe(
    settings: Settings, report_id: str, raw_json_path=None
) -> pd.DataFrame:
    sf = create_salesforce_client(settings)
    report = sf.restful(
        f"analytics/reports/{report_id}",
        params={"includeDetails": "true"},
        method="GET",
    )
    if raw_json_path:
        write_json(report, raw_json_path)
    return parse_report_json(report)
