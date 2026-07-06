from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, read_csv_if_exists
from utils.zendesk_client import format_macro_cadence


BOOL_COLUMNS = {
    "cg_escalation_status",
    "install_completed",
    "converted",
    "reengaged",
    "has_3_day_followup",
    "has_5_day_followup",
    "has_7_day_followup",
    "source_full_site_history",
}

REPORT_FIELDS = [
    "lifecycle_creator_id",
    "creator_key",
    "lead_key",
    "creator_project_name",
    "lead_contact",
    "company_name",
    "domain",
    "site_id",
    "salesforce_project_id",
    "salesforce_account_id",
    "vertical",
    "service_level",
    "previous_ad_network",
    "onboarding_owner",
    "monthly_pageviews",
    "current_status",
    "dropped_status",
    "onboard_year",
    "returned_year",
    "onboarding_started_date",
    "dropped_date",
    "dropped_dates",
    "returned_date",
    "returned_reason",
    "install_date",
    "install_history",
    "days_to_return",
    "cancellation_reason",
    "dropped_reason",
    "dropped_reason_category",
    "normalized_dropped_reason",
    "raw_description",
    "macro_cadence",
    "has_3_day_followup",
    "has_5_day_followup",
    "has_7_day_followup",
    "cg_involvement",
    "cg_escalation_status",
    "install_completed",
    "converted",
    "reengaged",
    "outcome",
    "returning_owner",
    "returning_status",
    "drop_count",
    "site_history_event_count",
]

CONTEXT_FIELDS = [
    "site_id",
    "site_name",
    "creator_name",
    "domain",
    "service_level",
    "vertical",
    "previous_ad_network",
    "onboarding_owner",
    "outcome",
    "dropped_date",
    "dropped_reason_category",
    "dropped_reason",
    "zendesk_context_available",
    "zendesk_ticket_count",
    "zendesk_ticket_ids",
    "zendesk_summary",
    "cancellation_ghosting_themes",
    "communication_themes",
    "dropoff_cg_themes",
    "sentiment",
    "milestone_stage",
    "cg_involvement",
    "cg_escalation_status",
    "cg_first_touch_at",
    "cg_days_from_drop",
    "context_summary",
]

DROPPED_REASON_GROUPS = [
    {
        "category": "Site Performance/SEO",
        "reasons": [
            "SEO/Pageviews down",
            "Site performance",
            "Poor user experience",
            "Other",
            "Core Web Vitals",
        ],
    },
    {
        "category": "Site Transfer",
        "reasons": [
            "No Longer Eligible For Transfer",
            "Rejected by MCM",
            "Failure to complete MCM IDV",
            "New owner did not want to stay with AdThrive",
        ],
    },
    {
        "category": "Fired",
        "reasons": [
            "Fraud traffic",
            "Brand safety",
            "Stolen content",
            "Other",
            "Ownership/MCM",
            "Identity Concerns",
            "AI Content",
        ],
    },
    {"category": "Merged", "reasons": ["Merged"]},
    {
        "category": "Switched ad networks",
        "reasons": [
            "Making changes / Vague",
            "No reason / Vague",
            "Testing competitor",
        ],
    },
    {
        "category": "Missing features",
        "reasons": [
            "Account manager",
            "Dashboard/More data",
            "Other",
            "Expanded Solutions related",
            "Ad content/controls",
        ],
    },
    {
        "category": "Set-up Cancellation",
        "reasons": [
            "RPM too high",
            "Never engaged",
            "Personal Reasons",
            "Failed verification",
            "Non-responsive",
            "Refused ad layout",
            "Rejected by MCM",
            "Single page application",
            "Refused to share ad performance",
            "Staying with Current ad provider",
            "Stuck in long-term contract",
            "Chose another provider",
            "Cancelled pre-onboarding",
            "Fraudulent traffic detected",
            "Other",
        ],
    },
    {
        "category": "Discontinuing Ads",
        "reasons": [
            "Design concerns",
            "Other revenue sources",
            "Retiring site",
            "Google Terminated MCM Account",
        ],
    },
    {
        "category": "Earning Concerns",
        "reasons": [
            "Low RPM/CPM",
            "Disappointed in RPM Guarantee",
            "RPM/CPM comparison",
            "Revenue Share",
            "Loyalty Bonus",
        ],
    },
    {"category": "Everything else", "reasons": ["Everything else"]},
]

def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def to_bool(value: object) -> bool:
    return clean_text(value).lower() in {"1", "true", "yes", "y", "booked", "installed", "converted"}


def cadence_has_day(cadence: object, day: str) -> bool:
    return bool(re.search(rf"\b{re.escape(day)}\b", clean_text(cadence).lower()))


def prepare_records(master: pd.DataFrame) -> list[dict[str, object]]:
    available_fields = [field for field in REPORT_FIELDS if field in master.columns]
    records = master[available_fields].fillna("").to_dict(orient="records")
    for record in records:
        for column in BOOL_COLUMNS:
            if column in record:
                record[column] = to_bool(record[column])
        for day, column in (
            ("3", "has_3_day_followup"),
            ("5", "has_5_day_followup"),
            ("7", "has_7_day_followup"),
        ):
            record[column] = bool(record.get(column)) or cadence_has_day(record.get("macro_cadence"), day)
        if not clean_text(record.get("macro_cadence")):
            days = [
                day
                for day, column in (
                    ("3", "has_3_day_followup"),
                    ("5", "has_5_day_followup"),
                    ("7", "has_7_day_followup"),
                )
                if record.get(column) is True
            ]
            record["macro_cadence"] = format_macro_cadence(days)
        for key, value in list(record.items()):
            if not isinstance(value, bool):
                record[key] = "" if value is None else str(value)
    return records


def prepare_context_records(context: pd.DataFrame) -> list[dict[str, object]]:
    if context.empty:
        return []
    available_fields = [field for field in CONTEXT_FIELDS if field in context.columns]
    records = context[available_fields].fillna("").to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if key in {"zendesk_context_available", "cg_escalation_status"}:
                record[key] = to_bool(value)
            else:
                record[key] = "" if value is None else str(value)
    return records


def render_html(records: list[dict[str, object]], generated_at: str) -> str:
    data_json = json.dumps(records, ensure_ascii=False)
    reason_groups_json = json.dumps(DROPPED_REASON_GROUPS, ensure_ascii=False)
    generated = html.escape(generated_at)
    total = len(records)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Site Retention Analysis</title>
  <style>
    :root {{
      --bg: #F0EDEB;
      --surface: #FFFFFF;
      --line: #E1DAD4;
      --text: #000000;
      --muted: #354786;
      --brand: #6B65FF;
      --brand-soft: #F0F0FF;
      --spark: #D2FF66;
      --pink: #ECB5D2;
      --orange: #FF7858;
      --green: #00785D;
      --red: #A23B4C;
      --blue: #354786;
      --grey: #978985;
      --ink-soft: #F0F0FF;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Roobert Pro", "DM Sans", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.4;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      border-top: 6px solid var(--brand);
      background: var(--brand-soft);
      padding: 26px 32px 22px;
    }}
    .title-row {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      flex-wrap: wrap;
    }}
    .eyebrow {{
      color: var(--green);
      font-size: 13px;
      font-weight: 760;
      letter-spacing: 0;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}
    h1 {{
      margin: 0;
      font-size: 46px;
      line-height: 1.15;
      letter-spacing: 0;
      font-weight: 720;
      color: var(--text);
    }}
    .subtitle {{
      color: var(--muted);
      margin-top: 12px;
      font-size: 17px;
      max-width: 980px;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .button {{
      border: 1px solid var(--green);
      border-radius: 6px;
      background: var(--green);
      color: var(--surface);
      cursor: pointer;
      font: inherit;
      font-size: 15px;
      font-weight: 760;
      min-height: 46px;
      padding: 10px 18px;
    }}
    .button.secondary {{
      border-color: var(--line);
      background: var(--surface);
      color: var(--muted);
    }}
    main {{
      padding: 28px 32px 40px;
      max-width: 1680px;
      margin: 0 auto;
    }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      align-items: end;
      margin-bottom: 24px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 18px;
    }}
    .search-control {{
      grid-column: span 2;
    }}
    .cadence-control {{
      grid-column: span 2;
    }}
    label {{
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
      font-size: 16px;
      min-height: 48px;
    }}
    input:focus, select:focus {{
      border-color: var(--brand);
      outline: 2px solid var(--brand);
      outline-offset: 1px;
    }}
    .control-group {{
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
    }}
    .controls > label,
    .control-group > span {{
      text-transform: uppercase;
    }}
    .cadence-options {{
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      padding: 9px 12px;
    }}
    .cadence-option {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: var(--text);
      background: transparent;
      border-radius: 0;
      padding: 0;
      font-size: 15px;
      font-weight: 650;
      line-height: 1;
    }}
    .cadence-option input {{
      width: auto;
      min-height: 0;
      margin: 0;
      padding: 0;
      accent-color: var(--brand);
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(5, minmax(130px, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }}
    .tile, .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .tile {{
      padding: 18px 20px;
      min-height: 116px;
      position: relative;
      cursor: help;
    }}
    .tile:focus {{
      border-color: var(--brand);
      outline: 2px solid var(--brand);
      outline-offset: 2px;
    }}
    .tile::after {{
      content: attr(data-tooltip);
      position: absolute;
      left: 12px;
      top: calc(100% + 8px);
      z-index: 20;
      width: min(320px, calc(100vw - 48px));
      border-radius: 6px;
      background: var(--text);
      color: var(--surface);
      box-shadow: var(--shadow);
      font-size: 13px;
      font-weight: 500;
      line-height: 1.35;
      opacity: 0;
      padding: 9px 10px;
      pointer-events: none;
      transform: translateY(-4px);
      transition: opacity 120ms ease, transform 120ms ease;
    }}
    .tile:hover::after,
    .tile:focus::after {{
      opacity: 1;
      transform: translateY(0);
    }}
    .tile .label {{
      color: var(--muted);
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
    }}
    .info-dot {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 760;
      line-height: 1;
    }}
    .tile .value {{
      margin-top: 14px;
      font-size: 40px;
      line-height: 1;
      font-weight: 760;
      letter-spacing: 0;
      color: var(--text);
    }}
    .tile .note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 15px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      padding: 18px;
      min-height: 320px;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .panel-header span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .bars {{
      display: grid;
      gap: 10px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(120px, 190px) 1fr 72px;
      gap: 12px;
      align-items: center;
    }}
    .bar-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text);
      font-size: 14px;
    }}
    .bar-track {{
      background: var(--ink-soft);
      height: 12px;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      min-width: 2px;
      background: var(--brand);
      border-radius: 999px;
    }}
    .bar-fill.blue {{ background: var(--green); }}
    .bar-fill.amber {{ background: var(--orange); }}
    .bar-fill.rose {{ background: var(--blue); }}
    .bar-value {{
      text-align: right;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-size: 14px;
    }}
    .table-panel {{
      padding: 0;
      overflow: hidden;
    }}
    .table-header {{
      padding: 18px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .table-title {{
      display: grid;
      gap: 2px;
    }}
    .table-tools {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
    }}
    .toggle-line {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      white-space: nowrap;
    }}
    .toggle-line input {{
      width: auto;
      min-height: 0;
      margin: 0;
      padding: 0;
      accent-color: var(--brand);
    }}
    .page-size {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .page-size select {{
      width: auto;
      min-height: 34px;
      padding: 5px 28px 5px 9px;
      font-size: 14px;
    }}
    .pagination-controls {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .pager-button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 760;
      min-height: 34px;
      padding: 6px 10px;
    }}
    .pager-button:disabled {{
      cursor: not-allowed;
      opacity: 0.45;
    }}
    .page-status {{
      color: var(--muted);
      font-size: 13px;
      min-width: 132px;
      text-align: center;
      white-space: nowrap;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 560px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1500px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    .number-col {{
      width: 46px;
      min-width: 46px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      text-align: right;
    }}
    th {{
      position: sticky;
      top: 0;
      background: var(--brand-soft);
      z-index: 1;
      color: var(--muted);
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .sort-button {{
      border: 0;
      background: transparent;
      color: inherit;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 0;
      min-height: 0;
      font: inherit;
      font-weight: inherit;
      text-transform: inherit;
      cursor: pointer;
    }}
    .sort-indicator {{
      color: var(--brand);
      display: inline-block;
      min-width: 8px;
    }}
    td {{
      font-size: 14px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--green);
      color: #FFFFFF;
      white-space: nowrap;
    }}
    .status.no {{
      background: var(--red);
      color: #FFFFFF;
    }}
    .status.warn {{
      background: var(--spark);
      color: var(--text);
    }}
    .status.progress {{
      background: var(--brand);
      color: #FFFFFF;
    }}
    .cell-note {{
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
      white-space: pre-line;
    }}
    .cadence-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      background: var(--brand-soft);
      color: var(--blue);
      font-size: 12px;
      font-weight: 700;
      line-height: 1.1;
      margin: 0 4px 4px 0;
      padding: 3px 8px;
      white-space: nowrap;
    }}
    .cadence-pill--3 {{
      background: var(--brand-soft);
      color: var(--blue);
    }}
    .cadence-pill--5 {{
      background: var(--spark);
      color: var(--text);
    }}
    .cadence-pill--7 {{
      background: var(--pink);
      color: var(--text);
    }}
    .cadence-pill--cg {{
      background: var(--blue);
      color: var(--surface);
    }}
    .context-link {{
      color: var(--green);
      font-weight: 760;
      text-decoration: none;
      white-space: nowrap;
    }}
    .context-link:hover {{
      text-decoration: underline;
    }}
    .hidden-col {{
      display: none;
    }}
    .empty {{
      color: var(--muted);
      padding: 18px 0;
      font-size: 13px;
    }}
    .empty-row td {{
      color: var(--muted);
      padding: 24px 14px;
      text-align: center;
    }}
    @media (max-width: 1100px) {{
      .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .controls, .kpis {{ grid-template-columns: 1fr; }}
      .search-control, .cadence-control {{ grid-column: auto; }}
      .bar-row {{ grid-template-columns: 110px 1fr 56px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-row">
      <div>
        <div class="eyebrow">Reporting</div>
        <h1>Site Retention Analysis</h1>
        <div class="subtitle">Track installed, dropped, returned, and re-engaged sites across onboarding ownership, follow-up cadence, Creator Growth involvement, and drop reasons.</div>
      </div>
      <div class="header-actions">
        <button class="button secondary" type="button" id="reset-filters">Reset</button>
        <button class="button" type="button" id="export-csv">Export CSV</button>
      </div>
    </div>
  </header>

  <main>
    <section class="controls" aria-label="Filters">
      <label class="search-control">Search
        <input id="search" type="search" placeholder="Site, creator, or onboarding owner">
      </label>
      <label>Installed Year
        <select id="installed-year"></select>
      </label>
      <label>Outcome
        <select id="outcome"></select>
      </label>
      <label>Owner
        <select id="owner"></select>
      </label>
      <label>Vertical
        <select id="vertical"></select>
      </label>
      <label>Service Level
        <select id="service"></select>
      </label>
      <label>Previous Ad Network
        <select id="previous-network"></select>
      </label>
      <div class="control-group cadence-control">
        <span>Follow-Up Cadence</span>
        <div class="cadence-options" id="cadence-options" role="group" aria-label="Follow-up cadence">
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="3">3 Day Follow Up</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="5">5 Day Follow Up</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="7">7 Day Follow Up</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="cg">Escalated to Creator Growth</label>
        </div>
      </div>
      <label>Dropped Reason Category
        <select id="reason-category"></select>
      </label>
      <label>Dropped Reason
        <select id="reason"></select>
      </label>
    </section>

    <section class="kpis" id="kpis"></section>

    <section class="grid">
      <div class="panel">
        <div class="panel-header"><h2>Service Level</h2><span id="service-count"></span></div>
        <div class="bars" id="service-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Dropped Reasons</h2><span id="reason-count"></span></div>
        <div class="bars" id="reason-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Creator Growth</h2><span id="cg-count"></span></div>
        <div class="bars" id="cg-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Previous Ad Network</h2><span id="network-count"></span></div>
        <div class="bars" id="network-bars"></div>
      </div>
    </section>

    <section class="panel table-panel">
      <div class="table-header">
        <div class="table-title">
          <h2>Sites</h2>
          <span class="subtitle" id="row-count"></span>
        </div>
        <div class="table-tools">
          <label class="page-size">Rows
            <select id="page-size">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="250">250</option>
            </select>
          </label>
          <div class="pagination-controls" aria-label="Table pagination">
            <button class="pager-button" type="button" id="prev-page">Previous</button>
            <span class="page-status" id="page-status"></span>
            <button class="pager-button" type="button" id="next-page">Next</button>
          </div>
          <label class="toggle-line"><input type="checkbox" id="toggle-returned-reason">Returned Reason</label>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="number-col">#</th>
              <th><button class="sort-button" type="button" data-sort="creator_project_name">Site Name <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="lead">Creator Name <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="service_level">Service Level <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="vertical">Vertical <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="previous_ad_network">Previous Ad Network <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="onboarding_owner">Onboarding Owner <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="dropped_date">Dropped Date <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="reason_category">Dropped Reason Category <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="reason">Dropped Reason <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="zendesk_context">Zendesk Context <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="macro_cadence">Follow-up Cadence <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="cg_involvement">CG Involvement <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="returned_date">Returned Date <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="outcome">Outcome <span class="sort-indicator"></span></button></th>
              <th class="returned-reason-col hidden-col"><button class="sort-button" type="button" data-sort="returned_reason">Returned Reason <span class="sort-indicator"></span></button></th>
            </tr>
          </thead>
          <tbody id="creator-rows"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const RECORDS = {data_json};
    const DROPPED_REASON_GROUPS = {reason_groups_json};
    const EVERYTHING_ELSE_REASON_OPTION = {{ category: 'Everything else', reason: 'Everything else' }};
    const REASON_OPTION_SEPARATOR = '::';
    const SERVICE_LEVELS = ['Insider', 'Platinum', 'Platinum Elite', 'Rise'];
    const OUTCOME_OPTIONS = ['Installed', 'Onboarding', 'Dropped', 'Returned'];
    const ONBOARDING_TEAM_OWNERS = ['Amy Burgess', 'Antoinette Smith', 'Michelle Stappert', 'Whitney Harrist'];
    const PREVIOUS_NETWORK_LABELS = {{
      'n/a': 'N/A',
      'adsense': 'AdSense',
      'adstyle': 'AdStyle',
      'adx': 'AdX',
      'adthrive legacy': 'AdThrive Legacy',
      'ezoic': 'Ezoic',
      'freestar': 'Freestar',
      'media.net': 'Media.net',
      'mediavine': 'Mediavine',
      'monumetric': 'Monumetric',
      'she media': 'SHE Media'
    }};
    const sortState = {{ key: 'activity_date', direction: 'desc' }};
    const tableState = {{ page: 1, pageSize: 100 }};
    const fields = {{
      search: document.getElementById('search'),
      installedYear: document.getElementById('installed-year'),
      outcome: document.getElementById('outcome'),
      service: document.getElementById('service'),
      previousNetwork: document.getElementById('previous-network'),
      vertical: document.getElementById('vertical'),
      owner: document.getElementById('owner'),
      cadenceOptions: document.getElementById('cadence-options'),
      reasonCategory: document.getElementById('reason-category'),
      reason: document.getElementById('reason')
    }};
    const actions = {{
      reset: document.getElementById('reset-filters'),
      exportCsv: document.getElementById('export-csv'),
      returnedReasonToggle: document.getElementById('toggle-returned-reason'),
      pageSize: document.getElementById('page-size'),
      prevPage: document.getElementById('prev-page'),
      nextPage: document.getElementById('next-page'),
      pageStatus: document.getElementById('page-status')
    }};
    const filterControls = [
      fields.search,
      fields.installedYear,
      fields.outcome,
      fields.service,
      fields.previousNetwork,
      fields.vertical,
      fields.owner,
      fields.cadenceOptions,
      fields.reason
    ];

    function text(value) {{
      return (value ?? '').toString();
    }}

    function clean(value) {{
      return text(value).trim();
    }}

    function display(value) {{
      const valueText = clean(value);
      return valueText || 'N/A';
    }}

    function displayLabel(value) {{
      const valueText = clean(value);
      const letters = valueText.match(/[A-Za-z]/g) || [];
      if (letters.length && /[A-Z]/.test(valueText) && !/[a-z]/.test(valueText)) {{
        const lowered = valueText.toLowerCase();
        return lowered.charAt(0).toUpperCase() + lowered.slice(1);
      }}
      return valueText || 'N/A';
    }}

    function truthy(value) {{
      return value === true || ['true', '1', 'yes', 'y', 'booked', 'installed', 'converted'].includes(text(value).toLowerCase());
    }}

    function pct(part, total) {{
      return total ? `${{Math.round((part / total) * 1000) / 10}}%` : '0%';
    }}

    function number(value) {{
      const n = Number(String(value).replace(/,/g, ''));
      return Number.isFinite(n) ? n : 0;
    }}

    function formatCount(value) {{
      return Number(value).toLocaleString();
    }}

    function optionValue(value) {{
      return display(value);
    }}

    function previousNetworkLabel(value) {{
      const valueText = clean(value);
      if (!valueText) return 'N/A';
      const key = valueText.toLowerCase().replace(/\\s+/g, ' ');
      return PREVIOUS_NETWORK_LABELS[key] || displayLabel(valueText);
    }}

    function previousNetworkParts(value) {{
      const valueText = clean(value);
      if (!valueText) return ['N/A'];
      const parts = valueText.split(',')
        .map(part => previousNetworkLabel(part))
        .filter(Boolean);
      return [...new Set(parts.length ? parts : [previousNetworkLabel(valueText)])];
    }}

    function previousNetworkValue(value) {{
      return previousNetworkParts(value).join(', ');
    }}

    function hasCadence(row, day) {{
      const cadenceText = clean(row.macro_cadence).toLowerCase();
      return truthy(row[`has_${{day}}_day_followup`]) || new RegExp(`\\\\b${{day}}\\\\b`).test(cadenceText);
    }}

    function hasEscalatedToCg(row) {{
      const involvement = clean(row.cg_involvement).toLowerCase();
      return truthy(row.cg_escalation_status)
        || truthy(row.has_escalated_to_cg)
        || involvement.includes('escalated to cg')
        || involvement.includes('escalated to creator growth');
    }}

    function hasCadenceFilter(row, value) {{
      return value === 'cg' ? hasEscalatedToCg(row) : hasCadence(row, value);
    }}

    function hasAnyFollowUp(row) {{
      return ['3', '5', '7'].some(day => hasCadence(row, day)) || hasEscalatedToCg(row);
    }}

    function cadenceItems(row) {{
      const labels = [];
      if (hasCadence(row, '3')) labels.push('3 Day');
      if (hasCadence(row, '5')) labels.push('5 Day');
      if (hasCadence(row, '7')) labels.push('7 Day');
      if (hasEscalatedToCg(row)) labels.push('Escalated to CG');
      return labels;
    }}

    function cadenceValue(row) {{
      const labels = cadenceItems(row);
      return labels.length ? labels.join(', ') : 'None';
    }}

    function cadencePillClass(label) {{
      if (label.startsWith('3')) return 'cadence-pill--3';
      if (label.startsWith('5')) return 'cadence-pill--5';
      if (label.startsWith('7')) return 'cadence-pill--7';
      return 'cadence-pill--cg';
    }}

    function cadencePills(row) {{
      const labels = cadenceItems(row);
      if (!labels.length) return 'None';
      return labels.map(label => `<span class="cadence-pill ${{cadencePillClass(label)}}">${{escapeHtml(label)}}</span>`).join('');
    }}

    function droppedYear(row) {{
      const value = clean(row.dropped_date);
      if (!value) return '';
      const parsed = new Date(value);
      if (!Number.isNaN(parsed.getTime())) return String(parsed.getUTCFullYear());
      return value.slice(0, 4);
    }}

    function hasZendeskContextPage(row) {{
      return hasDropSignal(row) && droppedYear(row) === '2026';
    }}

    function zendeskContextHref(row) {{
      const siteId = clean(row.site_id);
      if (siteId) return `zendesk_context.html?site_id=${{encodeURIComponent(siteId)}}`;
      return `zendesk_context.html?site_name=${{encodeURIComponent(display(row.creator_project_name))}}`;
    }}

    function zendeskContextCell(row) {{
      if (!hasZendeskContextPage(row)) return 'N/A';
      return `<a class="context-link" href="${{escapeAttr(zendeskContextHref(row))}}" target="_blank" rel="noopener">View context</a>`;
    }}

    function reasonCategoryValue(row) {{
      return displayLabel(row.dropped_reason_category);
    }}

    function reasonValue(row) {{
      return displayLabel(row.dropped_reason);
    }}

    function taxonomyKey(value) {{
      return clean(value)
        .toLowerCase()
        .replace(/&/g, 'and')
        .replace(/[^a-z0-9]+/g, '');
    }}

    function canonicalReasonKey(value) {{
      const key = taxonomyKey(value);
      const aliases = {{
        canceledpreonboarding: 'cancelledpreonboarding',
        cancelledpreboarding: 'cancelledpreonboarding',
        cancelledpreonboarding: 'cancelledpreonboarding',
        setupcancellation: 'cancelledpreonboarding',
        setupcancelled: 'cancelledpreonboarding',
        noreason: 'noreasonvague',
        noreasonvague: 'noreasonvague',
        noreasoncaptured: 'noreasonvague',
        nodroppedreasoncaptured: 'noreasonvague',
        vague: 'noreasonvague',
        everythingelse: 'everythingelse'
      }};
      return aliases[key] || key;
    }}

    const REASON_GROUP_BY_KEY = new Map();
    const REASON_OPTION_BY_GROUP_AND_REASON = new Map();
    const REASON_OPTIONS_BY_REASON = new Map();
    DROPPED_REASON_GROUPS.forEach(group => {{
      const categoryKey = taxonomyKey(group.category);
      REASON_GROUP_BY_KEY.set(categoryKey, group);
      group.reasons.forEach(reason => {{
        const option = {{ category: group.category, reason }};
        const reasonKey = canonicalReasonKey(reason);
        REASON_OPTION_BY_GROUP_AND_REASON.set(`${{categoryKey}}::${{reasonKey}}`, option);
        if (!REASON_OPTIONS_BY_REASON.has(reasonKey)) REASON_OPTIONS_BY_REASON.set(reasonKey, []);
        REASON_OPTIONS_BY_REASON.get(reasonKey).push(option);
      }});
    }});

    function hasDropSignal(row) {{
      const outcome = clean(row.outcome);
      return Boolean(
        clean(row.dropped_date)
        || number(row.drop_count) > 0
        || clean(row.dropped_reason)
        || clean(row.dropped_reason_category)
        || outcome === 'Dropped'
        || outcome === 'Returned'
      );
    }}

    function reasonOptionForRow(row) {{
      const categoryKey = taxonomyKey(row.dropped_reason_category);
      const candidates = [
        row.dropped_reason,
        row.normalized_dropped_reason,
        row.cancellation_reason
      ].map(clean).filter(Boolean);

      if (!hasDropSignal(row) && !categoryKey && !candidates.length) return null;

      if (REASON_GROUP_BY_KEY.has(categoryKey)) {{
        for (const candidate of candidates) {{
          const exact = REASON_OPTION_BY_GROUP_AND_REASON.get(`${{categoryKey}}::${{canonicalReasonKey(candidate)}}`);
          if (exact) return exact;
        }}
      }}

      for (const candidate of candidates) {{
        const matches = REASON_OPTIONS_BY_REASON.get(canonicalReasonKey(candidate)) || [];
        if (matches.length === 1) return matches[0];
      }}

      return EVERYTHING_ELSE_REASON_OPTION;
    }}

    function reasonOptionKey(category, reason) {{
      return `${{encodeURIComponent(category)}}${{REASON_OPTION_SEPARATOR}}${{encodeURIComponent(reason)}}`;
    }}

    function rowReasonOptionKey(row) {{
      const option = reasonOptionForRow(row);
      if (!option) return '';
      return reasonOptionKey(option.category, option.reason);
    }}

    function rowReasonCategoryFilterValue(row) {{
      const option = reasonOptionForRow(row);
      return option ? option.category : '';
    }}

    function yearValue(row, key, dateKey) {{
      const explicit = clean(row[key]);
      if (explicit) return explicit;
      const value = clean(row[dateKey]);
      if (!value) return '';
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? '' : String(parsed.getUTCFullYear());
    }}

    function ownerParts(row) {{
      return clean(row.onboarding_owner).split(';').map(item => item.trim()).filter(Boolean);
    }}

    function ownerValue(row) {{
      const owners = [...new Set(ownerParts(row))];
      return owners.length ? owners.join('; ') : 'N/A';
    }}

    function selectedCadenceDays() {{
      return [...document.querySelectorAll('input[name="cadence-day"]:checked')].map(input => input.value);
    }}

    function matchesInstalledYear(row) {{
      if (!fields.installedYear.value) return true;
      const outcome = clean(row.outcome);
      if (fields.outcome.value === 'Onboarding' && outcome === 'Onboarding') return true;
      return yearValue(row, 'onboard_year', 'install_date') === fields.installedYear.value;
    }}

    function escapeHtml(value) {{
      return text(value).replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}}[char]));
    }}

    function escapeAttr(value) {{
      return escapeHtml(value).replace(/`/g, '&grave;');
    }}

    function populateSelect(select, values) {{
      select.innerHTML = '<option value="">All</option>' + values
        .map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`)
        .join('');
    }}

    function populateGroupedSelect(select, groups) {{
      const groupOptions = groups
        .filter(group => group.values.length)
        .map(group => {{
          const options = group.values
            .map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`)
            .join('');
          return `<optgroup label="${{escapeAttr(group.label)}}">${{options}}</optgroup>`;
        }})
        .join('');
      select.innerHTML = '<option value="">All</option>' + groupOptions;
    }}

    function populateOwnerSelect() {{
      const owners = [...new Set(RECORDS.flatMap(ownerParts))].sort((a, b) => a.localeCompare(b));
      const onboardingTeamSet = new Set(ONBOARDING_TEAM_OWNERS);
      const onboardingTeamOwners = ONBOARDING_TEAM_OWNERS.filter(owner => owners.includes(owner));
      const otherOwners = owners.filter(owner => !onboardingTeamSet.has(owner));
      populateGroupedSelect(fields.owner, [
        {{ label: 'Onboarding Team', values: onboardingTeamOwners }},
        {{ label: 'Other', values: otherOwners }}
      ]);
    }}

    function populateReasonSelect() {{
      const selectedCategory = fields.reasonCategory.value;
      const groups = selectedCategory
        ? DROPPED_REASON_GROUPS.filter(group => group.category === selectedCategory)
        : DROPPED_REASON_GROUPS;
      const currentValue = fields.reason.value;
      const options = groups
        .map(group => {{
          const reasonOptions = group.reasons
            .map(reason => `<option value="${{escapeAttr(reasonOptionKey(group.category, reason))}}">${{escapeHtml(reason)}}</option>`)
            .join('');
          return `<optgroup label="${{escapeAttr(group.category)}}">${{reasonOptions}}</optgroup>`;
        }})
        .join('');
      fields.reason.innerHTML = '<option value="">All</option>' + options;
      if (currentValue && ![...fields.reason.options].some(option => option.value === currentValue)) {{
        fields.reason.value = '';
      }} else {{
        fields.reason.value = currentValue;
      }}
    }}

    function populateFilters() {{
      populateSelect(fields.installedYear, [...new Set(RECORDS
        .filter(row => clean(row.install_date))
        .map(row => yearValue(row, 'onboard_year', 'install_date'))
        .filter(Boolean))].sort((a, b) => b.localeCompare(a)));
      populateSelect(fields.outcome, OUTCOME_OPTIONS);
      populateSelect(fields.service, [...new Set(RECORDS.map(row => optionValue(row.service_level)))].sort((a, b) => a.localeCompare(b)));
      populateSelect(fields.previousNetwork, [...new Set(RECORDS.flatMap(row => previousNetworkParts(row.previous_ad_network)))].sort((a, b) => a.localeCompare(b)));
      populateSelect(fields.vertical, [...new Set(RECORDS.map(row => optionValue(row.vertical)))].sort((a, b) => a.localeCompare(b)));
      populateOwnerSelect();
      populateSelect(fields.reasonCategory, DROPPED_REASON_GROUPS.map(group => group.category));
      populateReasonSelect();
    }}

    function filtered() {{
      const query = fields.search.value.trim().toLowerCase();
      const cadenceDays = selectedCadenceDays();
      return RECORDS.filter(row => {{
        if (!matchesInstalledYear(row)) return false;
        if (fields.outcome.value && clean(row.outcome) !== fields.outcome.value) return false;
        if (fields.service.value && optionValue(row.service_level) !== fields.service.value) return false;
        if (fields.previousNetwork.value && !previousNetworkParts(row.previous_ad_network).includes(fields.previousNetwork.value)) return false;
        if (fields.vertical.value && optionValue(row.vertical) !== fields.vertical.value) return false;
        if (fields.owner.value && !ownerParts(row).includes(fields.owner.value)) return false;
        if (cadenceDays.length && !cadenceDays.some(value => hasCadenceFilter(row, value))) return false;
        if (fields.reasonCategory.value && rowReasonCategoryFilterValue(row) !== fields.reasonCategory.value) return false;
        if (fields.reason.value && rowReasonOptionKey(row) !== fields.reason.value) return false;
        if (!query) return true;
        const haystack = [
          row.creator_project_name,
          row.lead_contact,
          row.company_name,
          row.onboarding_owner
        ].map(text).join(' ').toLowerCase();
        return haystack.includes(query);
      }});
    }}

    function groupCounts(rows, formatter, limit = 8) {{
      const counts = new Map();
      rows.forEach(row => {{
        const value = formatter(row);
        counts.set(value, (counts.get(value) || 0) + 1);
      }});
      return [...counts.entries()]
        .map(([label, count]) => ({{ label, count }}))
        .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
        .slice(0, limit);
    }}

    function fixedCounts(rows, labels, formatter) {{
      const counts = new Map(labels.map(label => [label, 0]));
      rows.forEach(row => {{
        const value = formatter(row);
        if (counts.has(value)) counts.set(value, counts.get(value) + 1);
      }});
      return labels.map(label => ({{ label, count: counts.get(label) || 0 }}));
    }}

    function renderBars(id, rows, color = '') {{
      const target = document.getElementById(id);
      if (!rows.length) {{
        target.innerHTML = '<div class="empty">No rows match the current filters.</div>';
        return;
      }}
      const max = Math.max(...rows.map(row => row.count), 1);
      target.innerHTML = rows.map(row => {{
        const width = Math.max(2, (row.count / max) * 100);
        return `
          <div class="bar-row" title="${{escapeAttr(row.label)}}: ${{formatCount(row.count)}}">
            <div class="bar-label">${{escapeHtml(row.label)}}</div>
            <div class="bar-track"><div class="bar-fill ${{color}}" style="width: ${{width}}%"></div></div>
            <div class="bar-value">${{formatCount(row.count)}}</div>
          </div>
        `;
      }}).join('');
    }}

    function isDropped(row) {{
      return clean(row.outcome) === 'Dropped';
    }}

    function isSuccessfulOutcome(row) {{
      const outcome = clean(row.outcome);
      return outcome === 'Installed' || outcome === 'Returned';
    }}

    function summarize(rows) {{
      const total = rows.length;
      const dropped = rows.filter(isDropped).length;
      const installed = total;
      const returned = rows.filter(row => clean(row.outcome) === 'Returned').length;
      const reengagedWithCadence = rows.filter(row => hasAnyFollowUp(row) && isSuccessfulOutcome(row)).length;
      const rise = rows.filter(row => clean(row.service_level).toLowerCase() === 'rise').length;
      return {{ total, dropped, installed, returned, reengagedWithCadence, rise }};
    }}

    function renderKpis(rows) {{
      const s = summarize(rows);
      const tiles = [
        {{
          label: 'Sites',
          value: formatCount(s.total),
          note: 'Filtered row count',
          tooltip: 'Shows the total number of sites that match the current filters.'
        }},
        {{
          label: 'Dropped Rate',
          value: pct(s.dropped, s.installed),
          note: `${{formatCount(s.dropped)}} dropped`,
          tooltip: 'Shows the number of sites that have been dropped out of the number of sites installed for the selected time period and filters.'
        }},
        {{
          label: 'Returned Rate',
          value: pct(s.returned, s.installed),
          note: `${{formatCount(s.returned)}} returned`,
          tooltip: 'Shows the number of sites that returned after being dropped out of the number of sites installed for the selected time period and filters.'
        }},
        {{
          label: 'Re-engaged with cadence',
          value: pct(s.reengagedWithCadence, s.total),
          note: `${{formatCount(s.reengagedWithCadence)}} re-engaged`,
          tooltip: 'Shows the number of sites that received any follow-up cadence or Creator Growth escalation and ultimately ended as Installed or Returned, out of all sites matching the current filters.'
        }},
        {{
          label: 'Rise creators',
          value: pct(s.rise, s.total),
          note: `${{formatCount(s.rise)}} Rise sites`,
          tooltip: 'Shows the number of Rise service-level sites out of all sites matching the current filters.'
        }}
      ];
      document.getElementById('kpis').innerHTML = tiles.map(tile => `
        <div class="tile" tabindex="0" aria-label="${{escapeAttr(`${{tile.label}}. ${{tile.tooltip}}`)}}" data-tooltip="${{escapeAttr(tile.tooltip)}}">
          <div class="label">${{escapeHtml(tile.label)}} <span class="info-dot" aria-hidden="true">?</span></div>
          <div class="value">${{escapeHtml(tile.value)}}</div>
          <div class="note">${{escapeHtml(tile.note)}}</div>
        </div>
      `).join('');
    }}

    function statusClass(outcome) {{
      if (outcome === 'Dropped') return 'status no';
      if (outcome === 'Returned') return 'status warn';
      if (outcome === 'Onboarding') return 'status progress';
      return 'status';
    }}

    function cgLabel(row) {{
      return hasEscalatedToCg(row) ? 'Escalated to CG' : 'Not Escalated to CG';
    }}

    function cgDisplayValue(row) {{
      const involvement = clean(row.cg_involvement);
      if (involvement) return involvement;
      return hasEscalatedToCg(row) ? 'Escalated to CG' : 'None';
    }}

    function activityDateValue(row) {{
      const dates = [row.returned_date, row.install_date, row.dropped_date]
        .map(value => dateSortValue(value))
        .filter(value => value > 0);
      return dates.length ? Math.max(...dates) : 0;
    }}

    function displayValue(row, key) {{
      if (key === 'lead') return display(row.lead_contact || row.company_name);
      if (key === 'reason_category') return reasonCategoryValue(row);
      if (key === 'reason') return reasonValue(row);
      if (key === 'macro_cadence') return cadenceValue(row);
      if (key === 'cg_involvement') return display(cgDisplayValue(row));
      if (key === 'onboarding_owner') return ownerValue(row);
      if (key === 'returned_reason') return display(row.returned_reason);
      if (key === 'activity_date') return String(activityDateValue(row));
      if (key === 'zendesk_context') return hasZendeskContextPage(row) ? 'View context' : 'N/A';
      return display(row[key]);
    }}

    function dateSortValue(value) {{
      const valueText = clean(value);
      if (!valueText) return 0;
      const parsed = Date.parse(valueText);
      return Number.isFinite(parsed) ? parsed : 0;
    }}

    function sortValue(row, key) {{
      if (key === 'dropped_date' || key === 'returned_date' || key === 'install_date') return dateSortValue(row[key]);
      if (key === 'activity_date') return activityDateValue(row);
      return displayValue(row, key).toLowerCase();
    }}

    function sortRows(rows) {{
      return [...rows].sort((a, b) => {{
        const left = sortValue(a, sortState.key);
        const right = sortValue(b, sortState.key);
        let comparison = typeof left === 'number' && typeof right === 'number'
          ? left - right
          : String(left).localeCompare(String(right), undefined, {{ numeric: true, sensitivity: 'base' }});
        if (comparison === 0) comparison = display(a.creator_project_name).localeCompare(display(b.creator_project_name), undefined, {{ sensitivity: 'base' }});
        return sortState.direction === 'asc' ? comparison : -comparison;
      }});
    }}

    function updateSortIndicators() {{
      document.querySelectorAll('.sort-button').forEach(button => {{
        const active = button.dataset.sort === sortState.key;
        button.setAttribute('aria-sort', active ? (sortState.direction === 'asc' ? 'ascending' : 'descending') : 'none');
        const indicator = button.querySelector('.sort-indicator');
        if (indicator) indicator.textContent = active ? (sortState.direction === 'asc' ? '▲' : '▼') : '';
      }});
    }}

    function outcomePill(row) {{
      const value = display(row.outcome);
      return `<span class="${{statusClass(value)}}">${{escapeHtml(value)}}</span>`;
    }}

    function rowDetails(row) {{
      const parts = [
        clean(row.current_status) ? `Current status: ${{row.current_status}}` : '',
        clean(row.install_history) ? `Install history: ${{row.install_history}}` : '',
        clean(row.dropped_dates) ? `Dropped history: ${{row.dropped_dates}}` : ''
      ].filter(Boolean);
      return parts.join('\\n');
    }}

    function currentPageSize() {{
      const value = Number(actions.pageSize.value);
      return Number.isFinite(value) && value > 0 ? value : 100;
    }}

    function pageCount(totalRows) {{
      return Math.max(1, Math.ceil(totalRows / currentPageSize()));
    }}

    function clampTablePage(totalRows) {{
      tableState.pageSize = currentPageSize();
      tableState.page = Math.min(Math.max(tableState.page, 1), pageCount(totalRows));
    }}

    function visiblePageRows(rows) {{
      clampTablePage(rows.length);
      const start = (tableState.page - 1) * tableState.pageSize;
      return {{
        start,
        rows: rows.slice(start, start + tableState.pageSize)
      }};
    }}

    function renderPagination(totalRows, start, visibleCount) {{
      const totalPages = pageCount(totalRows);
      actions.prevPage.disabled = tableState.page <= 1 || totalRows === 0;
      actions.nextPage.disabled = tableState.page >= totalPages || totalRows === 0;
      if (!totalRows) {{
        actions.pageStatus.textContent = '0 of 0';
        return;
      }}
      const first = start + 1;
      const last = start + visibleCount;
      actions.pageStatus.textContent = `${{formatCount(first)}}-${{formatCount(last)}} of ${{formatCount(totalRows)}}`;
    }}

    function renderFromFirstPage() {{
      tableState.page = 1;
      render();
    }}

    function renderTable(rows) {{
      document.getElementById('row-count').textContent = `${{formatCount(rows.length)}} records`;
      const tbody = document.getElementById('creator-rows');
      const showReturnedReason = actions.returnedReasonToggle.checked;
      document.querySelectorAll('.returned-reason-col').forEach(cell => {{
        cell.classList.toggle('hidden-col', !showReturnedReason);
      }});
      if (!rows.length) {{
        renderPagination(0, 0, 0);
        tbody.innerHTML = `<tr class="empty-row"><td colspan="${{showReturnedReason ? 16 : 15}}">No records match the current filters.</td></tr>`;
        return;
      }}
      const page = visiblePageRows(rows);
      renderPagination(rows.length, page.start, page.rows.length);
      tbody.innerHTML = page.rows.map((row, index) => `
        <tr>
          <td class="number-col">${{page.start + index + 1}}</td>
          <td>
            <strong>${{escapeHtml(display(row.creator_project_name))}}</strong>
            ${{number(row.drop_count) > 1 ? `<div class="cell-note">${{number(row.drop_count)}} dropped attempts</div>` : ''}}
          </td>
          <td>${{escapeHtml(display(row.lead_contact || row.company_name))}}</td>
          <td>${{escapeHtml(display(row.service_level))}}</td>
          <td>${{escapeHtml(display(row.vertical))}}</td>
          <td>${{escapeHtml(display(row.previous_ad_network))}}</td>
          <td>${{escapeHtml(ownerValue(row))}}</td>
          <td title="${{escapeAttr(rowDetails(row))}}">${{escapeHtml(display(row.dropped_date))}}</td>
          <td>${{escapeHtml(reasonCategoryValue(row))}}</td>
          <td title="${{escapeAttr(row.raw_description || row.cancellation_reason || row.dropped_reason)}}">${{escapeHtml(reasonValue(row))}}</td>
          <td>${{zendeskContextCell(row)}}</td>
          <td>${{cadencePills(row)}}</td>
          <td>${{escapeHtml(display(cgDisplayValue(row)))}}</td>
          <td>${{escapeHtml(display(row.returned_date))}}</td>
          <td title="${{escapeAttr(rowDetails(row))}}">${{outcomePill(row)}}</td>
          <td class="returned-reason-col ${{showReturnedReason ? '' : 'hidden-col'}}">${{escapeHtml(display(row.returned_reason))}}</td>
        </tr>
      `).join('');
    }}

    function render() {{
      const rows = sortRows(filtered());
      renderKpis(rows);
      const service = fixedCounts(rows, SERVICE_LEVELS, row => optionValue(row.service_level));
      const reasons = groupCounts(rows.filter(isDropped), row => reasonValue(row), 10);
      const cg = fixedCounts(rows, ['Escalated to CG', 'Not Escalated to CG'], row => cgLabel(row));
      const networks = groupCounts(rows, row => previousNetworkValue(row.previous_ad_network), 10);
      renderBars('service-bars', service);
      renderBars('reason-bars', reasons, 'amber');
      renderBars('cg-bars', cg, 'blue');
      renderBars('network-bars', networks, 'rose');
      document.getElementById('service-count').textContent = `${{service.length}} groups`;
      document.getElementById('reason-count').textContent = `${{reasons.length}} groups`;
      document.getElementById('cg-count').textContent = `${{cg.length}} groups`;
      document.getElementById('network-count').textContent = `${{networks.length}} groups`;
      renderTable(rows);
      updateSortIndicators();
    }}

    const CSV_COLUMNS = [
      ['#', (_row, index) => index + 1],
      ['Site Name', row => display(row.creator_project_name)],
      ['Creator Name', row => display(row.lead_contact || row.company_name)],
      ['Service Level', row => display(row.service_level)],
      ['Vertical', row => display(row.vertical)],
      ['Previous Ad Network', row => display(row.previous_ad_network)],
      ['Onboarding Owner', row => ownerValue(row)],
      ['Dropped Date', row => display(row.dropped_date)],
      ['Dropped Reason Category', row => reasonCategoryValue(row)],
      ['Dropped Reason', row => reasonValue(row)],
      ['Zendesk Context', row => hasZendeskContextPage(row) ? zendeskContextHref(row) : 'N/A'],
      ['Follow-Up Cadence', row => cadenceValue(row)],
      ['CG Involvement', row => display(cgDisplayValue(row))],
      ['Returned Date', row => display(row.returned_date)],
      ['Outcome', row => display(row.outcome)],
      ['Returned Reason', row => display(row.returned_reason)]
    ];

    function csvEscape(value) {{
      const raw = text(value).replace(/\\r?\\n/g, ' ');
      if (/[",\\n]/.test(raw)) return `"${{raw.replace(/"/g, '""')}}"`;
      return raw;
    }}

    function exportCsv() {{
      const rows = sortRows(filtered());
      const header = CSV_COLUMNS.map(([label]) => csvEscape(label)).join(',');
      const body = rows.map((row, index) => CSV_COLUMNS.map(([, getter]) => csvEscape(getter(row, index))).join(','));
      const blob = new Blob([[header, ...body].join('\\n')], {{ type: 'text/csv;charset=utf-8;' }});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `site-retention-analysis-${{new Date().toISOString().slice(0, 10)}}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    }}

    function resetFilters() {{
      fields.search.value = '';
      fields.installedYear.value = '';
      fields.outcome.value = '';
      fields.service.value = '';
      fields.previousNetwork.value = '';
      fields.vertical.value = '';
      fields.owner.value = '';
      fields.reasonCategory.value = '';
      fields.reason.value = '';
      document.querySelectorAll('input[name="cadence-day"]').forEach(input => {{ input.checked = false; }});
      actions.returnedReasonToggle.checked = false;
      actions.pageSize.value = '100';
      tableState.page = 1;
      tableState.pageSize = 100;
      sortState.key = 'activity_date';
      sortState.direction = 'desc';
      populateReasonSelect();
      render();
    }}

    populateFilters();
    filterControls.forEach(control => control.addEventListener('input', renderFromFirstPage));
    filterControls.forEach(control => control.addEventListener('change', renderFromFirstPage));
    fields.reasonCategory.addEventListener('change', () => {{
      populateReasonSelect();
      renderFromFirstPage();
    }});
    actions.pageSize.addEventListener('change', () => {{
      tableState.page = 1;
      tableState.pageSize = currentPageSize();
      render();
    }});
    actions.prevPage.addEventListener('click', () => {{
      tableState.page = Math.max(1, tableState.page - 1);
      render();
    }});
    actions.nextPage.addEventListener('click', () => {{
      tableState.page = tableState.page + 1;
      render();
    }});
    actions.returnedReasonToggle.addEventListener('change', render);
    actions.reset.addEventListener('click', resetFilters);
    actions.exportCsv.addEventListener('click', exportCsv);
    document.querySelectorAll('.sort-button').forEach(button => {{
      button.addEventListener('click', () => {{
        const key = button.dataset.sort;
        if (sortState.key === key) {{
          sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
        }} else {{
          sortState.key = key;
          sortState.direction = ['dropped_date', 'returned_date', 'install_date', 'activity_date'].includes(key) ? 'desc' : 'asc';
        }}
        renderFromFirstPage();
      }});
    }});
    render();
  </script>
</body>
</html>
"""


def render_context_html(records: list[dict[str, object]], generated_at: str) -> str:
    data_json = json.dumps(records, ensure_ascii=False)
    generated = html.escape(generated_at)
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zendesk Context - Site Retention Analysis</title>
  <style>
    :root {
      --bg: #F0EDEB;
      --surface: #FFFFFF;
      --line: #E1DAD4;
      --text: #000000;
      --muted: #354786;
      --brand: #6B65FF;
      --brand-soft: #F0F0FF;
      --spark: #D2FF66;
      --pink: #ECB5D2;
      --orange: #FF7858;
      --green: #00785D;
      --red: #A23B4C;
      --blue: #354786;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Roobert Pro", "DM Sans", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.45;
    }
    header {
      border-bottom: 1px solid var(--line);
      border-top: 6px solid var(--brand);
      background: var(--brand-soft);
      padding: 26px 32px 22px;
    }
    .title-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      flex-wrap: wrap;
    }
    .eyebrow {
      color: var(--green);
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    h1 {
      margin: 0;
      font-size: 42px;
      line-height: 1.15;
      font-weight: 720;
    }
    .subtitle {
      color: var(--muted);
      margin-top: 10px;
      max-width: 980px;
    }
    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 32px 40px;
    }
    .button {
      border: 1px solid var(--green);
      border-radius: 6px;
      background: var(--green);
      color: var(--surface);
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      padding: 10px 16px;
      text-decoration: none;
      font-weight: 760;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
      padding: 18px;
    }
    .panel-header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    h2 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
    }
    h3 {
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 14px;
      text-transform: uppercase;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 84px;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      text-transform: uppercase;
    }
    .metric .value {
      margin-top: 7px;
      font-size: 17px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }
    .summary {
      font-size: 19px;
      line-height: 1.45;
    }
    .theme-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .theme-box {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 130px;
    }
    .pill {
      display: inline-flex;
      border-radius: 999px;
      background: var(--brand-soft);
      color: var(--blue);
      font-size: 12px;
      font-weight: 760;
      margin: 0 5px 6px 0;
      padding: 4px 8px;
    }
    .pill.warn {
      background: var(--spark);
      color: var(--text);
    }
    .pill.no {
      background: var(--red);
      color: var(--surface);
    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      font: inherit;
      min-height: 48px;
      padding: 12px 14px;
    }
    select {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      font: inherit;
      min-height: 38px;
      padding: 6px 30px 6px 10px;
    }
    .list-controls {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: end;
    }
    .pagination-controls {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .page-size {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
      white-space: nowrap;
    }
    .pager-button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 760;
      min-height: 38px;
      padding: 7px 10px;
    }
    .pager-button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }
    .page-status {
      color: var(--muted);
      font-size: 13px;
      min-width: 132px;
      text-align: center;
      white-space: nowrap;
    }
    .table-wrap {
      overflow: auto;
      max-height: 640px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 12px;
      text-align: left;
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      background: var(--brand-soft);
      color: var(--muted);
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
    }
    td {
      font-size: 14px;
    }
    .site-link {
      color: var(--green);
      font-weight: 760;
      text-decoration: none;
    }
    .site-link:hover {
      text-decoration: underline;
    }
    .empty {
      color: var(--muted);
      padding: 20px 0;
    }
    @media (max-width: 900px) {
      header, main { padding-left: 16px; padding-right: 16px; }
      h1 { font-size: 34px; }
      .meta-grid, .theme-grid { grid-template-columns: 1fr; }
      .list-controls { grid-template-columns: 1fr; }
      .pagination-controls { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <header>
    <div class="title-row">
      <div>
        <div class="eyebrow">Zendesk Context</div>
        <h1>Site Retention Analysis</h1>
        <div class="subtitle">Dropped/cancelled onboarding context for 2026 sites. Generated __GENERATED__.</div>
      </div>
      <a class="button" href="index.html">Back to dashboard</a>
    </div>
  </header>

  <main id="app"></main>

  <script>
    const CONTEXT_RECORDS = __DATA__;
    const contextListState = { page: 1, pageSize: 100 };

    function text(value) {
      return (value ?? '').toString();
    }

    function clean(value) {
      return text(value).trim();
    }

    function display(value) {
      const valueText = clean(value);
      return valueText || 'N/A';
    }

    function escapeHtml(value) {
      return text(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]));
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, '&grave;');
    }

    function statusPill(value) {
      const label = display(value);
      const className = label === 'True' || label === 'true' ? 'pill warn' : label === 'False' || label === 'false' ? 'pill no' : 'pill';
      return `<span class="${className}">${escapeHtml(label)}</span>`;
    }

    function splitThemes(value) {
      return clean(value).split(';').map(item => item.trim()).filter(Boolean);
    }

    function themePills(value) {
      const themes = splitThemes(value);
      if (!themes.length) return '<span class="pill">N/A</span>';
      return themes.map(theme => `<span class="pill">${escapeHtml(theme)}</span>`).join('');
    }

    function findSelectedRecord() {
      const params = new URLSearchParams(window.location.search);
      const siteId = clean(params.get('site_id'));
      const siteName = clean(params.get('site_name')).toLowerCase();
      if (siteId) {
        const match = CONTEXT_RECORDS.find(record => clean(record.site_id) === siteId);
        if (match) return match;
      }
      if (siteName) {
        const match = CONTEXT_RECORDS.find(record => clean(record.site_name).toLowerCase() === siteName);
        if (match) return match;
      }
      return null;
    }

    function renderMetric(label, value) {
      return `
        <div class="metric">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(display(value))}</div>
        </div>
      `;
    }

    function renderDetail(record) {
      return `
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2>${escapeHtml(display(record.site_name))}</h2>
              <div class="subtitle">${escapeHtml(display(record.domain))}</div>
            </div>
            <div>${statusPill(record.outcome)}</div>
          </div>
          <div class="meta-grid">
            ${renderMetric('Creator', record.creator_name)}
            ${renderMetric('Dropped Date', record.dropped_date)}
            ${renderMetric('Dropped Reason Category', record.dropped_reason_category)}
            ${renderMetric('Dropped Reason', record.dropped_reason)}
            ${renderMetric('Service Level', record.service_level)}
            ${renderMetric('Vertical', record.vertical)}
            ${renderMetric('Previous Ad Network', record.previous_ad_network)}
            ${renderMetric('Onboarding Owner', record.onboarding_owner)}
            ${renderMetric('Zendesk Tickets', record.zendesk_ticket_count)}
            ${renderMetric('Ticket IDs', record.zendesk_ticket_ids)}
            ${renderMetric('Sentiment', record.sentiment)}
            ${renderMetric('Milestone Stage', record.milestone_stage)}
          </div>
        </section>
        <section class="panel">
          <h2>Context Summary</h2>
          <p class="summary">${escapeHtml(display(record.context_summary))}</p>
          ${clean(record.zendesk_summary) ? `<p>${escapeHtml(record.zendesk_summary)}</p>` : ''}
        </section>
        <section class="panel">
          <div class="theme-grid">
            <div class="theme-box">
              <h3>Cancellation & Ghosting</h3>
              ${themePills(record.cancellation_ghosting_themes)}
            </div>
            <div class="theme-box">
              <h3>Communication & Sentiment</h3>
              ${themePills(record.communication_themes)}
            </div>
            <div class="theme-box">
              <h3>Drop-off & Community Growth</h3>
              ${themePills(record.dropoff_cg_themes)}
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="meta-grid">
            ${renderMetric('CG Involvement', record.cg_involvement)}
            ${renderMetric('CG Escalated', record.cg_escalation_status)}
            ${renderMetric('CG First Touch', record.cg_first_touch_at)}
            ${renderMetric('CG Days From Drop', record.cg_days_from_drop)}
          </div>
        </section>
      `;
    }

    function recordHref(record) {
      return `zendesk_context.html?site_id=${encodeURIComponent(clean(record.site_id))}`;
    }

    function renderList(records) {
      if (!records.length) {
        return '<div class="empty">No 2026 dropped/cancelled context records are available.</div>';
      }
      return `
        <section class="panel">
          <div class="panel-header">
            <h2>2026 Dropped/Cancelled Sites</h2>
            <span>${records.length.toLocaleString()} records</span>
          </div>
          <div class="list-controls">
            <input id="search" type="search" placeholder="Search site, creator, owner, reason, or context">
            <div class="pagination-controls" aria-label="Context pagination">
              <label class="page-size">Rows
                <select id="context-page-size">
                  <option value="50">50</option>
                  <option value="100" selected>100</option>
                  <option value="250">250</option>
                </select>
              </label>
              <button class="pager-button" type="button" id="context-prev-page">Previous</button>
              <span class="page-status" id="context-page-status"></span>
              <button class="pager-button" type="button" id="context-next-page">Next</button>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Site</th>
                  <th>Dropped</th>
                  <th>Reason</th>
                  <th>Sentiment</th>
                  <th>Milestone</th>
                  <th>Tickets</th>
                  <th>Context</th>
                </tr>
              </thead>
              <tbody id="context-rows"></tbody>
            </table>
          </div>
        </section>
      `;
    }

    function contextPageSize() {
      const select = document.getElementById('context-page-size');
      const value = Number(select ? select.value : contextListState.pageSize);
      return Number.isFinite(value) && value > 0 ? value : 100;
    }

    function contextPageCount(totalRows) {
      return Math.max(1, Math.ceil(totalRows / contextPageSize()));
    }

    function contextFilteredRows(records) {
      const input = document.getElementById('search');
      const query = clean(input ? input.value : '').toLowerCase();
      if (!query) return records;
      return records.filter(record => [
        record.site_name,
        record.creator_name,
        record.onboarding_owner,
        record.dropped_reason,
        record.dropped_reason_category,
        record.context_summary,
        record.sentiment,
        record.milestone_stage
      ].map(text).join(' ').toLowerCase().includes(query));
    }

    function updateContextPagination(totalRows, start, visibleCount) {
      const prev = document.getElementById('context-prev-page');
      const next = document.getElementById('context-next-page');
      const status = document.getElementById('context-page-status');
      if (!prev || !next || !status) return;
      const totalPages = contextPageCount(totalRows);
      prev.disabled = contextListState.page <= 1 || totalRows === 0;
      next.disabled = contextListState.page >= totalPages || totalRows === 0;
      if (!totalRows) {
        status.textContent = '0 of 0';
        return;
      }
      status.textContent = `${(start + 1).toLocaleString()}-${(start + visibleCount).toLocaleString()} of ${totalRows.toLocaleString()}`;
    }

    function renderRows(records) {
      const tbody = document.getElementById('context-rows');
      if (!tbody) return;
      contextListState.pageSize = contextPageSize();
      contextListState.page = Math.min(Math.max(contextListState.page, 1), contextPageCount(records.length));
      const start = (contextListState.page - 1) * contextListState.pageSize;
      const pageRows = records.slice(start, start + contextListState.pageSize);
      updateContextPagination(records.length, start, pageRows.length);
      if (!pageRows.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty">No context records match the current search.</td></tr>';
        return;
      }
      tbody.innerHTML = pageRows.map(record => `
        <tr>
          <td><a class="site-link" href="${escapeAttr(recordHref(record))}">${escapeHtml(display(record.site_name))}</a></td>
          <td>${escapeHtml(display(record.dropped_date))}</td>
          <td>${escapeHtml(display(record.dropped_reason_category))}<div class="subtitle">${escapeHtml(display(record.dropped_reason))}</div></td>
          <td>${escapeHtml(display(record.sentiment))}</td>
          <td>${escapeHtml(display(record.milestone_stage))}</td>
          <td>${escapeHtml(display(record.zendesk_ticket_count))}</td>
          <td>${escapeHtml(display(record.context_summary))}</td>
        </tr>
      `).join('');
    }

    function wireSearch(records) {
      const input = document.getElementById('search');
      if (!input) return;
      input.addEventListener('input', () => {
        contextListState.page = 1;
        renderRows(contextFilteredRows(records));
      });
    }

    function wireContextPagination(records) {
      const pageSize = document.getElementById('context-page-size');
      const prev = document.getElementById('context-prev-page');
      const next = document.getElementById('context-next-page');
      if (pageSize) {
        pageSize.addEventListener('change', () => {
          contextListState.page = 1;
          contextListState.pageSize = contextPageSize();
          renderRows(contextFilteredRows(records));
        });
      }
      if (prev) {
        prev.addEventListener('click', () => {
          contextListState.page = Math.max(1, contextListState.page - 1);
          renderRows(contextFilteredRows(records));
        });
      }
      if (next) {
        next.addEventListener('click', () => {
          contextListState.page = contextListState.page + 1;
          renderRows(contextFilteredRows(records));
        });
      }
    }

    function render() {
      const app = document.getElementById('app');
      const selected = findSelectedRecord();
      if (selected) {
        app.innerHTML = renderDetail(selected);
        return;
      }
      const params = new URLSearchParams(window.location.search);
      if (params.has('site_id') || params.has('site_name')) {
        app.innerHTML = `
          <section class="panel">
            <h2>Context Not Found</h2>
            <p class="empty">No Zendesk context row matched this site.</p>
          </section>
          ${renderList(CONTEXT_RECORDS)}
        `;
      } else {
        app.innerHTML = renderList(CONTEXT_RECORDS);
      }
      renderRows(CONTEXT_RECORDS);
      wireSearch(CONTEXT_RECORDS);
      wireContextPagination(CONTEXT_RECORDS);
    }

    render();
  </script>
</body>
</html>
"""
    return template.replace("__DATA__", data_json).replace("__GENERATED__", generated)


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    master_path = settings.output_dir / "master_creator_lifecycle.csv"
    if not master_path.exists():
        raise RuntimeError("master_creator_lifecycle.csv is missing. Run generate_outputs.py first.")
    master = read_csv(master_path)
    context = read_csv_if_exists(settings.output_dir / "zendesk_context_analysis.csv")
    records = prepare_records(master)
    context_records = prepare_context_records(context)
    html_output = render_html(records, datetime.now().strftime("%Y-%m-%d %H:%M"))
    context_html_output = render_context_html(context_records, datetime.now().strftime("%Y-%m-%d %H:%M"))

    output_path = settings.output_dir / "lifecycle_dashboard.html"
    output_path.write_text(html_output, encoding="utf-8")
    context_output_path = settings.output_dir / "zendesk_context.html"
    context_output_path.write_text(context_html_output, encoding="utf-8")

    pages_dir = settings.base_dir / "docs"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pages_path = pages_dir / "index.html"
    pages_path.write_text(html_output, encoding="utf-8")
    context_pages_path = pages_dir / "zendesk_context.html"
    context_pages_path.write_text(context_html_output, encoding="utf-8")
    (pages_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Wrote {output_path}")
    print(f"Wrote {context_output_path}")
    print(f"Wrote {pages_path}")
    print(f"Wrote {context_pages_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static HTML lifecycle dashboard.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
