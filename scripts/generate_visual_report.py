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
from utils.io import read_csv
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

FALLBACK_ALL_TIME_INSTALLED_SITE_COUNT = 9646


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
  <title>Onboarding Lifecycle Dashboard</title>
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
      font-size: 14px;
      line-height: 1.4;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      border-top: 6px solid var(--brand);
      background: var(--brand-soft);
      padding: 18px 28px 16px;
    }}
    .title-row {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 18px;
      flex-wrap: wrap;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
      letter-spacing: 0;
      font-weight: 720;
      color: var(--text);
    }}
    .subtitle {{
      color: var(--muted);
      margin-top: 5px;
      font-size: 13px;
    }}
    main {{
      padding: 20px 28px 32px;
      max-width: 1500px;
      margin: 0 auto;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(220px, 2fr) repeat(7, minmax(120px, 1fr));
      gap: 10px;
      align-items: end;
      margin-bottom: 16px;
    }}
    label {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      padding: 9px 10px;
      font: inherit;
      min-height: 38px;
    }}
    input:focus, select:focus {{
      border-color: var(--brand);
      outline: 2px solid var(--brand);
      outline-offset: 1px;
    }}
    .control-group {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    .cadence-options {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      padding: 5px 6px;
    }}
    .cadence-option {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: var(--text);
      background: var(--ink-soft);
      border-radius: 6px;
      padding: 4px 7px;
      font-size: 12px;
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
      gap: 10px;
      margin-bottom: 16px;
    }}
    .tile, .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .tile {{
      padding: 12px 13px;
      min-height: 82px;
    }}
    .tile .label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    .tile .value {{
      margin-top: 7px;
      font-size: 28px;
      line-height: 1;
      font-weight: 760;
      letter-spacing: 0;
      color: var(--blue);
    }}
    .tile .note {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }}
    .panel {{
      padding: 14px;
      min-height: 285px;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    h2 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .panel-header span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .bars {{
      display: grid;
      gap: 8px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(120px, 190px) 1fr 72px;
      gap: 10px;
      align-items: center;
    }}
    .bar-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text);
      font-size: 12px;
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
      font-size: 12px;
    }}
    .table-panel {{
      padding: 0;
      overflow: hidden;
    }}
    .table-header {{
      padding: 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 560px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1180px;
    }}
    th, td {{
      padding: 9px 10px;
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
      font-size: 11px;
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
      font-size: 12px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
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
    .cell-note {{
      margin-top: 3px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
      white-space: pre-line;
    }}
    .empty {{
      color: var(--muted);
      padding: 18px 0;
      font-size: 13px;
    }}
    @media (max-width: 1100px) {{
      .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .controls, .kpis {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 110px 1fr 56px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-row">
      <div>
        <h1>Onboarding Lifecycle Dashboard</h1>
        <div class="subtitle">{total} sites · Generated {generated}</div>
      </div>
    </div>
  </header>

  <main>
    <section class="controls" aria-label="Filters">
      <label>Search
        <input id="search" type="search" placeholder="Site Name, Site Owner Name, Onboarding Owner, Dropped Reason">
      </label>
      <label>Returned Year
        <select id="returned-year"></select>
      </label>
      <label>Service Level
        <select id="service"></select>
      </label>
      <label>Vertical
        <select id="vertical"></select>
      </label>
      <label>Owner
        <select id="owner"></select>
      </label>
      <div class="control-group">
        <span>Cadence</span>
        <div class="cadence-options" id="cadence-options" role="group" aria-label="Cadence follow-up days">
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="3">3 day</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="5">5 day</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="7">7 day</label>
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
        <h2>Onboarding Lifecycle Sites</h2>
        <span class="subtitle" id="row-count"></span>
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
              <th><button class="sort-button" type="button" data-sort="previous_ad_network">Network <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="onboarding_owner">Owner <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="dropped_date">Dropped Date <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="reason_category">Dropped Reason Category <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="reason">Dropped Reason <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="macro_cadence">Follow-up Cadence <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="cg_involvement">CG Involvement <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="returned_date">Returned Date <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="outcome">Outcome <span class="sort-indicator"></span></button></th>
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
    const FALLBACK_ALL_TIME_INSTALLED_SITE_COUNT = {FALLBACK_ALL_TIME_INSTALLED_SITE_COUNT};
    const EVERYTHING_ELSE_REASON_OPTION = {{ category: 'Everything else', reason: 'Everything else' }};
    const REASON_OPTION_SEPARATOR = '::';
    const sortState = {{ key: 'dropped_date', direction: 'asc' }};
    const fields = {{
      search: document.getElementById('search'),
      returnedYear: document.getElementById('returned-year'),
      service: document.getElementById('service'),
      vertical: document.getElementById('vertical'),
      owner: document.getElementById('owner'),
      cadenceOptions: document.getElementById('cadence-options'),
      reasonCategory: document.getElementById('reason-category'),
      reason: document.getElementById('reason')
    }};

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

    function hasCadence(row, day) {{
      const cadenceText = clean(row.macro_cadence).toLowerCase();
      return truthy(row[`has_${{day}}_day_followup`]) || new RegExp(`\\\\b${{day}}\\\\b`).test(cadenceText);
    }}

    function cadenceValue(row) {{
      const days = ['3', '5', '7'].filter(day => hasCadence(row, day));
      if (!days.length) return 'None';
      if (days.length === 1) return `${{days[0]}} day follow up`;
      if (days.length === 2) return `${{days[0]}} and ${{days[1]}} day follow up`;
      return `${{days.slice(0, -1).join(', ')}} and ${{days[days.length - 1]}} day follow up`;
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

    function reasonOptionForRow(row) {{
      const categoryKey = taxonomyKey(row.dropped_reason_category);
      const candidates = [
        row.dropped_reason,
        row.normalized_dropped_reason,
        row.cancellation_reason
      ].map(clean).filter(Boolean);

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
      return reasonOptionKey(option.category, option.reason);
    }}

    function rowReasonCategoryFilterValue(row) {{
      return reasonOptionForRow(row).category;
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

    function populateReasonSelect() {{
      const options = DROPPED_REASON_GROUPS
        .map(group => {{
          const reasonOptions = group.reasons
            .map(reason => `<option value="${{escapeAttr(reasonOptionKey(group.category, reason))}}">${{escapeHtml(reason)}}</option>`)
            .join('');
          return `<optgroup label="${{escapeAttr(group.category)}}">${{reasonOptions}}</optgroup>`;
        }})
        .join('');
      fields.reason.innerHTML = '<option value="">All</option>' + options;
    }}

    function populateFilters() {{
      populateSelect(fields.returnedYear, [...new Set(RECORDS.map(row => yearValue(row, 'returned_year', 'returned_date')).filter(Boolean))].sort((a, b) => b.localeCompare(a)));
      populateSelect(fields.service, [...new Set(RECORDS.map(row => optionValue(row.service_level)))].sort((a, b) => a.localeCompare(b)));
      populateSelect(fields.vertical, [...new Set(RECORDS.map(row => optionValue(row.vertical)))].sort((a, b) => a.localeCompare(b)));
      populateSelect(fields.owner, [...new Set(RECORDS.flatMap(ownerParts))].sort((a, b) => a.localeCompare(b)));
      populateSelect(fields.reasonCategory, DROPPED_REASON_GROUPS.map(group => group.category));
      populateReasonSelect();
    }}

    function filtered() {{
      const query = fields.search.value.trim().toLowerCase();
      const cadenceDays = selectedCadenceDays();
      return RECORDS.filter(row => {{
        if (fields.returnedYear.value && yearValue(row, 'returned_year', 'returned_date') !== fields.returnedYear.value) return false;
        if (fields.service.value && optionValue(row.service_level) !== fields.service.value) return false;
        if (fields.vertical.value && optionValue(row.vertical) !== fields.vertical.value) return false;
        if (fields.owner.value && !ownerParts(row).includes(fields.owner.value)) return false;
        if (cadenceDays.length && !cadenceDays.some(day => hasCadence(row, day))) return false;
        if (fields.reasonCategory.value && rowReasonCategoryFilterValue(row) !== fields.reasonCategory.value) return false;
        if (fields.reason.value && rowReasonOptionKey(row) !== fields.reason.value) return false;
        if (!query) return true;
        const haystack = [
          row.creator_project_name,
          row.lead_contact,
          row.company_name,
          row.site_id,
          row.domain,
          row.onboarding_owner,
          row.previous_ad_network,
          row.current_status,
          row.dropped_reason,
          row.dropped_reason_category,
          row.normalized_dropped_reason,
          row.cancellation_reason,
          row.raw_description,
          row.dropped_dates,
          row.install_history,
          row.returned_date,
          row.outcome,
          row.vertical,
          row.service_level
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
          <div class="bar-row" title="${{escapeAttr(row.label)}}: ${{row.count}}">
            <div class="bar-label">${{escapeHtml(row.label)}}</div>
            <div class="bar-track"><div class="bar-fill ${{color}}" style="width: ${{width}}%"></div></div>
            <div class="bar-value">${{row.count}}</div>
          </div>
        `;
      }}).join('');
    }}

    function isDropped(row) {{
      return clean(row.outcome) === 'Dropped';
    }}

    function isInstalled(row) {{
      return truthy(row.install_completed)
        || truthy(row.converted)
        || Boolean(clean(row.install_date))
        || Boolean(clean(row.returned_date));
    }}

    function hasActiveRateFilter() {{
      return Boolean(
        clean(fields.search.value)
        || fields.returnedYear.value
        || fields.service.value
        || fields.vertical.value
        || fields.owner.value
        || selectedCadenceDays().length
        || fields.reasonCategory.value
        || fields.reason.value
      );
    }}

    function installedDenominator(rows) {{
      const installedRows = rows.filter(isInstalled).length;
      if (hasActiveRateFilter()) return installedRows;
      return RECORDS.length < FALLBACK_ALL_TIME_INSTALLED_SITE_COUNT
        ? FALLBACK_ALL_TIME_INSTALLED_SITE_COUNT
        : installedRows;
    }}

    function summarize(rows) {{
      const total = rows.length;
      const dropped = rows.filter(isDropped).length;
      const installed = installedDenominator(rows);
      const returned = rows.filter(row => clean(row.outcome) === 'Returned').length;
      const returnedWithCadence = rows.filter(row => clean(row.outcome) === 'Returned' && ['3', '5', '7'].some(day => hasCadence(row, day))).length;
      const rise = rows.filter(row => clean(row.service_level).toLowerCase() === 'rise').length;
      return {{ total, dropped, installed, returned, returnedWithCadence, rise }};
    }}

    function renderKpis(rows) {{
      const s = summarize(rows);
      const tiles = [
        {{ label: 'Sites', value: formatCount(s.total), note: 'Filtered rows' }},
        {{ label: 'Dropped rate', value: s.installed ? pct(s.dropped, s.installed) : 'N/A', note: `${{formatCount(s.dropped)}} dropped / ${{formatCount(s.installed)}} installed` }},
        {{ label: 'Returned', value: formatCount(s.returned), note: pct(s.returned, s.total) }},
        {{ label: 'Returned with cadence', value: pct(s.returnedWithCadence, s.total), note: `${{formatCount(s.returnedWithCadence)}} of ${{formatCount(s.total)}} sites` }},
        {{ label: 'Rise creators', value: formatCount(s.rise), note: pct(s.rise, s.total) }}
      ];
      document.getElementById('kpis').innerHTML = tiles.map(tile => `
        <div class="tile">
          <div class="label">${{escapeHtml(tile.label)}}</div>
          <div class="value">${{escapeHtml(tile.value)}}</div>
          <div class="note">${{escapeHtml(tile.note)}}</div>
        </div>
      `).join('');
    }}

    function statusClass(outcome) {{
      if (outcome === 'Dropped' || outcome === 'Inactive') return 'status no';
      if (outcome === 'Returned') return 'status warn';
      return 'status';
    }}

    function displayValue(row, key) {{
      if (key === 'lead') return display(row.lead_contact || row.company_name);
      if (key === 'reason_category') return reasonCategoryValue(row);
      if (key === 'reason') return reasonValue(row);
      if (key === 'macro_cadence') return cadenceValue(row);
      if (key === 'cg_involvement') return display(row.cg_involvement || 'Not Assisted');
      if (key === 'onboarding_owner') return ownerValue(row);
      return display(row[key]);
    }}

    function dateSortValue(value) {{
      const valueText = clean(value);
      if (!valueText) return Number.POSITIVE_INFINITY;
      const parsed = Date.parse(valueText);
      return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
    }}

    function sortValue(row, key) {{
      if (key === 'dropped_date' || key === 'returned_date') return dateSortValue(row[key]);
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

    function renderTable(rows) {{
      document.getElementById('row-count').textContent = `${{rows.length}} rows`;
      const tbody = document.getElementById('creator-rows');
      tbody.innerHTML = rows.map((row, index) => `
        <tr>
          <td class="number-col">${{index + 1}}</td>
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
          <td>${{escapeHtml(cadenceValue(row))}}</td>
          <td>${{escapeHtml(display(row.cg_involvement || 'Not Assisted'))}}</td>
          <td>${{escapeHtml(display(row.returned_date))}}</td>
          <td title="${{escapeAttr(rowDetails(row))}}">${{outcomePill(row)}}</td>
        </tr>
      `).join('');
    }}

    function render() {{
      const rows = sortRows(filtered());
      renderKpis(rows);
      const service = groupCounts(rows, row => optionValue(row.service_level));
      const reasons = groupCounts(rows, row => reasonValue(row));
      const cg = groupCounts(rows, row => display(row.cg_involvement || 'Not Assisted'));
      const networks = groupCounts(rows, row => optionValue(row.previous_ad_network));
      renderBars('service-bars', service);
      renderBars('reason-bars', reasons, 'amber');
      renderBars('cg-bars', cg, 'blue');
      renderBars('network-bars', networks, 'rose');
      document.getElementById('service-count').textContent = `${{groupCounts(rows, row => optionValue(row.service_level), 1000).length}} segments`;
      document.getElementById('reason-count').textContent = `${{groupCounts(rows, row => reasonValue(row), 1000).length}} reasons`;
      document.getElementById('cg-count').textContent = `${{groupCounts(rows, row => display(row.cg_involvement || 'Not Assisted'), 1000).length}} groups`;
      document.getElementById('network-count').textContent = `${{groupCounts(rows, row => optionValue(row.previous_ad_network), 1000).length}} networks`;
      renderTable(rows);
      updateSortIndicators();
    }}

    populateFilters();
    Object.values(fields).forEach(control => control.addEventListener('input', render));
    Object.values(fields).forEach(control => control.addEventListener('change', render));
    document.querySelectorAll('.sort-button').forEach(button => {{
      button.addEventListener('click', () => {{
        const key = button.dataset.sort;
        if (sortState.key === key) {{
          sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
        }} else {{
          sortState.key = key;
          sortState.direction = 'asc';
        }}
        render();
      }});
    }});
    render();
  </script>
</body>
</html>
"""


def run() -> Path:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)
    master_path = settings.output_dir / "master_creator_lifecycle.csv"
    if not master_path.exists():
        raise RuntimeError("master_creator_lifecycle.csv is missing. Run generate_outputs.py first.")
    master = read_csv(master_path)
    records = prepare_records(master)
    html_output = render_html(records, datetime.now().strftime("%Y-%m-%d %H:%M"))

    output_path = settings.output_dir / "lifecycle_dashboard.html"
    output_path.write_text(html_output, encoding="utf-8")

    pages_dir = settings.base_dir / "docs"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pages_path = pages_dir / "index.html"
    pages_path.write_text(html_output, encoding="utf-8")
    (pages_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Wrote {output_path}")
    print(f"Wrote {pages_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static HTML lifecycle dashboard.")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
