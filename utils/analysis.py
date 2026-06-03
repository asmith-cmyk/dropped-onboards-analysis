from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from utils.columns import format_date_for_output
from utils.io import clean_blank
from utils.text import normalize_creator_name, normalize_text
from utils.zendesk_client import infer_macro_cadence


def as_bool(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=bool)
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna("").astype(str).str.strip().str.lower().isin(
        {"1", "true", "yes", "y", "booked", "installed", "converted"}
    )


def bool_series(series: pd.Series | bool | object, index=None) -> pd.Series:
    if not isinstance(series, pd.Series):
        return pd.Series(series, index=index)
    if series.dtype == bool:
        return series.fillna(False)
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "yes", "y", "booked", "installed", "converted"})


def cadence_has_days(value: object, required_days: set[str]) -> bool:
    days = set(re.findall(r"\b(?:3|5|7|10)\b", clean_blank(value)))
    return required_days.issubset(days)


def cadence_has_any_days(value: object, target_days: set[str]) -> bool:
    days = set(re.findall(r"\b(?:3|5|7|10)\b", clean_blank(value)))
    return bool(days.intersection(target_days))


def has_cadence(value: object) -> bool:
    cadence = clean_blank(value)
    return cadence != "" and cadence.lower() not in {"none", "unknown"}


def derive_cg_timing(row: pd.Series) -> str:
    involvement = normalize_text(row.get("cg_involvement", ""))
    event_at = pd.to_datetime(row.get("first_cg_touch_at", ""), errors="coerce")
    dropped_at = pd.to_datetime(row.get("dropped_date", ""), errors="coerce")
    if "non assisted" in involvement or "not assisted" in involvement or involvement in {"none", "no", ""}:
        if pd.isna(event_at):
            return "No CG involvement"
    if pd.notna(event_at) and pd.notna(dropped_at):
        days = (event_at - dropped_at).days
        if days <= 7:
            return "Early CG involvement"
        return "Late CG involvement"
    if ("assisted" in involvement and "not assisted" not in involvement and "non assisted" not in involvement) or clean_blank(row.get("cg_effort")):
        return "Assisted"
    return "No CG involvement"


def link_zendesk(matches: pd.DataFrame, zendesk: pd.DataFrame) -> pd.DataFrame:
    out = matches.copy()
    for column, default in (
        ("macro_cadence", "None"),
        ("meeting_offered_zendesk", False),
        ("ticket_reopened", False),
        ("zendesk_ticket_count", 0),
    ):
        if column not in out.columns:
            out[column] = default

    if zendesk.empty:
        return out

    z = zendesk.copy()
    z["creator_key"] = z["creator_key"].fillna("")
    z["lead_key"] = z["lead_key"].fillna("")
    for idx, row in out.iterrows():
        creator_key = row.get("creator_key", "")
        lead_key = row.get("lead_key", "")
        related = z[(z["creator_key"] == creator_key) & (z["creator_key"] != "")]
        if related.empty and lead_key:
            related = z[(z["lead_key"] == lead_key) & (z["lead_key"] != "")]
        if related.empty:
            continue
        out.at[idx, "zendesk_ticket_count"] = len(related)
        macro_flags = {
            column: bool(as_bool(related[column]).any()) if column in related.columns else False
            for column in ("macro_day_3", "macro_day_5", "macro_day_7", "macro_day_10")
        }
        out.at[idx, "macro_cadence"] = infer_macro_cadence(pd.Series(macro_flags))
        out.at[idx, "meeting_offered_zendesk"] = bool(as_bool(related["meeting_offered"]).any())
        out.at[idx, "ticket_reopened"] = bool(as_bool(related["ticket_reopened"]).any())
    return out


def link_slack(matches: pd.DataFrame, slack: pd.DataFrame) -> pd.DataFrame:
    out = matches.copy()
    for column, default in (
        ("slack_event_count", 0),
        ("first_cg_touch_at", ""),
        ("first_salesloft_meeting_at", ""),
        ("meeting_offered_slack", False),
        ("rescue_intervention", False),
    ):
        if column not in out.columns:
            out[column] = default

    if slack.empty:
        return out

    s = slack.copy()
    s["search_text"] = (s.get("text", "").astype(str) + " " + s.get("channel_name", "").astype(str)).map(normalize_text)
    s["event_at"] = pd.to_datetime(s.get("event_at", ""), errors="coerce")
    for idx, row in out.iterrows():
        terms = [
            normalize_creator_name(row.get("creator", "")),
            normalize_creator_name(row.get("lead_contact", "")),
            normalize_creator_name(row.get("returning_creator", "")),
            normalize_creator_name(row.get("returning_lead_contact", "")),
        ]
        terms = [term for term in terms if len(term) >= 4]
        if not terms:
            continue
        mask = pd.Series(False, index=s.index)
        for term in terms:
            mask = mask | s["search_text"].str.contains(term, regex=False, na=False)
        related = s[mask]
        if related.empty:
            continue
        out.at[idx, "slack_event_count"] = len(related)
        cg = related[related["event_type"].isin(["creator_growth_escalation", "rescue_intervention"])]
        if not cg.empty:
            first = cg["event_at"].dropna().min()
            out.at[idx, "first_cg_touch_at"] = first.isoformat() if pd.notna(first) else ""
        meetings = related[related["event_type"] == "salesloft_meeting"]
        if not meetings.empty:
            first = meetings["event_at"].dropna().min()
            out.at[idx, "first_salesloft_meeting_at"] = first.isoformat() if pd.notna(first) else ""
        out.at[idx, "meeting_offered_slack"] = bool(
            related["event_type"].isin(["onboarding_call_offer", "salesloft_meeting"]).any()
        )
        out.at[idx, "rescue_intervention"] = bool((related["event_type"] == "rescue_intervention").any())
    return out


def build_reengagement_output(timeline: pd.DataFrame) -> pd.DataFrame:
    master = timeline.copy()
    output = pd.DataFrame(index=master.index)
    output["Creator"] = master.get("creator_project_name", "")
    output["Vertical"] = master.get("vertical", "")
    output["Service Level"] = master.get("service_level", "")
    output["Previous Ad Network"] = master.get("previous_ad_network", "")
    output["Dropped Date"] = master.get("dropped_date", "")
    output["Returned Date"] = master.get("returned_date", "")
    output["Days_to_Return"] = master.get("days_to_return", "")
    output["CG Involvement"] = master.get("cg_involvement", "")
    output["Macro Cadence"] = master.get("macro_cadence", "None")
    output["Meeting Offered"] = bool_series(master.get("onboarding_call_offered", False), index=master.index)
    output["Re-engaged"] = bool_series(master.get("reengaged", False), index=master.index)
    output["Installed"] = bool_series(master.get("install_completed", False), index=master.index)
    output["Converted"] = bool_series(master.get("converted", False), index=master.index)
    output["Outcome"] = master.get("outcome", "")
    output["Onboarding Owner"] = master.get("onboarding_owner", "")
    output["Lead Contact"] = master.get("lead_contact", "")
    output["Match Method"] = master.get("match_method", "")
    output["Match Score"] = master.get("match_score", "")

    ordered = [
        "Creator",
        "Vertical",
        "Service Level",
        "Previous Ad Network",
        "Dropped Date",
        "Returned Date",
        "Days_to_Return",
        "CG Involvement",
        "Macro Cadence",
        "Meeting Offered",
        "Re-engaged",
        "Installed",
        "Converted",
        "Outcome",
        "Onboarding Owner",
        "Lead Contact",
        "Match Method",
        "Match Score",
    ]
    return output[ordered]


def cohort_summary(df: pd.DataFrame, cohort_type: str, column: str) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame()
    working = df.copy()
    fallback = "None" if column == "macro_cadence" else "Unknown"
    working[column] = working[column].replace("", fallback).fillna(fallback)
    rows = []
    for value, group in working.groupby(column, dropna=False):
        total = len(group)
        reengaged = int(bool_series(group["reengaged"]).sum()) if "reengaged" in group else 0
        installed = int(bool_series(group["install_completed"]).sum()) if "install_completed" in group else 0
        converted = int(bool_series(group["converted"]).sum()) if "converted" in group else 0
        days = pd.to_numeric(group.get("days_to_return", pd.Series(dtype=float)), errors="coerce")
        rows.append(
            {
                "cohort_type": cohort_type,
                "cohort_value": value or fallback,
                "total_dropped": total,
                "reengaged_count": reengaged,
                "reengagement_rate": round(reengaged / total, 4) if total else 0,
                "installed_count": installed,
                "install_rate": round(installed / total, 4) if total else 0,
                "converted_count": converted,
                "conversion_rate": round(converted / total, 4) if total else 0,
                "median_days_to_return": round(days.dropna().median(), 1) if days.notna().any() else "",
            }
        )
    return pd.DataFrame(rows)


def build_cohort_analysis(reengaged_output: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("Vertical", "vertical"),
        ("Service Level", "service_level"),
        ("Previous Ad Network", "previous_ad_network"),
        ("Creator Growth", "cg_involvement"),
        ("Macro Cadence", "macro_cadence"),
        ("Onboarding Owner", "onboarding_owner"),
    ]
    frames = [cohort_summary(reengaged_output, label, column) for label, column in specs]
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_cancellation_reason_analysis(
    reengaged_output: pd.DataFrame, classifications: pd.DataFrame | None = None
) -> pd.DataFrame:
    master = reengaged_output.copy()
    if master.empty or "normalized_reason" not in master.columns:
        return pd.DataFrame()
    master["normalized_reason"] = master["normalized_reason"].replace("", "Unknown").fillna("Unknown")
    if "dropped_reason_category" in master.columns:
        reason_category = master["dropped_reason_category"].replace("", pd.NA)
        master["_reason_analysis_category"] = reason_category.fillna(master["normalized_reason"]).fillna("Unknown")
    else:
        master["_reason_analysis_category"] = master["normalized_reason"]
    rows = []
    total_all = len(master)
    for category, group in master.groupby("_reason_analysis_category", dropna=False):
        total = len(group)
        reengaged = int(bool_series(group["reengaged"]).sum())
        installed = int(bool_series(group["install_completed"]).sum())
        rows.append(
            {
                "normalized_category": category,
                "count": total,
                "pct_of_dropped": round(total / total_all, 4) if total_all else 0,
                "reengaged_count": reengaged,
                "reengagement_rate": round(reengaged / total, 4) if total else 0,
                "installed_count": installed,
                "install_rate": round(installed / total, 4) if total else 0,
                "avg_confidence_score": round(
                    pd.to_numeric(group["reason_confidence_score"], errors="coerce").dropna().mean(),
                    3,
                )
                if "reason_confidence_score" in group and group["reason_confidence_score"].notna().any()
                else "",
            }
        )
    return pd.DataFrame(rows).sort_values(["count"], ascending=False)


def build_creator_growth_analysis(reengaged_output: pd.DataFrame) -> pd.DataFrame:
    return cohort_summary(reengaged_output, "Creator Growth", "cg_involvement")


def build_rise_creator_analysis(reengaged_output: pd.DataFrame) -> pd.DataFrame:
    rise = reengaged_output[
        reengaged_output["service_level"].fillna("").str.lower().str.contains("rise", na=False)
    ].copy()
    if rise.empty:
        return pd.DataFrame(
            columns=[
                "segment",
                "total_rise_creators",
                "reengaged_count",
                "reengagement_rate",
                "installed_count",
                "install_rate",
                "converted_count",
                "conversion_rate",
            ]
        )
    segments = {
        "All Rise": rise,
        "Onboarding Call Offered": rise[bool_series(rise["onboarding_call_offered"])],
        "No Onboarding Call Offered": rise[~bool_series(rise["onboarding_call_offered"])],
        "Salesloft Meeting Detected": rise[bool_series(rise["salesloft_meeting_detected"])],
        "Slack Intervention Detected": rise[bool_series(rise["slack_intervention_detected"])],
    }
    rows = []
    for segment, group in segments.items():
        total = len(group)
        reengaged = int(bool_series(group["reengaged"]).sum())
        installed = int(bool_series(group["install_completed"]).sum())
        converted = int(bool_series(group["converted"]).sum())
        rows.append(
            {
                "segment": segment,
                "total_rise_creators": total,
                "reengaged_count": reengaged,
                "reengagement_rate": round(reengaged / total, 4) if total else 0,
                "installed_count": installed,
                "install_rate": round(installed / total, 4) if total else 0,
                "converted_count": converted,
                "conversion_rate": round(converted / total, 4) if total else 0,
            }
        )
    return pd.DataFrame(rows)


def write_executive_summary(
    output_path: Path,
    reengaged_output: pd.DataFrame,
    cohort_analysis: pd.DataFrame,
    cg_analysis: pd.DataFrame,
    rise_analysis: pd.DataFrame,
) -> None:
    total = len(reengaged_output)
    reengaged = int(bool_series(reengaged_output["reengaged"]).sum()) if total else 0
    installed = int(bool_series(reengaged_output["install_completed"]).sum()) if total else 0
    cadence = reengaged_output.get("macro_cadence", pd.Series("", index=reengaged_output.index))
    returned_with_cadence = int(
        (
            bool_series(reengaged_output.get("reengaged", False), index=reengaged_output.index)
            & cadence.map(lambda value: cadence_has_any_days(value, {"3", "5", "7"}))
        ).sum()
    ) if total else 0
    rate = reengaged / total if total else 0
    install_rate = installed / total if total else 0
    median_days = pd.to_numeric(reengaged_output["days_to_return"], errors="coerce").dropna().median()

    if cohort_analysis.empty:
        top_cohorts = pd.DataFrame()
    else:
        top_cohorts = cohort_analysis.sort_values(
            ["reengagement_rate", "total_dropped"], ascending=[False, False]
        ).head(8)

    lines = [
        "# Onboarding Lifecycle Executive Summary",
        "",
        f"Generated from the master lifecycle dataset with {total} dropped onboarding creators/sites and {reengaged} returned creators/sites.",
        "",
        "## Headline Metrics",
        "",
        f"- Re-engagement rate: {rate:.1%}",
        f"- Install/conversion rate among dropped creators: {install_rate:.1%}",
        f"- Median days to return: {median_days:.1f}" if pd.notna(median_days) else "- Median days to return: unavailable",
        f"- Returned after 3, 5, or 7 day follow up cadence: {returned_with_cadence}/{total}",
        "",
        "## Strongest Cohorts",
        "",
    ]
    if top_cohorts.empty:
        lines.append("- No cohort data available yet.")
    else:
        for _, row in top_cohorts.iterrows():
            lines.append(
                f"- {row['cohort_type']} = {row['cohort_value']}: "
                f"{row['reengagement_rate']:.1%} re-engagement "
                f"({int(row['reengaged_count'])}/{int(row['total_dropped'])})."
            )

    lines.extend(["", "## Creator Growth", ""])
    if cg_analysis.empty:
        lines.append("- Creator Growth involvement could not be assessed from available data.")
    else:
        for _, row in cg_analysis.iterrows():
            lines.append(
                f"- {row['cohort_value']}: {row['reengagement_rate']:.1%} re-engagement "
                f"across {int(row['total_dropped'])} creators."
            )

    lines.extend(["", "## Rise Creators", ""])
    if rise_analysis.empty:
        lines.append("- No Rise creators were present in the current dropped cohort.")
    else:
        for _, row in rise_analysis.iterrows():
            lines.append(
                f"- {row['segment']}: {row['reengagement_rate']:.1%} re-engagement "
                f"and {row['install_rate']:.1%} install rate."
            )

    lines.extend(
        [
            "",
            "## Data Notes",
            "",
            "- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.",
            "- Salesforce dropped records and Snowflake Salesforce Onboarding project records define the table grain: one row per dropped onboarding creator/site.",
            "- Returning Salesforce, Snowflake returned-site cohorts, Zendesk, Slack, Creator Growth, and Salesloft signals enrich that lifecycle row.",
            "- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.",
            "- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
