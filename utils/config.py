from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_value(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    raw_data_dir: Path
    processed_data_dir: Path
    output_dir: Path

    salesforce_api_version: str
    salesforce_domain: str
    salesforce_dropped_report_id: str
    salesforce_returning_report_id: str

    zendesk_subdomain: str
    zendesk_search_query: str

    slack_channel_names: list[str]
    slack_start_date: str

    openai_model: str
    use_openai_classification: bool

    @property
    def has_salesforce_credentials(self) -> bool:
        username_flow = all(
            os.getenv(name)
            for name in (
                "SALESFORCE_USERNAME",
                "SALESFORCE_PASSWORD",
                "SALESFORCE_SECURITY_TOKEN",
            )
        )
        session_flow = all(
            os.getenv(name)
            for name in ("SALESFORCE_SESSION_ID", "SALESFORCE_INSTANCE_URL")
        )
        return username_flow or session_flow

    @property
    def has_zendesk_credentials(self) -> bool:
        return all(
            os.getenv(name)
            for name in ("ZENDESK_EMAIL", "ZENDESK_API_TOKEN", "ZENDESK_SUBDOMAIN")
        )

    @property
    def has_slack_credentials(self) -> bool:
        return bool(os.getenv("SLACK_BOT_TOKEN"))


def load_settings(base_dir: Path | None = None) -> Settings:
    root = base_dir or Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    return Settings(
        base_dir=root,
        data_dir=data_dir,
        raw_data_dir=data_dir / "raw",
        processed_data_dir=data_dir / "processed",
        output_dir=root / "outputs",
        salesforce_api_version=env_value("SALESFORCE_API_VERSION", "v60.0"),
        salesforce_domain=env_value("SALESFORCE_DOMAIN", "login"),
        salesforce_dropped_report_id=env_value(
            "SALESFORCE_DROPPED_REPORT_ID", "00OQQ000007tl772AA"
        ),
        salesforce_returning_report_id=env_value(
            "SALESFORCE_RETURNING_REPORT_ID", "00OQQ000007tlAL2AY"
        ),
        zendesk_subdomain=env_value("ZENDESK_SUBDOMAIN", "raptive"),
        zendesk_search_query=env_value(
            "ZENDESK_SEARCH_QUERY",
            'type:ticket tags:onboarding created>=2025-01-01',
        ),
        slack_channel_names=env_list(
            "SLACK_CHANNEL_NAMES",
            ["onboarding-creatorgrowth", "salesloft-meetings"],
        ),
        slack_start_date=env_value("SLACK_START_DATE", "2025-01-01"),
        openai_model=env_value("OPENAI_MODEL", "gpt-4.1-mini"),
        use_openai_classification=env_bool("USE_OPENAI_CLASSIFICATION", True),
    )


def ensure_project_dirs(settings: Settings) -> None:
    for path in (
        settings.raw_data_dir,
        settings.processed_data_dir,
        settings.output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
