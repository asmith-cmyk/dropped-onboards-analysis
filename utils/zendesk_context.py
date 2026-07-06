from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from utils.io import clean_blank, coalesce
from utils.text import extract_domains, normalize_creator_name, normalize_text


DROPPED_CONTEXT_YEAR = 2026
TICKET_LOOKBACK_DAYS = 180
TICKET_LOOKAHEAD_DAYS = 30


TEXT_COLUMN_ALIASES = {
    "body": "conversation_text",
    "comment": "conversation_text",
    "comments": "conversation_text",
    "conversation": "conversation_text",
    "conversation_text": "conversation_text",
    "description": "conversation_text",
    "latest_comment": "conversation_text",
    "ticket_comments": "conversation_text",
    "zendesk_comments": "conversation_text",
    "ai_summary": "zendesk_summary",
    "native_summary": "zendesk_summary",
    "summary": "zendesk_summary",
    "ticket_summary": "zendesk_summary",
    "zendesk_ai_summary": "zendesk_summary",
    "zendesk_summary": "zendesk_summary",
}


BASE_COLUMN_ALIASES = {
    "id": "ticket_id",
    "ticket_id": "ticket_id",
    "ticket id": "ticket_id",
    "requester": "lead_contact",
    "requester name": "lead_contact",
    "lead_contact": "lead_contact",
    "creator": "creator",
    "project name": "creator",
    "site": "creator",
    "site_id": "site_id",
    "site id": "site_id",
    "domain": "domain",
    "url": "domain",
    "website": "domain",
    "subject": "subject",
    "ticket subject": "subject",
    "created": "created_at",
    "created at": "created_at",
    "created_at": "created_at",
    "solved": "solved_at",
    "solved at": "solved_at",
    "solved_at": "solved_at",
    "updated": "updated_at",
    "updated at": "updated_at",
    "updated_at": "updated_at",
    "tags": "tags",
    "ticket tags": "tags",
    "sentiment": "zendesk_sentiment",
    "zendesk_sentiment": "zendesk_sentiment",
    "milestone": "milestone_signal",
    "milestone completed": "milestone_signal",
    "milestone_signal": "milestone_signal",
}


THEME_RULES: dict[str, dict[str, list[str]]] = {
    "Cancellation & Ghosting": {
        "Ghosting / no response": [
            "no response",
            "unresponsive",
            "havent heard",
            "haven t heard",
            "didnt hear",
            "didn t hear",
            "ghost",
            "never engaged",
            "stopped responding",
            "last attempt",
        ],
        "Considering or chose another provider": [
            "adsense",
            "ezoic",
            "freestar",
            "media vine",
            "mediavine",
            "monumetric",
            "provider",
            "competitor",
            "current ad provider",
            "another ad network",
        ],
        "Revenue or RPM concern": [
            "rpm",
            "cpm",
            "earnings",
            "revenue",
            "rev share",
            "revenue share",
            "guarantee",
            "low rate",
        ],
        "Ad layout or content concern": [
            "ad layout",
            "ad density",
            "ads",
            "content control",
            "content controls",
            "brand safety",
            "design",
        ],
        "Eligibility or verification blocker": [
            "mcm",
            "idv",
            "verification",
            "verify",
            "rejected",
            "eligible",
            "invalid traffic",
            "fraud",
        ],
        "Timing or personal constraint": [
            "busy",
            "later",
            "pause",
            "paused",
            "hold",
            "bandwidth",
            "personal",
            "family",
            "health",
            "not ready",
        ],
        "Technical or setup blocker": [
            "dns",
            "cname",
            "plugin",
            "implementation",
            "install",
            "setup",
            "site speed",
            "core web vitals",
            "technical",
        ],
    },
    "Communication & Sentiment": {
        "Negative sentiment": [
            "frustrated",
            "upset",
            "concerned",
            "disappointed",
            "hate",
            "hated",
            "confusing",
            "confused",
            "not happy",
            "poor",
        ],
        "Positive or interested sentiment": [
            "excited",
            "interested",
            "sounds good",
            "thank you",
            "thanks",
            "helpful",
            "appreciate",
        ],
        "Repeated follow-up pattern": [
            "follow up",
            "following up",
            "checking in",
            "circle back",
            "bump",
            "last attempt",
        ],
        "Questions about revenue": ["rpm", "cpm", "earnings", "revenue", "guarantee", "share"],
        "Questions about ads or layout": ["ad layout", "ads", "ad density", "placement", "sticky"],
        "Questions about timeline": ["timeline", "when", "how long", "install date", "go live"],
        "Questions about technical setup": ["dns", "cname", "plugin", "mcm", "idv", "verification"],
    },
    "Drop-off & Community Growth": {
        "Accepted but no engagement": ["accepted", "application accepted", "never engaged", "no response"],
        "MCM or IDV stage": ["mcm", "idv", "verification", "google ad manager"],
        "Ad layout review stage": ["ad layout", "layout review", "placement", "ad density"],
        "Install or technical setup stage": ["install", "implementation", "setup", "dns", "cname", "plugin"],
        "Checkup or post-install stage": ["checkup", "post install", "active", "go live"],
        "Community Growth involved": [
            "creator growth",
            "community growth",
            "cg handoff",
            "cg escalation",
            "passed to cg",
            "escalated to cg",
        ],
    },
}


MILESTONE_ORDER = [
    ("Checkup / post-install", ["checkup", "post install", "active", "go live"]),
    ("Install / technical setup", ["install", "implementation", "setup", "dns", "cname", "plugin"]),
    ("Ad layout review", ["ad layout", "layout review", "placement", "ad density"]),
    ("MCM / IDV", ["mcm", "idv", "verification", "google ad manager"]),
    ("Application accepted", ["accepted", "application accepted"]),
]


def _canonical_column(value: object) -> str:
    return normalize_text(value).replace(" ", "_")


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    alias_map = {**BASE_COLUMN_ALIASES, **TEXT_COLUMN_ALIASES}
    for column in df.columns:
        key = normalize_text(column)
        key_with_underscores = _canonical_column(column)
        rename[column] = alias_map.get(key, alias_map.get(key_with_underscores, column))
    return df.rename(columns=rename).copy()


def _join_unique(values: list[Any] | pd.Series, separator: str = "; ") -> str:
    items: list[str] = []
    for value in values:
        cleaned = clean_blank(value)
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return separator.join(items)


def _text_blob(row: pd.Series) -> str:
    return " ".join(
        clean_blank(row.get(column, ""))
        for column in ("subject", "tags", "conversation_text", "zendesk_summary", "milestone_signal")
        if clean_blank(row.get(column, ""))
    )


def _domain_key(*values: object) -> str:
    domains = extract_domains(*values)
    return domains[0] if domains else ""


def normalize_zendesk_context(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "ticket_id",
        "creator",
        "lead_contact",
        "site_id",
        "domain",
        "subject",
        "created_at",
        "updated_at",
        "solved_at",
        "tags",
        "conversation_text",
        "zendesk_summary",
        "zendesk_sentiment",
        "milestone_signal",
        "creator_key",
        "lead_key",
        "domain_key",
        "context_text",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    out = _rename_columns(df)
    for column in columns:
        if column not in out.columns:
            out[column] = ""

    out["creator_key"] = out["creator"].map(normalize_creator_name)
    out["lead_key"] = out["lead_contact"].map(normalize_creator_name)
    out["domain_key"] = out.apply(lambda row: _domain_key(row.get("domain", ""), row.get("conversation_text", "")), axis=1)
    out["context_text"] = out.apply(_text_blob, axis=1).map(normalize_text)
    return out[columns]


def _ticket_dates(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NaT, index=df.index)
    return pd.to_datetime(df[column].map(clean_blank), errors="coerce")


def _filter_ticket_window(related: pd.DataFrame, dropped_date: object) -> pd.DataFrame:
    dropped_at = pd.to_datetime(clean_blank(dropped_date), errors="coerce")
    if related.empty or pd.isna(dropped_at):
        return related

    created = _ticket_dates(related, "created_at")
    updated = _ticket_dates(related, "updated_at")
    solved = _ticket_dates(related, "solved_at")
    has_dates = created.notna() | updated.notna() | solved.notna()
    if not has_dates.any():
        return related

    start = created.fillna(updated).fillna(solved)
    end = solved.fillna(updated).fillna(created)
    in_window = (
        ~has_dates
        | (
            (start <= dropped_at + pd.Timedelta(days=TICKET_LOOKAHEAD_DAYS))
            & (end >= dropped_at - pd.Timedelta(days=TICKET_LOOKBACK_DAYS))
        )
    )
    return related.loc[in_window].copy()


def _related_tickets(row: pd.Series, zendesk: pd.DataFrame) -> pd.DataFrame:
    if zendesk.empty:
        return zendesk

    site_id = clean_blank(row.get("site_id", ""))
    domain_key = _domain_key(row.get("domain", ""))
    creator_key = clean_blank(row.get("creator_key", ""))
    lead_key = clean_blank(row.get("lead_key", ""))

    mask = pd.Series(False, index=zendesk.index)
    if site_id:
        mask = mask | zendesk["site_id"].map(clean_blank).eq(site_id)
    if domain_key:
        mask = mask | zendesk["domain_key"].eq(domain_key)
    if creator_key:
        mask = mask | zendesk["creator_key"].eq(creator_key)
    if lead_key:
        mask = mask | zendesk["lead_key"].eq(lead_key)

    return _filter_ticket_window(zendesk.loc[mask].copy(), row.get("dropped_date", ""))


def _matched_themes(text: str, area: str) -> list[str]:
    matches: list[str] = []
    for theme, terms in THEME_RULES[area].items():
        normalized_terms = [normalize_text(term) for term in terms]
        if any(term and term in text for term in normalized_terms):
            matches.append(theme)
    return matches


def _sentiment(related: pd.DataFrame, text: str) -> str:
    provided = _join_unique(related.get("zendesk_sentiment", pd.Series(dtype=str)).tolist())
    if provided:
        return provided
    if any(term in text for term in ("frustrated", "upset", "disappointed", "not happy", "hate", "hated", "poor")):
        return "Negative"
    if any(term in text for term in ("excited", "interested", "sounds good", "thank you", "thanks", "appreciate")):
        return "Positive"
    if text:
        return "Neutral / unclear"
    return ""


def _milestone_stage(text: str, related: pd.DataFrame) -> str:
    provided = _join_unique(related.get("milestone_signal", pd.Series(dtype=str)).tolist())
    if provided:
        return provided
    for label, terms in MILESTONE_ORDER:
        if any(normalize_text(term) in text for term in terms):
            return label
    return ""


def _summary(
    row: pd.Series,
    native_summary: str,
    themes: list[str],
    sentiment: str,
    milestone: str,
    has_context: bool,
) -> str:
    if native_summary:
        return native_summary
    if not themes and not sentiment and not milestone:
        if has_context:
            return "Zendesk context available; no matching theme detected yet."
        return "No Zendesk context available yet."

    parts = []
    if themes:
        parts.append(f"Signals: {', '.join(themes[:4])}")
    if sentiment:
        parts.append(f"Sentiment: {sentiment}")
    if milestone:
        parts.append(f"Likely stuck point: {milestone}")
    if clean_blank(row.get("cg_involvement", "")):
        parts.append(f"CG: {clean_blank(row.get('cg_involvement'))}")
    return ". ".join(parts) + "."


def _top_values(values: pd.Series, limit: int = 5) -> str:
    counts = Counter(clean_blank(value) or "N/A" for value in values)
    return "; ".join(f"{value} ({count})" for value, count in counts.most_common(limit))


def build_zendesk_context_outputs(
    master: pd.DataFrame,
    zendesk_context: pd.DataFrame | None = None,
    year: int = DROPPED_CONTEXT_YEAR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = normalize_zendesk_context(zendesk_context if zendesk_context is not None else pd.DataFrame())
    working = master.copy()
    dropped_at = pd.to_datetime(working.get("dropped_date", ""), errors="coerce")
    dropped_in_year = dropped_at.dt.year.eq(year)
    dropped = working.loc[dropped_in_year].copy()

    rows: list[dict[str, Any]] = []
    for _, row in dropped.iterrows():
        related = _related_tickets(row, z)
        context_text = " ".join(related.get("context_text", pd.Series(dtype=str)).map(clean_blank))
        native_summary = _join_unique(related.get("zendesk_summary", pd.Series(dtype=str)).tolist())
        cancellation_themes = _matched_themes(context_text, "Cancellation & Ghosting")
        communication_themes = _matched_themes(context_text, "Communication & Sentiment")
        dropoff_themes = _matched_themes(context_text, "Drop-off & Community Growth")
        sentiment = _sentiment(related, context_text)
        milestone = _milestone_stage(context_text, related)
        all_themes = cancellation_themes + communication_themes + dropoff_themes

        rows.append(
            {
                "site_id": row.get("site_id", ""),
                "site_name": row.get("creator_project_name", ""),
                "creator_name": coalesce(row.get("lead_contact", ""), row.get("company_name", "")),
                "domain": row.get("domain", ""),
                "service_level": row.get("service_level", ""),
                "vertical": row.get("vertical", ""),
                "previous_ad_network": row.get("previous_ad_network", ""),
                "onboarding_owner": row.get("onboarding_owner", ""),
                "outcome": row.get("outcome", ""),
                "dropped_date": row.get("dropped_date", ""),
                "dropped_reason_category": row.get("dropped_reason_category", ""),
                "dropped_reason": row.get("dropped_reason", ""),
                "zendesk_context_available": not related.empty,
                "zendesk_ticket_count": len(related),
                "zendesk_ticket_ids": _join_unique(related.get("ticket_id", pd.Series(dtype=str)).tolist()),
                "zendesk_summary": native_summary,
                "cancellation_ghosting_themes": _join_unique(cancellation_themes),
                "communication_themes": _join_unique(communication_themes),
                "dropoff_cg_themes": _join_unique(dropoff_themes),
                "sentiment": sentiment,
                "milestone_stage": milestone,
                "cg_involvement": row.get("cg_involvement", ""),
                "cg_escalation_status": row.get("cg_escalation_status", ""),
                "cg_first_touch_at": row.get("cg_first_touch_at", ""),
                "cg_days_from_drop": row.get("cg_days_from_drop", ""),
                "context_summary": _summary(row, native_summary, all_themes, sentiment, milestone, not related.empty),
            }
        )

    site_context = pd.DataFrame(rows)
    summary_rows: list[dict[str, Any]] = []
    if not site_context.empty:
        for area, column in (
            ("Cancellation & Ghosting", "cancellation_ghosting_themes"),
            ("Communication & Sentiment", "communication_themes"),
            ("Drop-off & Community Growth", "dropoff_cg_themes"),
        ):
            exploded = site_context.assign(theme=site_context[column].str.split("; ")).explode("theme")
            exploded["theme"] = exploded["theme"].map(clean_blank)
            has_context = exploded["zendesk_context_available"].astype(bool)
            exploded.loc[exploded["theme"].eq("") & has_context, "theme"] = "Zendesk context available - no matching theme"
            exploded.loc[exploded["theme"].eq(""), "theme"] = "No Zendesk context available"
            for theme, group in exploded.groupby("theme", dropna=False):
                summary_rows.append(
                    {
                        "analysis_area": area,
                        "theme": theme,
                        "site_count": len(group),
                        "dropped_count": int(group["outcome"].eq("Dropped").sum()),
                        "returned_count": int(group["outcome"].eq("Returned").sum()),
                        "onboarding_count": int(group["outcome"].eq("Onboarding").sum()),
                        "with_zendesk_context": int(group["zendesk_context_available"].astype(bool).sum()),
                        "top_dropped_reason_categories": _top_values(group["dropped_reason_category"]),
                        "top_dropped_reasons": _top_values(group["dropped_reason"]),
                    }
                )

    theme_summary = pd.DataFrame(summary_rows)
    return site_context, theme_summary
