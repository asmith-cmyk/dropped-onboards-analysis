from __future__ import annotations

import re
from typing import Iterable

from utils.io import clean_blank


EVERYTHING_ELSE_REASON = "Everything Else"

APPROVED_DROPPED_REASON_BUCKETS = [
    "Account manager",
    "Ad content/controls",
    "AI Content",
    "Brand safety",
    "Cancelled pre-onboarding",
    "Chose another provider",
    "Core Web Vitals",
    "Dashboard/More data",
    "Design concerns",
    "Disappointed in RPM Guarantee",
    "Expanded Solutions related",
    "Failed verification",
    "Failure to complete MCM IDV",
    "Fraud traffic",
    "Fraudulent traffic detected",
    "Google Terminated MCM Account",
    "Identity Concerns",
    "Loyalty Bonus",
    "Low RPM/CPM",
    "Making changes / Vague",
    "Never engaged",
    "New owner did not want to stay with AdThrive",
    "No Longer Eligible For Transfer",
    "No reason / Vague",
    "Non-responsive",
    "Other",
    "Other revenue sources",
    "Ownership/MCM",
    "Personal Reasons",
    "Poor user experience",
    "Refused ad layout",
    "Refused to share ad performance",
    "Rejected by MCM",
    "Retiring site",
    "Revenue Share",
    "RPM too high",
    "RPM/CPM comparison",
    "SEO/Pageviews down",
    "Single page application",
    "Site performance",
    "Staying with Current ad provider",
    "Stolen content",
    "Stuck in long-term contract",
    "Testing competitor",
]

APPROVED_DROPPED_REASONS = APPROVED_DROPPED_REASON_BUCKETS + [EVERYTHING_ELSE_REASON]


def reason_key(value: object) -> str:
    text = clean_blank(value).lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _alias_pairs() -> Iterable[tuple[str, str]]:
    for reason in APPROVED_DROPPED_REASON_BUCKETS:
        yield reason, reason

    yield "Set-up cancellation", "Cancelled pre-onboarding"
    yield "Setup cancellation", "Cancelled pre-onboarding"
    yield "Setup cancelled", "Cancelled pre-onboarding"
    yield "Canceled pre-onboarding", "Cancelled pre-onboarding"
    yield "Cancelled pre onboarding", "Cancelled pre-onboarding"
    yield "Canceled pre onboarding", "Cancelled pre-onboarding"
    yield "No reason/vague", "No reason / Vague"
    yield "No reason", "No reason / Vague"
    yield "No dropped reason captured", "No reason / Vague"
    yield "No reason captured", "No reason / Vague"
    yield "Vague", "No reason / Vague"
    yield "Non responsive", "Non-responsive"
    yield "Nonresponsive", "Non-responsive"
    yield "RPM CPM comparison", "RPM/CPM comparison"
    yield "Low RPM", "Low RPM/CPM"
    yield "Low CPM", "Low RPM/CPM"
    yield "AdThrive", "Other"


REASON_ALIASES = {reason_key(alias): canonical for alias, canonical in _alias_pairs()}


def normalize_dropped_reason(value: object, *, has_drop: bool = True) -> str:
    """Map a raw dropped reason to the approved dashboard bucket.

    The mapping is intentionally conservative: long freeform explanations stay in
    `Everything Else` unless they are an exact approved category or known legacy
    spelling. The table can still show the original raw text.
    """

    clean = clean_blank(value)
    if not clean:
        return "No reason / Vague" if has_drop else ""

    key = reason_key(clean)
    return REASON_ALIASES.get(key, EVERYTHING_ELSE_REASON)
