from __future__ import annotations

import pandas as pd

from utils.analysis import bool_series, derive_cg_timing, link_slack, link_zendesk
from utils.columns import format_date_for_output
from utils.io import clean_blank
from utils.text import normalize_creator_name


MASTER_COLUMNS = [
    "lifecycle_creator_id",
    "creator_project_name",
    "lead_contact",
    "domain",
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
    "dropped_date",
    "returned_date",
    "scheduled_install_date",
    "install_date",
    "days_to_return",
    "cancellation_reason",
    "raw_description",
    "normalized_reason",
    "reason_confidence_score",
    "reason_classification_method",
    "macro_cadence",
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
    "match_method",
    "match_score",
    "source_salesforce_dropped",
    "source_salesforce_returning",
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


def _is_present(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return clean_blank(value) != ""


def _coerce_bool(value: object) -> bool:
    return clean_blank(value).lower() in {"1", "true", "yes", "y", "booked", "installed", "converted"}


def _outcome_series(df: pd.DataFrame) -> pd.Series:
    installed = bool_series(_series_or_default(df, "install_completed", False), index=df.index)
    reengaged = bool_series(_series_or_default(df, "reengaged", False), index=df.index)
    cadence = _series_or_default(df, "macro_cadence", "None").fillna("").astype(str).str.strip()
    outcome = pd.Series("Dropped", index=df.index)
    outcome.loc[reengaged] = "Returned"
    outcome.loc[installed & (cadence == "3/5/7")] = "Re-engaged & Installed"
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
    ) | reengaged
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


def build_master_creator_lifecycle(
    matches: pd.DataFrame,
    classifications: pd.DataFrame,
    zendesk: pd.DataFrame,
    slack: pd.DataFrame,
    manual_overrides: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the canonical creator lifecycle fact table.

    Salesforce dropped records are the grain: one row per dropped onboarding creator.
    Returning Salesforce, Zendesk, and Slack data are enrichments on that lifecycle row.
    """
    if matches.empty:
        return pd.DataFrame(columns=MASTER_COLUMNS)

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
    lifecycle["domain"] = _series_or_default(enriched, "domain")
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
    lifecycle["dropped_date"] = format_date_for_output(dropped_date)
    lifecycle["returned_date"] = format_date_for_output(returned_date)
    lifecycle["scheduled_install_date"] = format_date_for_output(scheduled_install_date)
    lifecycle["install_date"] = format_date_for_output(install_date)
    lifecycle["days_to_return"] = _format_days(days_to_return)
    lifecycle["cancellation_reason"] = _series_or_default(enriched, "cancelled_reason")
    lifecycle["raw_description"] = _series_or_default(enriched, "description")
    lifecycle["normalized_reason"] = _series_or_default(enriched, "normalized_category").replace("", "Unknown")
    lifecycle["reason_confidence_score"] = _series_or_default(enriched, "confidence_score")
    lifecycle["reason_classification_method"] = _series_or_default(enriched, "classification_method")
    lifecycle["macro_cadence"] = _series_or_default(enriched, "macro_cadence", "None").replace({"": "None", "Unknown": "None"})
    lifecycle["zendesk_ticket_count"] = _numeric_or_default(enriched, "zendesk_ticket_count").astype(int)
    lifecycle["ticket_reopened"] = _bool_or_default(enriched, "ticket_reopened")
    lifecycle["cg_involvement"] = _series_or_default(enriched, "cg_involvement")
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
    lifecycle["match_method"] = _series_or_default(enriched, "match_method")
    lifecycle["match_score"] = _series_or_default(enriched, "match_score")
    lifecycle["source_salesforce_dropped"] = True
    lifecycle["source_salesforce_returning"] = reengaged

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
    if manual_overrides is not None and not manual_overrides.empty:
        lifecycle = apply_manual_overrides(lifecycle, manual_overrides)
    lifecycle = _recalculate_lifecycle_flags(lifecycle)
    lifecycle = lifecycle[MASTER_COLUMNS]
    for column in lifecycle.select_dtypes(include=["object"]).columns:
        lifecycle[column] = lifecycle[column].map(clean_blank)
        lifecycle[column] = lifecycle[column].str.replace(r"\s+", " ", regex=True).str.strip()
    lifecycle["macro_cadence"] = lifecycle["macro_cadence"].replace("", "None")
    lifecycle["cg_involvement"] = lifecycle["cg_involvement"].replace("", "None")
    lifecycle["outcome"] = _outcome_series(lifecycle)
    return lifecycle.sort_values(["dropped_date", "creator_project_name"], na_position="last")
