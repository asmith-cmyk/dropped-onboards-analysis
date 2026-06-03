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
    "rescue_intervention_detected",
    "install_completed",
    "converted",
    "reengaged",
    "source_salesforce_dropped",
    "source_salesforce_returning",
}


REPORT_FIELDS = [
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
    "returning_owner",
    "monthly_pageviews",
    "dropped_status",
    "dropped_date",
    "returned_date",
    "days_to_return",
    "cancellation_reason",
    "dropped_reason",
    "dropped_reason_category",
    "macro_cadence",
    "zendesk_ticket_ids",
    "zendesk_ticket_created_dates",
    "zendesk_ticket_solved_dates",
    "cg_involvement",
    "cg_escalation_status",
    "install_completed",
    "converted",
    "reengaged",
    "outcome",
    "match_method",
    "match_score",
]


def to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def parsed_date(value: object) -> pd.Timestamp:
    return pd.to_datetime(clean_text(value), errors="coerce")


def display_date_list(values: list[object]) -> str:
    dates = sorted(
        {
            parsed.strftime("%Y-%m-%d")
            for parsed in (parsed_date(value) for value in values)
            if not pd.isna(parsed)
        }
    )
    return "; ".join(dates)


def first_present(rows: list[dict[str, object]], column: str) -> str:
    for row in rows:
        value = clean_text(row.get(column, ""))
        if value:
            return value
    return ""


def combined_present(rows: list[dict[str, object]], column: str) -> str:
    values = []
    for row in rows:
        value = clean_text(row.get(column, ""))
        if value and value not in values:
            values.append(value)
    return "; ".join(values)


def bool_any(rows: list[dict[str, object]], column: str) -> bool:
    return any(to_bool(row.get(column, False)) for row in rows)


def outcome_priority(value: object) -> int:
    normalized = clean_text(value).lower()
    if normalized == "re-engaged & installed":
        return 3
    if normalized == "returned":
        return 2
    if normalized == "dropped":
        return 1
    return 0


def combined_cadence(rows: list[dict[str, object]]) -> str:
    days = set()
    for row in rows:
        days.update(re.findall(r"\b(?:3|5|7|10)\b", clean_text(row.get("macro_cadence", ""))))
    return format_macro_cadence([day for day in ("3", "5", "7", "10") if day in days])


def display_days_to_return(dropped_date: str, returned_date: str, fallback: object) -> str:
    dropped = parsed_date(dropped_date)
    returned = parsed_date(returned_date)
    if pd.isna(dropped) or pd.isna(returned):
        return clean_text(fallback)
    return str(int((returned - dropped).days))


def collapse_returned_attempts(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Show one dashboard row when repeat drops share one lifecycle outcome.

    The master lifecycle CSV stays event-level. The dashboard is creator-level for
    sites, so multiple dropped attempts with the same return state are represented
    as one row with visible drop history.
    """
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    passthrough: list[dict[str, object]] = []

    for record in records:
        returned_date = clean_text(record.get("returned_date", ""))
        site_key = clean_text(record.get("site_id", ""))
        if not site_key:
            site_key = clean_text(record.get("salesforce_account_id", ""))
        if not site_key:
            site_key = clean_text(record.get("creator_key", "")) or clean_text(record.get("creator_project_name", "")).lower()

        if site_key:
            groups.setdefault((site_key, returned_date), []).append(record)
        else:
            passthrough.append(record)

    collapsed: list[dict[str, object]] = []
    for (_, returned_date), rows in groups.items():
        if len(rows) == 1:
            row = rows[0].copy()
            row["drop_count"] = 1
            row["dropped_dates"] = clean_text(row.get("dropped_date", ""))
            row["dropped_sort_date"] = clean_text(row.get("dropped_date", ""))
            row["first_dropped_date"] = clean_text(row.get("dropped_date", ""))
            row["latest_dropped_date"] = clean_text(row.get("dropped_date", ""))
            row["drop_history"] = clean_text(row.get("dropped_date", ""))
            collapsed.append(row)
            continue

        ordered = sorted(
            rows,
            key=lambda row: (
                pd.Timestamp.min if pd.isna(parsed_date(row.get("dropped_date", ""))) else parsed_date(row.get("dropped_date", "")),
                clean_text(row.get("salesforce_project_id", "")),
            ),
        )
        latest = ordered[-1].copy()
        date_list = display_date_list([row.get("dropped_date", "") for row in ordered])
        latest_drop = clean_text(ordered[-1].get("dropped_date", ""))
        first_drop = clean_text(ordered[0].get("dropped_date", ""))

        latest["drop_count"] = len({clean_text(row.get("dropped_date", "")) for row in ordered if clean_text(row.get("dropped_date", ""))})
        latest["dropped_dates"] = date_list
        latest["dropped_date"] = date_list or latest_drop
        latest["dropped_sort_date"] = latest_drop
        latest["first_dropped_date"] = first_drop
        latest["latest_dropped_date"] = latest_drop
        latest["days_to_return"] = display_days_to_return(latest_drop, returned_date, latest.get("days_to_return", ""))
        latest["macro_cadence"] = combined_cadence(ordered)
        latest["cg_involvement"] = "Assisted" if any(clean_text(row.get("cg_involvement", "")).lower() == "assisted" for row in ordered) else "Not Assisted"
        latest["install_completed"] = bool_any(ordered, "install_completed")
        latest["converted"] = bool_any(ordered, "converted")
        latest["reengaged"] = bool_any(ordered, "reengaged") or bool(returned_date)
        latest["outcome"] = max((clean_text(row.get("outcome", "")) for row in ordered), key=outcome_priority, default=clean_text(latest.get("outcome", "")))
        latest["lead_contact"] = first_present(list(reversed(ordered)), "lead_contact")
        latest["creator_project_name"] = first_present(list(reversed(ordered)), "creator_project_name")
        latest["onboarding_owner"] = combined_present(ordered, "onboarding_owner")
        latest["returning_owner"] = first_present(list(reversed(ordered)), "returning_owner")

        history_parts = []
        for row in ordered:
            date = clean_text(row.get("dropped_date", ""))
            owner = clean_text(row.get("onboarding_owner", ""))
            reason = (
                clean_text(row.get("dropped_reason", ""))
                or clean_text(row.get("dropped_reason_category", ""))
                or clean_text(row.get("cancellation_reason", ""))
            )
            cg = clean_text(row.get("cg_involvement", ""))
            details = " | ".join(part for part in (owner, reason, cg) if part)
            history_parts.append(f"{date}: {details}" if details else date)
        latest["drop_history"] = "\n".join(history_parts)
        collapsed.append(latest)

    for row in passthrough:
        row = row.copy()
        row["drop_count"] = 1
        row["dropped_dates"] = clean_text(row.get("dropped_date", ""))
        row["dropped_sort_date"] = clean_text(row.get("dropped_date", ""))
        row["first_dropped_date"] = clean_text(row.get("dropped_date", ""))
        row["latest_dropped_date"] = clean_text(row.get("dropped_date", ""))
        row["drop_history"] = clean_text(row.get("dropped_date", ""))
        collapsed.append(row)

    return collapsed


def prepare_records(master: pd.DataFrame) -> list[dict[str, object]]:
    available_fields = [field for field in REPORT_FIELDS if field in master.columns]
    records = master[available_fields].fillna("").to_dict(orient="records")
    for record in records:
        for column in BOOL_COLUMNS:
            if column in record:
                record[column] = to_bool(record[column])
        for key, value in list(record.items()):
            if not isinstance(value, bool):
                record[key] = "" if value is None else str(value)
    return collapse_returned_attempts(records)


def render_html(records: list[dict[str, object]], generated_at: str) -> str:
    data_json = json.dumps(records, ensure_ascii=False)
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
      --bg: #f7f7f4;
      --surface: #ffffff;
      --line: #d8d9d2;
      --text: #172026;
      --muted: #5d6770;
      --teal: #0f766e;
      --blue: #2563eb;
      --amber: #b45309;
      --rose: #be123c;
      --ink-soft: #eef0ec;
      --shadow: 0 1px 2px rgba(23, 32, 38, 0.06);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.4;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--surface);
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
      grid-template-columns: minmax(220px, 2fr) repeat(6, minmax(130px, 1fr));
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
    .control-group {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    .control-title {{
      display: block;
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
      accent-color: var(--teal);
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
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
    .tile.has-tooltip {{
      cursor: help;
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
      color: #25313a;
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
      background: var(--teal);
      border-radius: 999px;
    }}
    .bar-fill.blue {{ background: var(--blue); }}
    .bar-fill.amber {{ background: var(--amber); }}
    .bar-fill.rose {{ background: var(--rose); }}
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
      border-bottom: 1px solid #eceee8;
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
      background: #fbfbf9;
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
      color: var(--teal);
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
      background: #edf7f4;
      color: #0f5f58;
      white-space: nowrap;
    }}
    .status.no {{
      background: #f3f4f0;
      color: #687078;
    }}
    .status.warn {{
      background: #fff4df;
      color: #8a4b08;
    }}
    .cell-note {{
      margin-top: 3px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
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
        <div class="subtitle">{total} dropped onboarding creators · Generated {generated}</div>
      </div>
      <div class="subtitle">Source: outputs/master_creator_lifecycle.csv</div>
    </div>
  </header>

  <main>
    <section class="controls" aria-label="Filters">
      <label>Search
        <input id="search" type="search" placeholder="Creator, lead, owner, reason">
      </label>
      <label>Returned Year
        <select id="year"></select>
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
        <span class="control-title">Cadence</span>
        <div class="cadence-options" id="cadence-options" role="group" aria-label="Cadence follow-up days">
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="3">3 day</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="5">5 day</label>
          <label class="cadence-option"><input type="checkbox" name="cadence-day" value="7">7 day</label>
        </div>
      </div>
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
        <h2>Dropped Onboard Sites</h2>
        <span class="subtitle" id="row-count"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="number-col">#</th>
              <th><button class="sort-button" type="button" data-sort="creator_project_name">Creator <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="lead">Lead <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="service_level">Service <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="vertical">Vertical <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="previous_ad_network">Network <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="onboarding_owner">Owner <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="dropped_date">Dropped <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="reason">Dropped Reason <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="macro_cadence">Cadence <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="cg_involvement">CG Involvement <span class="sort-indicator"></span></button></th>
              <th><button class="sort-button" type="button" data-sort="returned_date">Returned <span class="sort-indicator"></span></button></th>
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
    const sortState = {{ key: 'dropped_date', direction: 'asc' }};

    const fields = {{
      search: document.getElementById('search'),
      year: document.getElementById('year'),
      service: document.getElementById('service'),
      vertical: document.getElementById('vertical'),
      owner: document.getElementById('owner'),
      cadenceOptions: document.getElementById('cadence-options'),
      reason: document.getElementById('reason')
    }};

    function text(value) {{
      return (value ?? '').toString();
    }}

    function truthy(value) {{
      return value === true || ['true', '1', 'yes', 'y'].includes(text(value).toLowerCase());
    }}

    function pct(part, total) {{
      return total ? `${{Math.round((part / total) * 1000) / 10}}%` : '0%';
    }}

    function number(value) {{
      const n = Number(String(value).replace(/,/g, ''));
      return Number.isFinite(n) ? n : 0;
    }}

    function optionValue(value) {{
      const clean = text(value).trim();
      return clean || 'Unknown';
    }}

    function cadenceValue(value) {{
      const clean = text(value).trim();
      return clean && clean !== 'Unknown' ? clean : 'None';
    }}

    function cadenceDetail(row) {{
      const details = [
        row.zendesk_ticket_ids ? `Tickets: ${{row.zendesk_ticket_ids}}` : '',
        row.zendesk_ticket_created_dates ? `Created: ${{row.zendesk_ticket_created_dates}}` : '',
        row.zendesk_ticket_solved_dates ? `Solved: ${{row.zendesk_ticket_solved_dates}}` : ''
      ].filter(Boolean);
      return details.length ? details.join('\\n') : cadenceValue(row.macro_cadence);
    }}

    function cadenceHasDays(value, requiredDays) {{
      const days = new Set((text(value).match(/\\b(?:3|5|7|10)\\b/g) || []));
      return requiredDays.every(day => days.has(day));
    }}

    function cadenceHasAnyDays(value, targetDays) {{
      const days = new Set((text(value).match(/\\b(?:3|5|7|10)\\b/g) || []));
      return targetDays.some(day => days.has(day));
    }}

    function splitList(value) {{
      return text(value).split(';').map(item => item.trim()).filter(Boolean);
    }}

    function uniqueList(values) {{
      return [...new Set(values.filter(Boolean))];
    }}

    function ownerParts(row) {{
      return uniqueList([...splitList(row.onboarding_owner), ...splitList(row.returning_owner)]);
    }}

    function ownerValue(row) {{
      const owners = ownerParts(row);
      return owners.length ? owners.join('; ') : 'Unknown';
    }}

    function ownerDetail(row) {{
      const dropped = splitList(row.onboarding_owner).join('; ');
      const returning = splitList(row.returning_owner).join('; ');
      const details = [
        dropped ? `Dropped owner: ${{dropped}}` : '',
        returning ? `Returning owner: ${{returning}}` : ''
      ].filter(Boolean);
      return details.length ? details.join('\\n') : ownerValue(row);
    }}

    function yearValue(value) {{
      const clean = text(value).trim();
      if (!clean) return '';
      const parsed = new Date(clean);
      return Number.isNaN(parsed.getTime()) ? '' : String(parsed.getUTCFullYear());
    }}

    function dateInYear(value, year) {{
      const clean = text(value).trim();
      if (!clean || !year) return false;
      const parsed = new Date(clean);
      if (Number.isNaN(parsed.getTime())) return false;
      const start = Date.UTC(Number(year), 0, 1);
      const end = Date.UTC(Number(year) + 1, 0, 1);
      return parsed.getTime() >= start && parsed.getTime() < end;
    }}

    const GENERIC_REASON_VALUES = new Set(['Dropped', 'Canceled', 'Cancelled', 'Prior site dropped status']);
    const NO_DROPPED_REASON = 'No dropped reason captured';
    const NO_REASON_CATEGORY = 'No dropped reason category captured';

    function isUsefulReason(value) {{
      const clean = text(value).trim();
      return clean && !GENERIC_REASON_VALUES.has(clean);
    }}

    function reasonCategoryValue(row) {{
      const category = text(row.dropped_reason_category).trim();
      return isUsefulReason(category) ? category : NO_REASON_CATEGORY;
    }}

    function reasonValue(row) {{
      const reason = text(row.dropped_reason).trim();
      return isUsefulReason(reason) ? reason : NO_DROPPED_REASON;
    }}

    function reasonDetail(row) {{
      const details = [
        isUsefulReason(row.dropped_reason_category) ? `Dropped reason category: ${{text(row.dropped_reason_category)}}` : '',
        isUsefulReason(row.cancellation_reason) ? `Cancellation reason: ${{text(row.cancellation_reason)}}` : ''
      ].filter(Boolean);
      return details.length ? details.join('\\n') : reasonValue(row);
    }}

    function displayValue(row, key) {{
      if (key === 'lead') return text(row.lead_contact || row.company_name);
      if (key === 'reason') return reasonValue(row);
      if (key === 'macro_cadence') return cadenceValue(row.macro_cadence);
      if (key === 'cg_involvement') return text(row.cg_involvement || 'Not Assisted');
      if (key === 'onboarding_owner') return ownerValue(row);
      return text(row[key]);
    }}

    function dateSortValue(value) {{
      const clean = text(value).trim();
      if (!clean) return Number.POSITIVE_INFINITY;
      const parsed = Date.parse(clean);
      return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
    }}

    function sortValue(row, key) {{
      if (key === 'dropped_date') return dateSortValue(row.dropped_sort_date || row.latest_dropped_date || row.dropped_date);
      if (key === 'returned_date') return dateSortValue(row[key]);
      const value = displayValue(row, key).trim().toLowerCase();
      return value || 'zzzzzz';
    }}

    function sortMissing(row, key) {{
      if (key === 'dropped_date') return !text(row.dropped_sort_date || row.latest_dropped_date || row.dropped_date).trim();
      if (key === 'returned_date') return !text(row[key]).trim();
      const value = displayValue(row, key).trim();
      return !value || value === 'Unknown' || value === NO_DROPPED_REASON || value === NO_REASON_CATEGORY;
    }}

    function sortRows(rows) {{
      return [...rows].sort((a, b) => {{
        const leftMissing = sortMissing(a, sortState.key);
        const rightMissing = sortMissing(b, sortState.key);
        if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
        const left = sortValue(a, sortState.key);
        const right = sortValue(b, sortState.key);
        let comparison;
        if (typeof left === 'number' && typeof right === 'number') {{
          comparison = left - right;
        }} else {{
          comparison = String(left).localeCompare(String(right), undefined, {{ numeric: true, sensitivity: 'base' }});
        }}
        if (comparison === 0) {{
          comparison = text(a.creator_project_name).localeCompare(text(b.creator_project_name), undefined, {{ sensitivity: 'base' }});
        }}
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

    function populateSelect(id, key, formatter = optionValue) {{
      const select = document.getElementById(id);
      const values = [...new Set(RECORDS.map(row => formatter(row[key])))].sort((a, b) => a.localeCompare(b));
      select.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join('');
    }}

    function populateYearSelect() {{
      const select = fields.year;
      const values = [...new Set(RECORDS.map(row => yearValue(row.returned_date)).filter(Boolean))]
        .sort((a, b) => b.localeCompare(a));
      select.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join('');
    }}

    function populateReasonSelect() {{
      const values = [...new Set(RECORDS.map(row => reasonValue(row)))].sort((a, b) => a.localeCompare(b));
      fields.reason.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join('');
    }}

    function populateOwnerSelect() {{
      const values = uniqueList(RECORDS.flatMap(row => ownerParts(row))).sort((a, b) => a.localeCompare(b));
      fields.owner.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join('');
    }}

    function selectedCadenceDays() {{
      return [...document.querySelectorAll('input[name="cadence-day"]:checked')].map(input => input.value);
    }}

    function escapeHtml(value) {{
      return text(value).replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[char]));
    }}

    function escapeAttr(value) {{
      return escapeHtml(value).replace(/`/g, '&#096;');
    }}

    function filtered() {{
      const query = fields.search.value.trim().toLowerCase();
      return RECORDS.filter(row => {{
        if (fields.year.value && !dateInYear(row.returned_date, fields.year.value)) return false;
        if (fields.service.value && optionValue(row.service_level) !== fields.service.value) return false;
        if (fields.vertical.value && optionValue(row.vertical) !== fields.vertical.value) return false;
        if (fields.owner.value && !ownerParts(row).includes(fields.owner.value)) return false;
        const cadenceDays = selectedCadenceDays();
        if (cadenceDays.length && !cadenceHasAnyDays(row.macro_cadence, cadenceDays)) return false;
        if (fields.reason.value && reasonValue(row) !== fields.reason.value) return false;
        if (!query) return true;
        const haystack = [
          row.creator_project_name,
          row.lead_contact,
          row.company_name,
          row.site_id,
          row.onboarding_owner,
          row.returning_owner,
          row.dropped_reason,
          row.dropped_reason_category,
          row.cancellation_reason,
          row.zendesk_ticket_ids,
          row.zendesk_ticket_created_dates,
          row.zendesk_ticket_solved_dates,
          row.drop_history,
          row.dropped_status,
          row.dropped_date,
          row.returned_date,
          row.outcome,
          row.previous_ad_network,
          row.vertical,
          row.service_level
        ].map(text).join(' ').toLowerCase();
        return haystack.includes(query);
      }});
    }}

    function summarize(rows) {{
      const total = rows.length;
      const reengaged = rows.filter(row => truthy(row.reengaged)).length;
      const returnedWithCadence = rows.filter(row => truthy(row.reengaged) && cadenceHasAnyDays(row.macro_cadence, ['3', '5', '7'])).length;
      const rise = rows.filter(row => text(row.service_level).toLowerCase() === 'rise').length;
      return {{ total, reengaged, returnedWithCadence, rise }};
    }}

    function renderKpis(rows) {{
      const s = summarize(rows);
      const tiles = [
        {{ label: 'Dropped onboards', value: s.total, note: 'Filtered rows' }},
        {{ label: 'Returned', value: s.reengaged, note: pct(s.reengaged, s.total) }},
        {{
          label: 'Re-engaged & Installed',
          value: pct(s.returnedWithCadence, s.total),
          note: `${{s.returnedWithCadence}} of ${{s.total}} sites`,
          tooltip: 'Percentage of sites that received a 3, 5, or 7 day follow up and returned.'
        }},
        {{ label: 'Rise creators', value: s.rise, note: pct(s.rise, s.total) }}
      ];
      document.getElementById('kpis').innerHTML = tiles.map(tile => {{
        const tooltip = tile.tooltip ? ` title="${{escapeAttr(tile.tooltip)}}" aria-label="${{escapeAttr(`${{tile.label}}: ${{tile.tooltip}}`)}}"` : '';
        return `
        <div class="tile${{tile.tooltip ? ' has-tooltip' : ''}}"${{tooltip}}>
          <div class="label">${{escapeHtml(tile.label)}}</div>
          <div class="value">${{escapeHtml(tile.value)}}</div>
          <div class="note">${{escapeHtml(tile.note)}}</div>
        </div>
      `;
      }}).join('');
    }}

    function groupCounts(rows, key, limit = 8, formatter = optionValue) {{
      const counts = new Map();
      rows.forEach(row => {{
        const value = formatter(row[key], row);
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

    function statusPill(value, label = 'Yes') {{
      return truthy(value)
        ? `<span class="status">${{escapeHtml(label)}}</span>`
        : '<span class="status no">No</span>';
    }}

    function outcome(row) {{
      if (text(row.outcome).trim()) return `<span class="${{row.outcome === 'Dropped' ? 'status no' : row.outcome === 'Returned' ? 'status warn' : 'status'}}">${{escapeHtml(row.outcome)}}</span>`;
      if (truthy(row.install_completed) && cadenceHasDays(row.macro_cadence, ['3', '5', '7'])) {{
        return '<span class="status">Re-engaged &amp; Installed</span>';
      }}
      if (truthy(row.reengaged) || text(row.returned_date).trim()) return '<span class="status warn">Returned</span>';
      return '<span class="status no">Dropped</span>';
    }}

    function renderTable(rows) {{
      document.getElementById('row-count').textContent = `${{rows.length}} rows`;
      const tbody = document.getElementById('creator-rows');
      tbody.innerHTML = rows.map((row, index) => `
        <tr>
          <td class="number-col">${{index + 1}}</td>
          <td>
            <strong>${{escapeHtml(row.creator_project_name)}}</strong>
            ${{number(row.drop_count) > 1 ? `<div class="cell-note">${{number(row.drop_count)}} dropped attempts</div>` : ''}}
          </td>
          <td>${{escapeHtml(row.lead_contact || row.company_name)}}</td>
          <td>${{escapeHtml(row.service_level || 'Unknown')}}</td>
          <td>${{escapeHtml(row.vertical || 'Unknown')}}</td>
          <td>${{escapeHtml(row.previous_ad_network || 'Unknown')}}</td>
          <td title="${{escapeAttr(ownerDetail(row))}}">${{escapeHtml(ownerValue(row))}}</td>
          <td title="${{escapeAttr(row.drop_history || row.dropped_date)}}">${{escapeHtml(row.dropped_date)}}</td>
          <td title="${{escapeAttr(reasonDetail(row))}}">${{escapeHtml(reasonValue(row))}}</td>
          <td title="${{escapeAttr(cadenceDetail(row))}}">${{escapeHtml(cadenceValue(row.macro_cadence))}}</td>
          <td>${{escapeHtml(row.cg_involvement || 'Not Assisted')}}</td>
          <td>${{escapeHtml(row.returned_date)}}</td>
          <td>${{outcome(row)}}</td>
        </tr>
      `).join('');
    }}

    function render() {{
      const rows = sortRows(filtered());
      renderKpis(rows);
      renderBars('service-bars', groupCounts(rows, 'service_level'), '');
      renderBars('reason-bars', groupCounts(rows, 'dropped_reason', 8, (_value, row) => reasonValue(row)), 'amber');
      renderBars('cg-bars', groupCounts(rows, 'cg_involvement'), 'blue');
      renderBars('network-bars', groupCounts(rows, 'previous_ad_network'), 'rose');
      document.getElementById('service-count').textContent = `${{groupCounts(rows, 'service_level', 50).length}} segments`;
      document.getElementById('reason-count').textContent = `${{groupCounts(rows, 'dropped_reason', 50, (_value, row) => reasonValue(row)).length}} reasons`;
      document.getElementById('cg-count').textContent = `${{groupCounts(rows, 'cg_involvement', 50).length}} groups`;
      document.getElementById('network-count').textContent = `${{groupCounts(rows, 'previous_ad_network', 50).length}} networks`;
      renderTable(rows);
      updateSortIndicators();
    }}

    populateYearSelect();
    populateSelect('service', 'service_level');
    populateSelect('vertical', 'vertical');
    populateOwnerSelect();
    populateReasonSelect();
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
