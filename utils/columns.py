from __future__ import annotations

from datetime import date

import pandas as pd

from utils.io import clean_blank, coalesce
from utils.text import (
    extract_domains,
    infer_date_from_text,
    normalize_creator_name,
    normalize_text,
    slugify_column,
)


ALIASES = {
    "project_project_name": "creator",
    "onboarding_project_link_project_name": "creator",
    "project_name": "creator",
    "creator": "creator",
    "site": "creator",
    "lead_contact": "lead_contact",
    "lead": "lead_contact",
    "contact": "lead_contact",
    "lead_cg_involvement": "cg_involvement",
    "cg_involvement": "cg_involvement",
    "lead_current_ad_network": "previous_ad_network",
    "current_ad_network": "previous_ad_network",
    "previous_ad_network": "previous_ad_network",
    "project_owner_name": "owner",
    "project_owner": "owner",
    "onboarding_project_link_owner_name": "owner",
    "owner": "owner",
    "description": "description",
    "lead_monthly_pageview_estimate": "monthly_pageview_estimate",
    "monthly_pageview_estimate": "monthly_pageview_estimate",
    "monthly_pageviews": "monthly_pageview_estimate",
    "service_level": "service_level",
    "lead_vertical": "vertical",
    "vertical": "vertical",
    "lead_cg_effort": "cg_effort",
    "cg_effort": "cg_effort",
    "cancelled_reason": "cancelled_reason",
    "canceled_reason": "cancelled_reason",
    "cancel_reason": "cancelled_reason",
    "cancelled_date": "dropped_date",
    "canceled_date": "dropped_date",
    "drop_date": "dropped_date",
    "dropped_date": "dropped_date",
    "project_cancelled_date": "dropped_date",
    "project_canceled_date": "dropped_date",
    "onboarding_project_link_scheduled_install_date": "scheduled_install_date",
    "scheduled_install_date": "scheduled_install_date",
    "install_date": "install_date",
    "returned_date": "returned_date",
    "conversion_date": "conversion_date",
    "project_id": "salesforce_project_id",
    "salesforce_project_id": "salesforce_project_id",
    "account_id": "salesforce_account_id",
    "salesforce_account_id": "salesforce_account_id",
    "lead_id": "salesforce_lead_id",
    "salesforce_lead_id": "salesforce_lead_id",
}

CANONICAL_COLUMNS = [
    "creator",
    "lead_contact",
    "previous_ad_network",
    "owner",
    "cg_involvement",
    "cg_effort",
    "description",
    "monthly_pageview_estimate",
    "service_level",
    "vertical",
    "cancelled_reason",
    "dropped_date",
    "scheduled_install_date",
    "install_date",
    "returned_date",
    "conversion_date",
    "salesforce_project_id",
    "salesforce_account_id",
    "salesforce_lead_id",
    "domain",
]


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    seen: dict[str, int] = {}
    for column in df.columns:
        slug = slugify_column(column)
        canonical = ALIASES.get(slug, slug)
        count = seen.get(canonical, 0)
        seen[canonical] = count + 1
        if count:
            canonical = f"{canonical}_{count + 1}"
        rename_map[column] = canonical
    return df.rename(columns=rename_map)


def parse_date_column(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.map(clean_blank), errors="coerce")


def canonicalize_dataframe(
    df: pd.DataFrame, source: str, reference_date: date | None = None
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS + ["source"])

    out = rename_columns(df.copy())
    for column in out.columns:
        if out[column].dtype == object:
            out[column] = out[column].map(clean_blank)

    for column in CANONICAL_COLUMNS:
        if column not in out.columns:
            out[column] = ""

    out["source"] = source

    for date_column in (
        "dropped_date",
        "scheduled_install_date",
        "install_date",
        "returned_date",
        "conversion_date",
    ):
        out[date_column] = parse_date_column(out[date_column])

    if source == "dropped":
        inferred = out["description"].map(
            lambda value: infer_date_from_text(value, reference=reference_date)
        )
        out["dropped_date"] = out["dropped_date"].fillna(inferred)

    if source == "returning":
        out["returned_date"] = out["returned_date"].fillna(out["install_date"])
        out["returned_date"] = out["returned_date"].fillna(out["scheduled_install_date"])

    out["creator"] = out.apply(
        lambda row: coalesce(row.get("creator"), row.get("site"), row.get("domain")),
        axis=1,
    )
    out["domain"] = out.apply(
        lambda row: coalesce(
            row.get("domain"),
            ", ".join(
                extract_domains(
                    row.get("creator"),
                    row.get("description"),
                    row.get("lead_contact"),
                )
            ),
        ),
        axis=1,
    )
    out["creator_key"] = out["creator"].map(normalize_creator_name)
    out["lead_key"] = out["lead_contact"].map(normalize_creator_name)
    out["domain_key"] = out["domain"].map(normalize_text)
    out["network_key"] = out["previous_ad_network"].map(normalize_text)
    out["service_level_key"] = out["service_level"].map(normalize_text)
    out["vertical_key"] = out["vertical"].map(normalize_text)
    out["owner_key"] = out["owner"].map(normalize_text)

    return out


def format_date_for_output(series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(series, errors="coerce")
    return dates.dt.strftime("%Y-%m-%d").fillna("")

