from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd

try:
    from slack_sdk import WebClient
except ImportError:
    WebClient = None

from utils.text import normalize_text


def iso_to_slack_ts(value: str) -> str:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return str(dt.timestamp())


def classify_slack_event(channel_name: str, text: str) -> str:
    normalized = normalize_text(f"{channel_name} {text}")
    if "salesloft" in normalized or "meeting booked" in normalized or "booked a meeting" in normalized:
        return "salesloft_meeting"
    if "call link" in normalized or "book a call" in normalized or "schedule a call" in normalized:
        return "onboarding_call_offer"
    if "creator growth" in normalized or "passed to cg" in normalized or "cg handoff" in normalized:
        return "creator_growth_escalation"
    if "rescue" in normalized or "save" in normalized or "re engage" in normalized:
        return "rescue_intervention"
    return "mention"


class SlackPuller:
    def __init__(self) -> None:
        if WebClient is None:
            raise RuntimeError("slack-sdk is not installed. Run `pip install -r requirements.txt`.")
        self.client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    def find_channel_id(self, name: str) -> str:
        target = name.lstrip("#").lower()
        cursor = None
        while True:
            response = self.client.conversations_list(
                types="public_channel,private_channel",
                exclude_archived=True,
                limit=200,
                cursor=cursor,
            )
            for channel in response.get("channels", []):
                if channel.get("name", "").lower() == target:
                    return channel["id"]
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        raise RuntimeError(f"Slack channel not found or not accessible: {name}")

    def fetch_channel_history(self, channel_name: str, oldest: str) -> list[dict[str, Any]]:
        channel_id = self.find_channel_id(channel_name)
        cursor = None
        rows: list[dict[str, Any]] = []
        while True:
            response = self.client.conversations_history(
                channel=channel_id,
                oldest=oldest,
                limit=200,
                cursor=cursor,
                inclusive=True,
            )
            for message in response.get("messages", []):
                text = message.get("text", "")
                ts = message.get("ts", "")
                event_ts = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat() if ts else ""
                rows.append(
                    {
                        "channel_name": channel_name.lstrip("#"),
                        "channel_id": channel_id,
                        "message_ts": ts,
                        "event_at": event_ts,
                        "user": message.get("user") or message.get("bot_id", ""),
                        "text": text,
                        "event_type": classify_slack_event(channel_name, text),
                        "thread_ts": message.get("thread_ts", ""),
                        "permalink": "",
                    }
                )
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return rows

    def fetch_channels(self, channel_names: list[str], start_date: str) -> pd.DataFrame:
        oldest = iso_to_slack_ts(start_date)
        rows: list[dict[str, Any]] = []
        for channel_name in channel_names:
            rows.extend(self.fetch_channel_history(channel_name, oldest))
        return pd.DataFrame(rows)
