from __future__ import annotations

import html
import re
import unicodedata
from datetime import date
from typing import Iterable

import pandas as pd


DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+\.[a-z]{2,})(?:/[^\s,;)]*)?",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b")


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = html.unescape(text)
    text = strip_accents(text).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify_column(value: object) -> str:
    return normalize_text(value).replace(" ", "_")


def normalize_creator_name(value: object) -> str:
    text = normalize_text(value)
    for suffix in (" llc", " inc", " co", " company", " blog", " media"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return re.sub(r"\s+", " ", text).strip()


def extract_domains(*values: object) -> list[str]:
    domains: list[str] = []
    ignored = {
        "salesforce.com",
        "force.com",
        "zendesk.com",
        "slack.com",
        "raptive.com",
        "cafemedia.com",
    }
    for value in values:
        text = "" if value is None else str(value).lower()
        for match in DOMAIN_RE.findall(text):
            domain = match.strip(".").lower()
            if not any(domain.endswith(ignored_domain) for ignored_domain in ignored):
                domains.append(domain)
    return sorted(set(domains))


def infer_date_from_text(value: object, reference: date | None = None) -> pd.Timestamp:
    text = "" if value is None else str(value)
    ref = reference or date.today()
    candidates: list[tuple[int, pd.Timestamp]] = []
    for match in DATE_RE.finditer(text):
        month_s, day_s, year_s = match.groups()
        month = int(month_s)
        day = int(day_s)
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        if year_s:
            year = int(year_s)
            if year < 100:
                year += 2000
        else:
            year = ref.year
            if month > ref.month + 1:
                year -= 1
        parsed = pd.to_datetime(
            f"{year:04d}-{month:02d}-{day:02d}", errors="coerce"
        )
        if pd.notna(parsed):
            context_start = max(0, match.start() - 80)
            context_end = min(len(text), match.end() + 100)
            context = normalize_text(text[context_start:context_end])
            if any(term in context for term in ("drop", "dropped", "dropping", "cancel", "cancellation")):
                score = 0
            elif any(term in context for term in ("no response", "unresponsive", "followed up", "havent heard")):
                score = 1
            else:
                score = 2
            candidates.append((score, parsed))
    if not candidates:
        return pd.NaT
    # Prefer dates closest to cancellation/drop language, then the most recent such date.
    return sorted(candidates, key=lambda item: (item[0], -item[1].value))[0][1]


def contains_any(text: object, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in terms)
