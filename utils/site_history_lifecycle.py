from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from utils.columns import format_date_for_output
from utils.io import clean_blank
from utils.lifecycle import MASTER_COLUMNS
from utils.reasons import normalize_dropped_reason
from utils.text import normalize_creator_name
from utils.zendesk_client import format_macro_cadence


ACTIVE_LIFECYCLE_STATUSES = {"pending", "active", "setup", "install", "checkup"}
DROP_LIFECYCLE_STATUSES = {"dropped", "cancelled", "canceled", "offboarded"}

FULL_HISTORY_EXTRA_COLUMNS = [
    "current_status",
    "onboard_year",
    "returned_year",
    "drop_count",
    "dropped_dates",
    "install_history",
    "site_history_event_count",
    "has_3_day_followup",
    "has_5_day_followup",
    "has_7_day_followup",
    "normalized_dropped_reason",
    "source_full_site_history",
]

FULL_HISTORY_MASTER_COLUMNS = MASTER_COLUMNS + [
    column for column in FULL_HISTORY_EXTRA_COLUMNS if column not in MASTER_COLUMNS
]


def normalize_history_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        for column in out.columns
    ]
    return out


def _blank_series(index: pd.Index) -> pd.Series:
    return pd.Series("", index=index, dtype="object")


def _field(df: pd.DataFrame, aliases: Iterable[str]) -> pd.Series:
    out = _blank_series(df.index)
    for alias in aliases:
        column = re.sub(r"[^a-z0-9]+", "_", alias.strip().lower()).strip("_")
        if column not in df.columns:
            continue
        candidate = df[column].fillna("").astype(str).map(clean_blank)
        out = out.where(out.map(bool), candidate)
    return out


def _last_present(group: pd.DataFrame, column: str) -> str:
    if column not in group.columns:
        return ""
    values = group[column].fillna("").astype(str).map(clean_blank)
    values = values[values.ne("")]
    if values.empty:
        return ""
    return values.iloc[-1]


def _first_present(group: pd.DataFrame, column: str) -> str:
    if column not in group.columns:
        return ""
    values = group[column].fillna("").astype(str).map(clean_blank)
    values = values[values.ne("")]
    if values.empty:
        return ""
    return values.iloc[0]


def _status_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_blank(value).lower())


def _date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.fillna("").astype(str).map(clean_blank), errors="coerce")


def _format_date(value: object) -> str:
    return format_date_for_output(pd.Series([value])).iloc[0]


def _date_list(values: pd.Series) -> str:
    dates = sorted(
        {
            parsed.strftime("%Y-%m-%d")
            for parsed in pd.to_datetime(values, errors="coerce").dropna()
        }
    )
    return "; ".join(dates)


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna("").astype(str).str.strip().str.lower().isin(
        {"1", "true", "yes", "y", "booked", "installed", "converted"}
    )


def _macro_cadence(row: dict[str, object]) -> str:
    days = [
        day
        for day, column in (
            ("3", "has_3_day_followup"),
            ("5", "has_5_day_followup"),
            ("7", "has_7_day_followup"),
        )
        if bool(row.get(column))
    ]
    return format_macro_cadence(days)


def _cg_label(value: object) -> str:
    clean = clean_blank(value)
    key = clean.lower()
    if key in {"1", "true", "yes", "y", "assisted"}:
        return "Assisted"
    if "assisted" in key and "not" not in key and "non" not in key:
        return "Assisted"
    return "Not Assisted"


def _drop_reason_for_group(group: pd.DataFrame, latest_drop: pd.Timestamp) -> str:
    reason_columns = [
        "dropped_reason",
        "cancelled_reason",
        "canceled_reason",
        "drop_reason",
        "reason_they_left",
        "reason_they_left_specifics",
        "dropped_reason_category",
    ]
    reason_frame = group.copy()
    if pd.notna(latest_drop):
        same_drop_date = reason_frame["_drop_date"].eq(latest_drop)
        status_drop = reason_frame["_status_key"].isin(DROP_LIFECYCLE_STATUSES)
        filtered = reason_frame.loc[same_drop_date | status_drop]
        if not filtered.empty:
            reason_frame = filtered
    for column in reason_columns:
        value = _last_present(reason_frame, column)
        if value:
            return value
    for column in reason_columns:
        value = _last_present(group, column)
        if value:
            return value
    return ""


def _build_group_row(site_key: str, group: pd.DataFrame) -> dict[str, object]:
    group = group.sort_values(["_event_at", "_row_order"], na_position="last").copy()
    current_status = _last_present(group, "current_status") or _last_present(group, "status")
    current_status_key = _status_key(current_status)
    active_current_status = current_status_key in ACTIVE_LIFECYCLE_STATUSES

    install_dates = group["_install_date"].dropna()
    latest_install = install_dates.max() if not install_dates.empty else pd.NaT

    explicit_drop_dates = group["_drop_date"].dropna()
    status_drop_dates = group.loc[group["_status_key"].isin(DROP_LIFECYCLE_STATUSES), "_event_at"].dropna()
    all_drop_dates = pd.concat([explicit_drop_dates, status_drop_dates]).dropna()
    latest_drop = all_drop_dates.max() if not all_drop_dates.empty else pd.NaT
    has_drop = pd.notna(latest_drop)

    returned_after_drop = install_dates[install_dates > latest_drop] if has_drop else pd.Series(dtype="datetime64[ns]")
    latest_return = returned_after_drop.max() if not returned_after_drop.empty else pd.NaT
    has_return_after_drop = pd.notna(latest_return)

    if has_drop and has_return_after_drop and active_current_status:
        outcome = "Returned"
    elif has_drop and not has_return_after_drop and not active_current_status:
        outcome = "Dropped"
    elif active_current_status:
        outcome = "Active"
    else:
        outcome = "Inactive"

    raw_reason = _drop_reason_for_group(group, latest_drop)
    normalized_reason = normalize_dropped_reason(raw_reason, has_drop=has_drop)
    dropped_date = _format_date(latest_drop)
    returned_date = _format_date(latest_return)
    install_date = _format_date(latest_install)
    days_to_return = ""
    if pd.notna(latest_drop) and pd.notna(latest_return):
        days_to_return = str(int((latest_return - latest_drop).days))

    owner_name = _last_present(group, "site_owner_name") or _last_present(group, "creator_name") or _last_present(group, "lead_contact")
    site_name = (
        _last_present(group, "site_name")
        or _last_present(group, "company_name")
        or owner_name
        or site_key
    )
    onboard_owner = _last_present(group, "onboard_owner_name") or _last_present(group, "onboarding_owner")
    cg_signal = (
        _last_present(group, "cg_assisted")
        or _last_present(group, "cg_involvement")
        or _last_present(group, "creator_growth")
    )

    row: dict[str, object] = {
        "lifecycle_creator_id": site_key,
        "creator_project_name": site_name,
        "lead_contact": owner_name,
        "company_name": _last_present(group, "company_name") or site_name,
        "domain": _last_present(group, "domain") or _last_present(group, "website") or _last_present(group, "url"),
        "site_id": _last_present(group, "site_id"),
        "salesforce_project_id": _last_present(group, "project_id") or _last_present(group, "salesforce_project_id"),
        "salesforce_account_id": _last_present(group, "salesforce_account_id") or _last_present(group, "account_id"),
        "salesforce_lead_id": _last_present(group, "salesforce_lead_id") or _last_present(group, "lead_id"),
        "vertical": _last_present(group, "primary_vertical") or _last_present(group, "verticals") or _last_present(group, "vertical"),
        "service_level": _last_present(group, "service_level"),
        "previous_ad_network": _last_present(group, "previous_ad_network"),
        "onboarding_owner": onboard_owner,
        "monthly_pageviews": _last_present(group, "monthly_pageviews") or _last_present(group, "monthly_pageview_estimate"),
        "dropped_status": current_status,
        "onboarding_started_date": _format_date(_first_present(group, "onboarding_started_date")),
        "dropped_date": dropped_date,
        "returned_date": returned_date,
        "scheduled_install_date": "",
        "install_date": install_date,
        "days_to_return": days_to_return,
        "cancellation_reason": _last_present(group, "cancelled_reason") or _last_present(group, "canceled_reason"),
        "dropped_reason": raw_reason,
        "dropped_reason_category": normalized_reason if has_drop else "",
        "raw_description": _last_present(group, "raw_description") or _last_present(group, "description"),
        "normalized_reason": normalized_reason if has_drop else "",
        "reason_confidence_score": "",
        "reason_classification_method": "full_site_history_exact_bucket" if has_drop else "",
        "zendesk_ticket_ids": _last_present(group, "zendesk_ticket_ids"),
        "zendesk_ticket_created_dates": _last_present(group, "zendesk_ticket_created_dates"),
        "zendesk_ticket_solved_dates": _last_present(group, "zendesk_ticket_solved_dates"),
        "zendesk_ticket_count": _last_present(group, "zendesk_ticket_count") or 0,
        "ticket_reopened": bool(_bool_series(group.get("ticket_reopened", pd.Series(False, index=group.index))).any()),
        "cg_involvement": _cg_label(cg_signal),
        "cg_effort": _last_present(group, "cg_effort"),
        "cg_escalation_status": bool(_bool_series(group.get("cg_escalation_status", pd.Series(False, index=group.index))).any()),
        "cg_escalation_timing": "",
        "cg_first_touch_at": _last_present(group, "cg_first_touch_at"),
        "cg_days_from_drop": "",
        "onboarding_call_offered": bool(_bool_series(group.get("onboarding_call_offered", pd.Series(False, index=group.index))).any()),
        "salesloft_meeting_detected": bool(_bool_series(group.get("salesloft_meeting_detected", pd.Series(False, index=group.index))).any()),
        "first_salesloft_meeting_at": _last_present(group, "first_salesloft_meeting_at"),
        "slack_intervention_detected": bool(_bool_series(group.get("slack_intervention_detected", pd.Series(False, index=group.index))).any()),
        "slack_intervention_count": _last_present(group, "slack_intervention_count") or 0,
        "rescue_intervention_detected": bool(_bool_series(group.get("rescue_intervention_detected", pd.Series(False, index=group.index))).any()),
        "install_completed": active_current_status and pd.notna(latest_install),
        "converted": active_current_status and pd.notna(latest_install),
        "reengaged": outcome == "Returned",
        "outcome": outcome,
        "returning_project_name": site_name if outcome == "Returned" else "",
        "returning_lead_contact": owner_name if outcome == "Returned" else "",
        "returning_previous_ad_network": _last_present(group, "previous_ad_network") if outcome == "Returned" else "",
        "returning_owner": onboard_owner if outcome == "Returned" else "",
        "returning_status": current_status if outcome == "Returned" else "",
        "match_method": "full_site_history",
        "match_score": 100,
        "source_salesforce_dropped": False,
        "source_salesforce_returning": False,
        "source_snowflake": True,
        "current_status": current_status,
        "onboard_year": str(latest_install.year) if pd.notna(latest_install) else "",
        "returned_year": str(latest_return.year) if pd.notna(latest_return) else "",
        "drop_count": len({date.strftime("%Y-%m-%d") for date in all_drop_dates.dropna()}),
        "dropped_dates": _date_list(all_drop_dates),
        "install_history": _date_list(install_dates),
        "site_history_event_count": len(group),
        "has_3_day_followup": bool(_bool_series(group.get("has_3_day_followup", pd.Series(False, index=group.index))).any()),
        "has_5_day_followup": bool(_bool_series(group.get("has_5_day_followup", pd.Series(False, index=group.index))).any()),
        "has_7_day_followup": bool(_bool_series(group.get("has_7_day_followup", pd.Series(False, index=group.index))).any()),
        "normalized_dropped_reason": normalized_reason if has_drop else "",
        "source_full_site_history": True,
    }
    row["creator_key"] = normalize_creator_name(row["creator_project_name"])
    row["lead_key"] = normalize_creator_name(row["lead_contact"])
    row["macro_cadence"] = _macro_cadence(row)
    return row


def build_master_from_site_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=FULL_HISTORY_MASTER_COLUMNS)

    out = normalize_history_columns(history)
    out["_row_order"] = range(len(out))
    out["site_id"] = _field(out, ["site_id", "siteid", "id"])
    out["project_id"] = _field(out, ["project_id", "salesforce_project_id", "onboarding_project_id"])
    out["salesforce_account_id"] = _field(out, ["salesforce_account_id", "account_id"])
    out["salesforce_lead_id"] = _field(out, ["salesforce_lead_id", "lead_id"])
    out["site_name"] = _field(out, ["site_name", "account_name", "company_name", "project_name", "creator_project_name"])
    out["site_owner_name"] = _field(out, ["site_owner_name"])
    out["creator_name"] = _field(out, ["creator_name", "lead_contact", "contact_name", "lead_name", "site_owner_name"])
    out["company_name"] = _field(out, ["company_name", "account_name"])
    out["domain"] = _field(out, ["domain", "website", "site_domain", "url"])
    out["current_status"] = _field(out, ["current_status", "current_site_status", "status", "site_status"])
    out["status"] = _field(out, ["status", "site_history_status", "history_status"])
    out["service_level"] = _field(out, ["service_level"])
    out["primary_vertical"] = _field(out, ["primary_vertical"])
    out["verticals"] = _field(out, ["verticals", "vertical"])
    out["previous_ad_network"] = _field(out, ["previous_ad_network", "current_ad_network", "ad_network"])
    out["onboard_owner_name"] = _field(out, ["onboard_owner_name", "onboarding_owner", "owner_name", "project_owner_name"])
    out["dropped_reason"] = _field(out, ["dropped_reason", "drop_reason", "reason"])
    out["dropped_reason_category"] = _field(out, ["dropped_reason_category", "reason_category"])
    out["cancelled_reason"] = _field(out, ["cancelled_reason", "canceled_reason", "cancellation_reason"])
    out["install_date"] = _field(out, ["install_date", "actual_install_date"])
    out["dropped_date"] = _field(out, ["dropped_date", "drop_date", "cancelled_date", "canceled_date", "offboarded_date"])
    out["event_date"] = _field(out, ["event_date", "history_date", "updated_at", "created_at", "status_updated_at"])
    out["onboarding_started_date"] = _field(out, ["onboarding_started_date", "setup_date", "setup_started_date"])
    out["has_3_day_followup"] = _field(out, ["has_3_day_followup", "has_3_day_macro", "macro_day_3"])
    out["has_5_day_followup"] = _field(out, ["has_5_day_followup", "has_5_day_macro", "macro_day_5"])
    out["has_7_day_followup"] = _field(out, ["has_7_day_followup", "has_7_day_macro", "macro_day_7"])
    out["cg_assisted"] = _field(out, ["cg_assisted", "cg_effort", "cg_effort_c"])
    out["cg_involvement"] = _field(out, ["cg_involvement", "cg_involvement_c"])

    out["_install_date"] = _date_series(out["install_date"])
    out["_drop_date"] = _date_series(out["dropped_date"])
    out["_event_at"] = _date_series(out["event_date"]).fillna(out["_drop_date"]).fillna(out["_install_date"])
    out["_status_key"] = out["current_status"].where(out["current_status"].map(bool), out["status"]).map(_status_key)

    out["_site_key"] = out["site_id"]
    fallback = (
        out["salesforce_account_id"]
        .where(out["salesforce_account_id"].map(bool), out["domain"])
        .where(lambda value: value.map(bool), out["site_name"].map(normalize_creator_name))
    )
    out.loc[out["_site_key"].eq(""), "_site_key"] = fallback
    out = out.loc[out["_site_key"].map(bool)].copy()

    rows = [
        _build_group_row(site_key, group)
        for site_key, group in out.groupby("_site_key", sort=False)
    ]
    master = pd.DataFrame(rows, columns=FULL_HISTORY_MASTER_COLUMNS)
    for column in master.select_dtypes(include=["object"]).columns:
        master[column] = master[column].map(clean_blank)
    return master.sort_values(["outcome", "dropped_date", "creator_project_name"], na_position="last")
