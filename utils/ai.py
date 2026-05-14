from __future__ import annotations

import json
import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # Allows local/offline runs to use deterministic rules.
    OpenAI = None

from utils.text import normalize_text


CATEGORIES = [
    "Communication Dropoff",
    "Timing / Busy",
    "Monetization Concerns",
    "Technical Blockers",
    "Competitive Loyalty",
    "Personal Reasons",
    "Unknown",
]


def rule_based_classify(description: str, cancelled_reason: str = "") -> dict[str, Any]:
    text = normalize_text(f"{cancelled_reason} {description}")
    rules = [
        ("Personal Reasons", {"mother passed", "health", "family", "personal reason", "bereavement"}),
        ("Technical Blockers", {"technical", "dns", "ads txt", "adstxt", "gam", "plugin", "code", "install issue"}),
        ("Monetization Concerns", {"monetization", "revenue", "rpm", "rate", "layout", "ad density", "earnings"}),
        ("Competitive Loyalty", {"mediavine", "freestar", "adsense", "other network", "current network", "stay with"}),
        ("Timing / Busy", {"busy", "later", "hold off", "not ready", "move", "vacation", "postpone", "timing"}),
        ("Communication Dropoff", {"unresponsive", "no response", "non responsive", "havent heard", "ghost", "followed up"}),
    ]
    for category, terms in rules:
        if any(term in text for term in terms):
            return {
                "normalized_category": category,
                "confidence_score": 0.72,
                "classification_method": "rules",
            }
    return {
        "normalized_category": "Unknown",
        "confidence_score": 0.4,
        "classification_method": "rules",
    }


def openai_classify(
    description: str,
    cancelled_reason: str = "",
    model: str = "gpt-4.1-mini",
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI()
    prompt = {
        "task": "Classify why this creator dropped onboarding.",
        "allowed_categories": CATEGORIES,
        "description": description or "",
        "cancelled_reason": cancelled_reason or "",
        "output_schema": {
            "normalized_category": "one allowed category",
            "confidence_score": "number from 0 to 1",
        },
    }
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You normalize cancellation reasons for lifecycle analytics. "
                    "Use only the provided categories and return compact JSON."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    parsed = json.loads(response.choices[0].message.content or "{}")
    category = parsed.get("normalized_category", "Unknown")
    if category not in CATEGORIES:
        category = "Unknown"
    confidence = float(parsed.get("confidence_score", 0.0) or 0.0)
    return {
        "normalized_category": category,
        "confidence_score": max(0.0, min(confidence, 1.0)),
        "classification_method": "openai",
    }


def classify_cancellation_reason(
    description: str,
    cancelled_reason: str = "",
    model: str = "gpt-4.1-mini",
    use_openai: bool = True,
) -> dict[str, Any]:
    if use_openai and os.getenv("OPENAI_API_KEY"):
        try:
            return openai_classify(description, cancelled_reason, model=model)
        except Exception:
            return rule_based_classify(description, cancelled_reason)
    return rule_based_classify(description, cancelled_reason)
