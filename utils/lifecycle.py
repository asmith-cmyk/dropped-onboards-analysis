from __future__ import annotations

import re

import pandas as pd

from utils.analysis import bool_series, derive_cg_timing, link_slack, link_zendesk
from utils.columns import format_date_for_output
from utils.io import clean_blank
from utils.text import normalize_creator_name


MASTER_COLUMNS = [
    "lifecycle_creator_id",
    "creator_project_name",
    "lead_contact",
    "company_name",
    "domain",
    "site_id",
    "salesforce_project_id",
    "salesforce_account_id",
    "salesforce_lead_id",
    "creator_key",
    "lead_key",
    "vertical",
    "service_level",
    "previous_ad_network",
    "onboarding_owner",
    "monthly_pageviews",
    "dropped_status",
    "dropped_date",
    "returned_date",
    "scheduled_install_date",
    "install_date",
    "days_to_return",
    "cancellation_reason",
    "dropped_reason_category",
    "raw_description",
    "normalized_reason",
    "reason_confidence_score",
    "reason_classification_method",
    "macro_cadence",
    "zendesk_ticket_ids",
    "zendesk_ticket_created_dates",
    "zendesk_ticket_solved_dates",
    "zendesk_ticket_count",
    "ticket_reopened",
    "cg_involvement",
    "cg_effort",
    "cg_escalation_status",
    "cg_escalation_timing",
    "cg_first_touch_at",
    "cg_days_from_drop",
    "onboarding_call_offered",
    "salesloft_meeting_detected",
    "first_salesloft_meeting_at",
    "slack_intervention_detected",
    "slack_intervention_count",
    "rescue_intervention_detected",
    "install_completed",
    "converted",
    "reengaged",
    "outcome",
    "returning_project_name",
    "returning_lead_contact",
    "returning_previous_ad_network",
    "returning_owner",
    "returning_status",
    "match_method",
    "match_score",
    "source_salesforce_dropped",
    "source_salesforce_returning",
    "source_snowflake",
]


def _series_or_default(df: pd.DataFrame, column: str, default="") -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(default, index=df.index)


def _bool_or_default(df: pd.DataFrame, column: str, default=False) -> pd.Series:
    if column in df.columns:
        return bool_series(df[column], index=df.index)
    return pd.Series(default, index=df.index)


def _numeric_or_default(df: pd.DataFrame, column: str, default=0) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index)


def _format_datetime(series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(series, errors="coerce")
    return dates.dt.strftime("%Y-%m-%dT%H:%M:%S%z").fillna("")


def _format_days(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.astype("Int64").astype(str).replace("<NA>", "")


def _format_date_like(series: pd.Series, numeric_unit: str = "s") -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    parsed = pd.to_datetime(text.where(numeric.isna(), ""), errors="coerce")
    numeric_dates = pd.to_datetime(numeric, errors="coerce", unit=numeric_unit, origin="unix")
    parsed = parsed.fillna(numeric_dates)
    return format_date_for_output(parsed)


def _is_present(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return clean_blank(value) != ""


def _setup_cancellation_mask(*series: pd.Series) -> pd.Series:
    if not series:
        return pd.Series(dtype=bool)
    combined = pd.Series("", index=series[0].index)
    for item in series:
        combined = combined + " " + item.fillna("").astype(str)
    normalized = combined.str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    return normalized.str.contains("setupcancellation", regex=False, na=False) | normalized.str.contains(
        "setupcancelled", regex=False, na=False
    )


def _setup_cancellation_note_mask(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    return text.str.match(r"^setup\s+cancellation\s+note\b", case=False, na=False)


def _snowflake_reason_category(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    category = _series_or_default(df, "dropped_reason_category").fillna("").astype(str).map(clean_blank)
    description = _series_or_default(df, "raw_description").fillna("").astype(str)
    reason = _series_or_default(df, "dropped_reason").fillna("").astype(str)
    setup_note_mask = _setup_cancellation_note_mask(description)
    setup_mask = _setup_cancellation_mask(category, description, reason)

    derived = pd.Series("", index=df.index)
    derived.loc[setup_mask] = "Set-up cancellation"
    derived.loc[setup_note_mask] = "Cancelled Pre-onboarding"

    category_present = category.map(_is_present)
    out = category.where(category_present, derived)
    out.loc[setup_note_mask] = "Cancelled Pre-onboarding"

    method = pd.Series("", index=df.index)
    method.loc[category_present] = "snowflake_category"
    method.loc[~category_present & derived.map(_is_present)] = "description_pattern"
    method.loc[setup_note_mask] = "description_pattern"
    return out, method


def _coerce_bool(value: object) -> bool:
    return clean_blank(value).lower() in {"1", "true", "yes", "y", "booked", "installed", "converted"}


def _cg_involvement_label(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    assisted = (
        (
            normalized.str.contains("assisted", regex=False)
            | normalized.isin({"1", "true", "yes", "y"})
        )
        & ~normalized.str.contains("non", regex=False)
        & ~normalized.str.contains("not", regex=False)
        & ~normalized.isin({"", "none", "no", "false", "0", "not assisted"})
    )
    return pd.Series("Not Assisted", index=series.index).where(~assisted, "Assisted")


def _cadence_has_days(value: object, required_days: set[str]) -> bool:
    days = set(re.findall(r"\b(?:3|5|7|10)\b", clean_blank(value)))
    return required_days.issubset(days)


def _outcome_series(df: pd.DataFrame) -> pd.Series:
    installed = bool_series(_series_or_default(df, "install_completed", False), index=df.index)
    reengaged = bool_series(_series_or_default(df, "reengaged", False), index=df.index)
    cadence = _series_or_default(df, "macro_cadence", "None").fillna("").astype(str).str.strip()
    outcome = pd.Series("Dropped", index=df.index)
    outcome.loc[reengaged] = "Returned"
    outcome.loc[installed & cadence.map(lambda value: _cadence_has_days(value, {"3", "5", "7"}))] = (
        "Re-engaged & Installed"
    )
    return outcome


def _recalculate_lifecycle_flags(lifecycle: pd.DataFrame) -> pd.DataFrame:
    out = lifecycle.copy()
    dropped = pd.to_datetime(_series_or_default(out, "dropped_date"), errors="coerce")
    returned = pd.to_datetime(_series_or_default(out, "returned_date"), errors="coerce")
    install = pd.to_datetime(_series_or_default(out, "install_date"), errors="coerce")
    scheduled_install = pd.to_datetime(_series_or_default(out, "scheduled_install_date"), errors="coerce")

    returned = returned.fillna(install).fillna(scheduled_install)
    out["returned_date"] = format_date_for_output(returned)
    out["days_to_return"] = _format_days((returned - dropped).dt.days)

    install_completed = bool_series(_series_or_default(out, "install_completed", False), index=out.index) | install.notna()
    reengaged = bool_series(_series_or_default(out, "reengaged", False), index=out.index) | returned.notna()
    converted = bool_series(_series_or_default(out, "converted", False), index=out.index) | install_completed

    out["install_completed"] = install_completed
    out["converted"] = converted
    out["reengaged"] = reengaged
    out["source_salesforce_returning"] = bool_series(
        _series_or_default(out, "source_salesforce_returning", False), index=out.index
    )
    out["outcome"] = _outcome_series(out)
    return out


def apply_manual_overrides(lifecycle: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Apply explicit lifecycle corrections by creator key.

    Manual overrides are intentionally small and auditable. They are useful when a
    signal is confirmed in Slack or Salesforce but is not yet present in the
    exported source files available to the automated pipeline.
    """
    if lifecycle.empty or overrides.empty:
        return lifecycle

    out = lifecycle.copy()
    if "creator_key" not in out.columns:
        out["creator_key"] = out["creator_project_name"].map(normalize_creator_name)

    manual = overrides.copy()
    if "creator_key" not in manual.columns:
        source_names = manual["creator_project_name"] if "creator_project_name" in manual.columns else pd.Series("", index=manual.index)
        manual["creator_key"] = source_names.map(normalize_creator_name)
    manual["creator_key"] = manual["creator_key"].fillna("").map(clean_blank)

    bool_columns = {
        "ticket_reopened",
        "cg_escalation_status",
        "onboarding_call_offered",
        "salesloft_meeting_detected",
        "slack_intervention_detected",
        "rescue_intervention_detected",
        "install_completed",
        "converted",
        "reengaged",
        "source_salesforce_dropped",
        "source_salesforce_returning",
        "source_snowflake",
    }
    numeric_columns = {
        "zendesk_ticket_count",
        "slack_intervention_count",
        "match_score",
        "reason_confidence_score",
    }
    skip_columns = {"creator_key", "manual_note", "override_note", "notes"}

    for _, override in manual.iterrows():
        creator_key = override.get("creator_key", "")
        if not creator_key:
            continue
        matches = out.index[out["creator_key"] == creator_key]
        if matches.empty:
            continue
        idx = matches[0]
        for column, value in override.items():
            if column in skip_columns or column not in out.columns or not _is_present(value):
                continue
            if column in bool_columns:
                out.at[idx, column] = _coerce_bool(value)
            elif column in numeric_columns:
                out.at[idx, column] = pd.to_numeric(value, errors="coerce")
            else:
                out.at[idx, column] = value

    out["macro_cadence"] = _series_or_default(out, "macro_cadence", "None").replace({"": "None", "Unknown": "None"})
    out = _recalculate_lifecycle_flags(out)
    return out


def _attach_classifications(matches: pd.DataFrame, classifications: pd.DataFrame) -> pd.DataFrame:
    out = matches.copy()
    for column in (
        "raw_description",
        "raw_cancelled_reason",
        "normalized_category",
        "confidence_score",
        "classification_method",
    ):
        if column not in out.columns:
            out[column] = ""

    if classifications.empty:
        return out

    cols = [
        column
        for column in (
            "creator_key",
            "raw_description",
            "raw_cancelled_reason",
            "normalized_category",
            "confidence_score",
            "classification_method",
        )
        if column in classifications.columns
    ]
    enriched = out.merge(
        classifications[cols].drop_duplicates(subset=["creator_key"]),
        on="creator_key",
        how="left",
        suffixes=("", "_classified"),
    )
    for base in (
        "raw_description",
        "raw_cancelled_reason",
        "normalized_category",
        "confidence_score",
        "classification_method",
    ):
        classified = f"{base}_classified"
        if classified in enriched.columns:
            enriched[base] = enriched[classified].where(
                enriched[classified].astype(str).str.len() > 0,
                enriched[base],
            )
            enriched = enriched.drop(columns=[classified])
    return enriched


def _normalize_snowflake_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    return out


def _dedupe_snowflake_returned(returned: pd.DataFrame) -> pd.DataFrame:
    if returned.empty:
        return returned

    out = _normalize_snowflake_columns(returned)
    for column in (
        "project_id",
        "site_id",
        "creator_name",
        "company_name",
        "current_status",
        "actual_close_date",
        "expected_install_date",
        "lead_contact",
        "service_level",
        "vertical",
        "previous_ad_network",
        "onboarding_owner",
        "monthly_pageviews",
        "dropped_reason_category",
    ):
        if column not in out.columns:
            out[column] = ""
    out["_return_key"] = out["project_id"].map(clean_blank)
    fallback_key = (
        out["site_id"].map(clean_blank)
        + "|"
        + out["actual_close_date"].map(clean_blank)
        + "|"
        + out["creator_name"].map(normalize_creator_name)
    )
    out.loc[out["_return_key"].eq(""), "_return_key"] = fallback_key
    status_priority = {"active": 0, "checkup": 1, "install": 2, "setup": 3}
    out["_status_priority"] = out["current_status"].fillna("").astype(str).str.lower().map(status_priority).fillna(99)
    out["_expected_install_at"] = pd.to_datetime(
        _format_date_like(out["expected_install_date"], numeric_unit="D"), errors="coerce"
    )
    out["_actual_close_at"] = pd.to_datetime(_format_date_like(out["actual_close_date"], numeric_unit="s"), errors="coerce")
    out = out.sort_values(["_return_key", "_expected_install_at", "_status_priority", "_actual_close_at"])
    return out.drop_duplicates(subset=["_return_key"], keep="first").drop(
        columns=["_return_key", "_status_priority"]
    )


def _build_snowflake_lifecycle(dropped: pd.DataFrame, returned: pd.DataFrame) -> pd.DataFrame:
    if dropped.empty:
        return pd.DataFrame(columns=MASTER_COLUMNS)

    d = _normalize_snowflake_columns(dropped)
    for column in ("site_id", "creator_name", "company_name", "status", "actual_close_date"):
        if column not in d.columns:
            d[column] = ""
    d["_actual_close_at"] = pd.to_datetime(_format_date_like(d["actual_close_date"], numeric_unit="s"), errors="coerce")
    d["_drop_key"] = d.get("project_id", pd.Series("", index=d.index)).map(clean_blank)
    fallback_key = (
        d["site_id"].map(clean_blank)
        + "|"
        + d["actual_close_date"].map(clean_blank)
        + "|"
        + d["creator_name"].map(normalize_creator_name)
    )
    d.loc[d["_drop_key"].eq(""), "_drop_key"] = fallback_key
    d = d.sort_values(["_drop_key", "_actual_close_at"]).drop_duplicates(subset=["_drop_key"], keep="last")

    reason_category, reason_category_method = _snowflake_reason_category(d)
    d["_derived_dropped_reason_category"] = reason_category.to_numpy()
    d["_derived_reason_category_method"] = reason_category_method.to_numpy()
    r = _dedupe_snowflake_returned(returned)
    d["returning_status"] = ""
    d["returned_expected_install_date"] = ""
    d["returned_actual_close_date"] = ""
    if not r.empty:
        r = r[
            [
                "project_id",
                "site_id",
                "current_status",
                "expected_install_date",
                "actual_close_date",
                "lead_contact",
                "service_level",
                "vertical",
                "previous_ad_network",
                "onboarding_owner",
                "monthly_pageviews",
            ]
        ].rename(
            columns={
                "current_status": "returning_status",
                "expected_install_date": "returned_expected_install_date",
                "actual_close_date": "returned_actual_close_date",
                "lead_contact": "returning_lead_contact",
                "service_level": "returning_service_level",
                "vertical": "returning_vertical",
                "previous_ad_network": "returning_previous_ad_network",
                "onboarding_owner": "returning_onboarding_owner",
                "monthly_pageviews": "returning_monthly_pageviews",
            }
        )
        r["_project_key"] = r["project_id"].map(clean_blank)
        r_project = r[r["_project_key"].ne("")].drop_duplicates(subset=["_project_key"], keep="first")
        if not r_project.empty:
            d = d.merge(
                r_project[
                    [
                        "project_id",
                        "returning_status",
                        "returned_expected_install_date",
                        "returned_actual_close_date",
                        "returning_lead_contact",
                        "returning_service_level",
                        "returning_vertical",
                        "returning_previous_ad_network",
                        "returning_onboarding_owner",
                        "returning_monthly_pageviews",
                    ]
                ],
                on="project_id",
                how="left",
                suffixes=("", "_project"),
            )
            for column in (
                "returning_status",
                "returned_expected_install_date",
                "returned_actual_close_date",
                "returning_lead_contact",
                "returning_service_level",
                "returning_vertical",
                "returning_previous_ad_network",
                "returning_onboarding_owner",
                "returning_monthly_pageviews",
            ):
                project_column = f"{column}_project"
                if project_column in d.columns:
                    d[column] = d[project_column].where(d[project_column].map(_is_present), d[column])
                    d = d.drop(columns=[project_column])

        r_site = r.drop_duplicates(subset=["site_id", "returned_actual_close_date"], keep="first")
        if not r_site.empty:
            d = d.merge(
                r_site[
                    [
                        "site_id",
                        "returning_status",
                        "returned_expected_install_date",
                        "returned_actual_close_date",
                        "returning_lead_contact",
                        "returning_service_level",
                        "returning_vertical",
                        "returning_previous_ad_network",
                        "returning_onboarding_owner",
                        "returning_monthly_pageviews",
                    ]
                ],
                left_on=["site_id", "actual_close_date"],
                right_on=["site_id", "returned_actual_close_date"],
                how="left",
                suffixes=("", "_site"),
            )
            for column in (
                "returning_status",
                "returned_expected_install_date",
                "returned_actual_close_date",
                "returning_lead_contact",
                "returning_service_level",
                "returning_vertical",
                "returning_previous_ad_network",
                "returning_onboarding_owner",
                "returning_monthly_pageviews",
            ):
                site_column = f"{column}_site"
                if site_column in d.columns:
                    d[column] = d[column].where(d[column].map(_is_present), d[site_column])
                    d = d.drop(columns=[site_column])

        return_metadata = {
            "lead_contact": "returning_lead_contact",
            "service_level": "returning_service_level",
            "vertical": "returning_vertical",
            "previous_ad_network": "returning_previous_ad_network",
            "monthly_pageviews": "returning_monthly_pageviews",
        }
        for target, source in return_metadata.items():
            if source in d.columns:
                if target not in d.columns:
                    d[target] = ""
                d[target] = d[source].where(d[source].map(_is_present), d[target])

    dropped_date = d["_actual_close_at"]
    expected_install = pd.to_datetime(_format_date_like(d["returned_expected_install_date"], numeric_unit="D"), errors="coerce")
    reengaged = expected_install.notna()
    returning_status = d["returning_status"].fillna("").astype(str)
    install_completed = returning_status.str.lower().isin({"active", "checkup"})

    lifecycle = pd.DataFrame(index=d.index)
    lifecycle["lifecycle_creator_id"] = d.get("project_id", d["site_id"]).fillna("").astype(str)
    lifecycle["creator_project_name"] = d["creator_name"]
    lifecycle["lead_contact"] = d.get("lead_contact", "")
    lifecycle["company_name"] = d["company_name"]
    lifecycle["domain"] = d.get("domain", "")
    lifecycle["site_id"] = d["site_id"]
    lifecycle["salesforce_project_id"] = d.get("project_id", "")
    lifecycle["salesforce_account_id"] = d.get("salesforce_account_id", "")
    lifecycle["salesforce_lead_id"] = d.get("salesforce_lead_id", "")
    lifecycle["creator_key"] = d["creator_name"].map(normalize_creator_name)
    lifecycle["lead_key"] = d.get("lead_contact", "").map(normalize_creator_name) if "lead_contact" in d.columns else ""
    lifecycle["vertical"] = d.get("vertical", "")
    lifecycle["service_level"] = d.get("service_level", "")
    lifecycle["previous_ad_network"] = d.get("previous_ad_network", "")
    lifecycle["onboarding_owner"] = d.get("onboarding_owner", "")
    lifecycle["monthly_pageviews"] = d.get("monthly_pageviews", "")
    lifecycle["dropped_status"] = d["status"]
    lifecycle["dropped_date"] = format_date_for_output(dropped_date)
    lifecycle["returned_date"] = format_date_for_output(expected_install)
    lifecycle["scheduled_install_date"] = format_date_for_output(expected_install)
    lifecycle["install_date"] = ""
    lifecycle["days_to_return"] = _format_days((expected_install - dropped_date).dt.days)
    lifecycle["cancellation_reason"] = d.get("dropped_reason", "")
    lifecycle["dropped_reason_category"] = d["_derived_dropped_reason_category"]
    lifecycle["raw_description"] = d.get("raw_description", "")
    lifecycle["normalized_reason"] = lifecycle["dropped_reason_category"].where(
        lifecycle["dropped_reason_category"].map(_is_present), "Unknown"
    )
    lifecycle["reason_confidence_score"] = ""
    lifecycle["reason_classification_method"] = d["_derived_reason_category_method"]
    lifecycle["macro_cadence"] = "None"
    lifecycle["zendesk_ticket_ids"] = ""
    lifecycle["zendesk_ticket_created_dates"] = ""
    lifecycle["zendesk_ticket_solved_dates"] = ""
    lifecycle["zendesk_ticket_count"] = 0
    lifecycle["ticket_reopened"] = False
    lifecycle["cg_involvement"] = _cg_involvement_label(d.get("cg_involvement", pd.Series("", index=d.index)))
    lifecycle["cg_effort"] = d.get("cg_effort", "")
    lifecycle["cg_escalation_status"] = False
    lifecycle["cg_escalation_timing"] = "No CG involvement"
    lifecycle["cg_first_touch_at"] = ""
    lifecycle["cg_days_from_drop"] = ""
    lifecycle["onboarding_call_offered"] = False
    lifecycle["salesloft_meeting_detected"] = False
    lifecycle["first_salesloft_meeting_at"] = ""
    lifecycle["slack_intervention_detected"] = False
    lifecycle["slack_intervention_count"] = 0
    lifecycle["rescue_intervention_detected"] = False
    lifecycle["install_completed"] = install_completed
    lifecycle["converted"] = install_completed
    lifecycle["reengaged"] = reengaged
    lifecycle["outcome"] = _outcome_series(lifecycle)
    lifecycle["returning_project_name"] = d["creator_name"].where(reengaged, "")
    lifecycle["returning_lead_contact"] = ""
    lifecycle["returning_previous_ad_network"] = ""
    lifecycle["returning_owner"] = _series_or_default(d, "returning_onboarding_owner").where(reengaged, "")
    lifecycle["returning_status"] = returning_status.where(reengaged, "")
    lifecycle["match_method"] = "snowflake_site_id"
    lifecycle["match_score"] = 100
    lifecycle["source_salesforce_dropped"] = True
    lifecycle["source_salesforce_returning"] = False
    lifecycle["source_snowflake"] = True

    return lifecycle[MASTER_COLUMNS]


def _dedupe_lifecycle_rows(lifecycle: pd.DataFrame) -> pd.DataFrame:
    if lifecycle.empty:
        return lifecycle

    out = lifecycle.copy()
    out["_source_priority"] = (~bool_series(out.get("source_snowflake", False), index=out.index)).astype(int)
    out = out.sort_values(["_source_priority", "dropped_date", "creator_project_name"])

    out["_project_key"] = out["salesforce_project_id"].map(clean_blank)
    with_project = out[out["_project_key"].ne("")].drop_duplicates(subset=["_project_key"], keep="first")
    without_project = out[out["_project_key"].eq("")]
    out = pd.concat([with_project, without_project], ignore_index=True)

    out["_natural_key"] = (
        out["creator_key"].map(clean_blank)
        + "|"
        + out["dropped_date"].map(clean_blank)
        + "|"
        + out["lead_key"].map(clean_blank)
    )
    out = out.sort_values(["_natural_key", "_source_priority"])
    out = out.drop_duplicates(subset=["_natural_key"], keep="first")
    return out.drop(columns=["_source_priority", "_project_key", "_natural_key"])


def build_master_creator_lifecycle(
    matches: pd.DataFrame,
    classifications: pd.DataFrame,
    zendesk: pd.DataFrame,
    slack: pd.DataFrame,
    manual_overrides: pd.DataFrame | None = None,
    snowflake_dropped: pd.DataFrame | None = None,
    snowflake_returned: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the canonical creator lifecycle fact table.

    Dropped onboarding records are the grain: one row per dropped creator/site.
    Salesforce and Snowflake dropped rows define the lifecycle population; returning
    Salesforce, Snowflake, Zendesk, Slack, Creator Growth, and Salesloft signals
    enrich those lifecycle rows.
    """
    enriched = _attach_classifications(matches, classifications)
    enriched = link_zendesk(enriched, zendesk)
    enriched = link_slack(enriched, slack)

    dropped_date = pd.to_datetime(_series_or_default(enriched, "dropped_date"), errors="coerce")
    returned_date = pd.to_datetime(_series_or_default(enriched, "returning_returned_date"), errors="coerce")
    install_date = pd.to_datetime(_series_or_default(enriched, "returning_install_date"), errors="coerce")
    scheduled_install_date = pd.to_datetime(
        _series_or_default(enriched, "returning_scheduled_install_date"), errors="coerce"
    )
    returned_date = returned_date.fillna(install_date).fillna(scheduled_install_date)
    days_to_return = (returned_date - dropped_date).dt.days

    meeting_offered_zendesk = _bool_or_default(enriched, "meeting_offered_zendesk")
    meeting_offered_slack = _bool_or_default(enriched, "meeting_offered_slack")
    salesloft_meeting = _series_or_default(enriched, "first_salesloft_meeting_at").astype(str).str.len() > 0
    slack_event_count = _numeric_or_default(enriched, "slack_event_count")
    slack_intervention = slack_event_count > 0
    rescue_intervention = _bool_or_default(enriched, "rescue_intervention")

    cg_first_touch = pd.to_datetime(_series_or_default(enriched, "first_cg_touch_at"), errors="coerce")
    cg_escalated = cg_first_touch.notna() | rescue_intervention
    cg_days_from_drop = (cg_first_touch - dropped_date).dt.days

    install_completed = install_date.notna()
    reengaged = _bool_or_default(enriched, "reengaged")
    dropped_reason_category = _series_or_default(enriched, "dropped_reason_category").fillna("").astype(str).map(clean_blank)
    setup_category = pd.Series("", index=enriched.index)
    description = _series_or_default(enriched, "description").fillna("").astype(str)
    setup_category.loc[
        _setup_cancellation_mask(
            dropped_reason_category,
            description,
            _series_or_default(enriched, "cancelled_reason").fillna("").astype(str),
        )
    ] = "Set-up cancellation"
    setup_category.loc[_setup_cancellation_note_mask(description)] = "Cancelled Pre-onboarding"
    dropped_reason_category = dropped_reason_category.where(
        dropped_reason_category.map(_is_present), setup_category
    )
    dropped_reason_category.loc[_setup_cancellation_note_mask(description)] = "Cancelled Pre-onboarding"

    lifecycle = pd.DataFrame(index=enriched.index)
    lifecycle["lifecycle_creator_id"] = (
        _series_or_default(enriched, "salesforce_project_id")
        .where(_series_or_default(enriched, "salesforce_project_id").astype(str).str.len() > 0)
        .fillna(_series_or_default(enriched, "salesforce_account_id"))
        .where(lambda s: s.astype(str).str.len() > 0)
        .fillna(_series_or_default(enriched, "creator_key"))
    )
    lifecycle["creator_project_name"] = _series_or_default(enriched, "creator")
    lifecycle["lead_contact"] = _series_or_default(enriched, "lead_contact")
    lifecycle["company_name"] = _series_or_default(enriched, "company_name")
    lifecycle["domain"] = _series_or_default(enriched, "domain")
    lifecycle["site_id"] = _series_or_default(enriched, "site_id")
    lifecycle["salesforce_project_id"] = _series_or_default(enriched, "salesforce_project_id")
    lifecycle["salesforce_account_id"] = _series_or_default(enriched, "salesforce_account_id")
    lifecycle["salesforce_lead_id"] = _series_or_default(enriched, "salesforce_lead_id")
    lifecycle["creator_key"] = _series_or_default(enriched, "creator_key")
    lifecycle["lead_key"] = _series_or_default(enriched, "lead_key")
    lifecycle["vertical"] = _series_or_default(enriched, "vertical")
    lifecycle["service_level"] = _series_or_default(enriched, "service_level")
    lifecycle["previous_ad_network"] = _series_or_default(enriched, "previous_ad_network")
    lifecycle["onboarding_owner"] = _series_or_default(enriched, "owner")
    lifecycle["monthly_pageviews"] = _series_or_default(enriched, "monthly_pageview_estimate")
    lifecycle["dropped_status"] = _series_or_default(enriched, "status")
    lifecycle["dropped_date"] = format_date_for_output(dropped_date)
    lifecycle["returned_date"] = format_date_for_output(returned_date)
    lifecycle["scheduled_install_date"] = format_date_for_output(scheduled_install_date)
    lifecycle["install_date"] = format_date_for_output(install_date)
    lifecycle["days_to_return"] = _format_days(days_to_return)
    lifecycle["cancellation_reason"] = _series_or_default(enriched, "cancelled_reason")
    lifecycle["dropped_reason_category"] = dropped_reason_category
    lifecycle["raw_description"] = _series_or_default(enriched, "description")
    lifecycle["normalized_reason"] = dropped_reason_category.where(
        dropped_reason_category.map(_is_present),
        _series_or_default(enriched, "normalized_category").replace("", "Unknown"),
    )
    lifecycle["reason_confidence_score"] = _series_or_default(enriched, "confidence_score")
    lifecycle["reason_classification_method"] = _series_or_default(enriched, "classification_method")
    lifecycle["macro_cadence"] = _series_or_default(enriched, "macro_cadence", "None").replace({"": "None", "Unknown": "None"})
    lifecycle["zendesk_ticket_ids"] = _series_or_default(enriched, "zendesk_ticket_ids")
    lifecycle["zendesk_ticket_created_dates"] = _series_or_default(enriched, "zendesk_ticket_created_dates")
    lifecycle["zendesk_ticket_solved_dates"] = _series_or_default(enriched, "zendesk_ticket_solved_dates")
    lifecycle["zendesk_ticket_count"] = _numeric_or_default(enriched, "zendesk_ticket_count").astype(int)
    lifecycle["ticket_reopened"] = _bool_or_default(enriched, "ticket_reopened")
    lifecycle["cg_involvement"] = _cg_involvement_label(_series_or_default(enriched, "cg_involvement"))
    lifecycle["cg_effort"] = _series_or_default(enriched, "cg_effort")
    lifecycle["cg_escalation_status"] = cg_escalated
    lifecycle["cg_first_touch_at"] = _format_datetime(cg_first_touch)
    lifecycle["cg_days_from_drop"] = _format_days(cg_days_from_drop)
    lifecycle["onboarding_call_offered"] = meeting_offered_zendesk | meeting_offered_slack
    lifecycle["salesloft_meeting_detected"] = salesloft_meeting
    lifecycle["first_salesloft_meeting_at"] = _format_datetime(
        pd.to_datetime(_series_or_default(enriched, "first_salesloft_meeting_at"), errors="coerce")
    )
    lifecycle["slack_intervention_detected"] = slack_intervention
    lifecycle["slack_intervention_count"] = slack_event_count.astype(int)
    lifecycle["rescue_intervention_detected"] = rescue_intervention
    lifecycle["install_completed"] = install_completed
    lifecycle["converted"] = install_completed
    lifecycle["reengaged"] = reengaged
    lifecycle["outcome"] = _outcome_series(lifecycle)
    lifecycle["returning_project_name"] = _series_or_default(enriched, "returning_creator")
    lifecycle["returning_lead_contact"] = _series_or_default(enriched, "returning_lead_contact")
    lifecycle["returning_previous_ad_network"] = _series_or_default(enriched, "returning_previous_ad_network")
    lifecycle["returning_owner"] = _series_or_default(enriched, "returning_owner")
    lifecycle["returning_status"] = _series_or_default(enriched, "returning_status")
    lifecycle["match_method"] = _series_or_default(enriched, "match_method")
    lifecycle["match_score"] = _series_or_default(enriched, "match_score")
    lifecycle["source_salesforce_dropped"] = True
    lifecycle["source_salesforce_returning"] = reengaged
    lifecycle["source_snowflake"] = False

    lifecycle["cg_escalation_timing"] = lifecycle.apply(
        lambda row: derive_cg_timing(
            pd.Series(
                {
                    "cg_involvement": row.get("cg_involvement", ""),
                    "cg_effort": row.get("cg_effort", ""),
                    "first_cg_touch_at": row.get("cg_first_touch_at", ""),
                    "dropped_date": row.get("dropped_date", ""),
                }
            )
        ),
        axis=1,
    )

    for column in MASTER_COLUMNS:
        if column not in lifecycle.columns:
            lifecycle[column] = ""

    lifecycle = lifecycle[MASTER_COLUMNS]
    snowflake_lifecycle = _build_snowflake_lifecycle(
        snowflake_dropped if snowflake_dropped is not None else pd.DataFrame(),
        snowflake_returned if snowflake_returned is not None else pd.DataFrame(),
    )
    if not snowflake_lifecycle.empty:
        lifecycle = pd.concat([lifecycle, snowflake_lifecycle], ignore_index=True)
        lifecycle = _dedupe_lifecycle_rows(lifecycle)
    lifecycle = link_zendesk(lifecycle, zendesk)
    if manual_overrides is not None and not manual_overrides.empty:
        lifecycle = apply_manual_overrides(lifecycle, manual_overrides)
    lifecycle = _recalculate_lifecycle_flags(lifecycle)
    lifecycle = lifecycle[MASTER_COLUMNS]
    for column in lifecycle.select_dtypes(include=["object"]).columns:
        lifecycle[column] = lifecycle[column].map(clean_blank)
        lifecycle[column] = lifecycle[column].str.replace(r"\s+", " ", regex=True).str.strip()
    lifecycle["macro_cadence"] = lifecycle["macro_cadence"].replace("", "None")
    missing_reason = lifecycle["cancellation_reason"].str.lower().isin(
        {"", "dropped", "canceled", "cancelled", "prior site dropped status"}
    )
    lifecycle.loc[missing_reason, "cancellation_reason"] = "No reason captured"
    lifecycle["cg_involvement"] = _cg_involvement_label(lifecycle["cg_involvement"])
    lifecycle["outcome"] = _outcome_series(lifecycle)
    return lifecycle.sort_values(["dropped_date", "creator_project_name"], na_position="last")
