from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv


BOOL_COLUMNS = {
    "cg_escalation_status",
    "onboarding_call_offered",
    "salesloft_meeting_detected",
    "slack_intervention_detected",
    "rescue_intervention_detected",
    "install_completed",
    "converted",
    "reengaged",
    "source_salesforce_dropped",
    "source_salesforce_returning",
    "source_zendesk",
    "source_slack",
}


REPORT_FIELDS = [
    "creator_project_name",
    "lead_contact",
    "vertical",
    "service_level",
    "previous_ad_network",
    "onboarding_owner",
    "monthly_pageviews",
    "dropped_date",
    "returned_date",
    "days_to_return",
    "cancellation_reason",
    "normalized_reason",
    "macro_cadence",
    "cg_involvement",
    "cg_escalation_status",
    "cg_escalation_timing",
    "onboarding_call_offered",
    "salesloft_meeting_detected",
    "slack_intervention_detected",
    "install_completed",
    "converted",
    "reengaged",
    "match_method",
    "match_score",
    "source_zendesk",
    "source_slack",
]


def to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


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
    return records


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
      grid-template-columns: minmax(240px, 2fr) repeat(5, minmax(140px, 1fr));
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
    .kpis {{
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
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
        <div class="subtitle">Master lifecycle model · {total} dropped onboarding creators · Generated {generated}</div>
      </div>
      <div class="subtitle">Source: outputs/master_creator_lifecycle.csv</div>
    </div>
  </header>

  <main>
    <section class="controls" aria-label="Filters">
      <label>Search
        <input id="search" type="search" placeholder="Creator, lead, owner, reason">
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
      <label>Cadence
        <select id="cadence"></select>
      </label>
      <label>Status
        <select id="status">
          <option value="">All</option>
          <option value="reengaged">Re-engaged</option>
          <option value="installed">Installed</option>
          <option value="rise">Rise</option>
          <option value="slack">Slack intervention</option>
          <option value="salesloft">Salesloft meeting</option>
        </select>
      </label>
    </section>

    <section class="kpis" id="kpis"></section>

    <section class="grid">
      <div class="panel">
        <div class="panel-header"><h2>Service Level Mix</h2><span id="service-count"></span></div>
        <div class="bars" id="service-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Cancellation Reasons</h2><span id="reason-count"></span></div>
        <div class="bars" id="reason-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Creator Growth Timing</h2><span id="cg-count"></span></div>
        <div class="bars" id="cg-bars"></div>
      </div>
      <div class="panel">
        <div class="panel-header"><h2>Previous Ad Network</h2><span id="network-count"></span></div>
        <div class="bars" id="network-bars"></div>
      </div>
    </section>

    <section class="panel table-panel">
      <div class="table-header">
        <h2>Master Lifecycle Rows</h2>
        <span class="subtitle" id="row-count"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Creator</th>
              <th>Lead</th>
              <th>Service</th>
              <th>Vertical</th>
              <th>Network</th>
              <th>Owner</th>
              <th>Dropped</th>
              <th>Reason</th>
              <th>Cadence</th>
              <th>CG Timing</th>
              <th>Call</th>
              <th>Salesloft</th>
              <th>Slack</th>
              <th>Returned</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody id="creator-rows"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const RECORDS = {data_json};

    const fields = {{
      search: document.getElementById('search'),
      service: document.getElementById('service'),
      vertical: document.getElementById('vertical'),
      owner: document.getElementById('owner'),
      cadence: document.getElementById('cadence'),
      status: document.getElementById('status')
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

    function populateSelect(id, key) {{
      const select = document.getElementById(id);
      const values = [...new Set(RECORDS.map(row => optionValue(row[key])))].sort((a, b) => a.localeCompare(b));
      select.innerHTML = '<option value="">All</option>' + values.map(value => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join('');
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
        if (fields.service.value && optionValue(row.service_level) !== fields.service.value) return false;
        if (fields.vertical.value && optionValue(row.vertical) !== fields.vertical.value) return false;
        if (fields.owner.value && optionValue(row.onboarding_owner) !== fields.owner.value) return false;
        if (fields.cadence.value && optionValue(row.macro_cadence) !== fields.cadence.value) return false;
        if (fields.status.value === 'reengaged' && !truthy(row.reengaged)) return false;
        if (fields.status.value === 'installed' && !truthy(row.install_completed)) return false;
        if (fields.status.value === 'rise' && text(row.service_level).toLowerCase() !== 'rise') return false;
        if (fields.status.value === 'slack' && !truthy(row.slack_intervention_detected)) return false;
        if (fields.status.value === 'salesloft' && !truthy(row.salesloft_meeting_detected)) return false;
        if (!query) return true;
        const haystack = [
          row.creator_project_name,
          row.lead_contact,
          row.onboarding_owner,
          row.normalized_reason,
          row.cancellation_reason,
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
      const installed = rows.filter(row => truthy(row.install_completed)).length;
      const rise = rows.filter(row => text(row.service_level).toLowerCase() === 'rise').length;
      const zendesk = rows.filter(row => truthy(row.source_zendesk)).length;
      const slack = rows.filter(row => truthy(row.source_slack) || truthy(row.slack_intervention_detected)).length;
      return {{ total, reengaged, installed, rise, zendesk, slack }};
    }}

    function renderKpis(rows) {{
      const s = summarize(rows);
      const tiles = [
        ['Dropped creators', s.total, 'Filtered lifecycle rows'],
        ['Re-engaged', s.reengaged, pct(s.reengaged, s.total)],
        ['Installed', s.installed, pct(s.installed, s.total)],
        ['Rise creators', s.rise, pct(s.rise, s.total)],
        ['Zendesk enriched', s.zendesk, pct(s.zendesk, s.total)],
        ['Slack enriched', s.slack, pct(s.slack, s.total)]
      ];
      document.getElementById('kpis').innerHTML = tiles.map(([label, value, note]) => `
        <div class="tile">
          <div class="label">${{escapeHtml(label)}}</div>
          <div class="value">${{escapeHtml(value)}}</div>
          <div class="note">${{escapeHtml(note)}}</div>
        </div>
      `).join('');
    }}

    function groupCounts(rows, key, limit = 8) {{
      const counts = new Map();
      rows.forEach(row => {{
        const value = optionValue(row[key]);
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
      if (truthy(row.install_completed)) return '<span class="status">Installed</span>';
      if (truthy(row.reengaged)) return '<span class="status warn">Returned</span>';
      return '<span class="status no">Dropped</span>';
    }}

    function renderTable(rows) {{
      document.getElementById('row-count').textContent = `${{rows.length}} rows`;
      const tbody = document.getElementById('creator-rows');
      tbody.innerHTML = rows.map(row => `
        <tr>
          <td><strong>${{escapeHtml(row.creator_project_name)}}</strong></td>
          <td>${{escapeHtml(row.lead_contact)}}</td>
          <td>${{escapeHtml(row.service_level || 'Unknown')}}</td>
          <td>${{escapeHtml(row.vertical || 'Unknown')}}</td>
          <td>${{escapeHtml(row.previous_ad_network || 'Unknown')}}</td>
          <td>${{escapeHtml(row.onboarding_owner || 'Unknown')}}</td>
          <td>${{escapeHtml(row.dropped_date)}}</td>
          <td>${{escapeHtml(row.normalized_reason || 'Unknown')}}</td>
          <td>${{escapeHtml(row.macro_cadence || 'Unknown')}}</td>
          <td>${{escapeHtml(row.cg_escalation_timing || 'Unknown')}}</td>
          <td>${{statusPill(row.onboarding_call_offered)}}</td>
          <td>${{statusPill(row.salesloft_meeting_detected)}}</td>
          <td>${{statusPill(row.slack_intervention_detected)}}</td>
          <td>${{escapeHtml(row.returned_date)}}</td>
          <td>${{outcome(row)}}</td>
        </tr>
      `).join('');
    }}

    function render() {{
      const rows = filtered();
      renderKpis(rows);
      renderBars('service-bars', groupCounts(rows, 'service_level'), '');
      renderBars('reason-bars', groupCounts(rows, 'normalized_reason'), 'amber');
      renderBars('cg-bars', groupCounts(rows, 'cg_escalation_timing'), 'blue');
      renderBars('network-bars', groupCounts(rows, 'previous_ad_network'), 'rose');
      document.getElementById('service-count').textContent = `${{groupCounts(rows, 'service_level', 50).length}} segments`;
      document.getElementById('reason-count').textContent = `${{groupCounts(rows, 'normalized_reason', 50).length}} reasons`;
      document.getElementById('cg-count').textContent = `${{groupCounts(rows, 'cg_escalation_timing', 50).length}} groups`;
      document.getElementById('network-count').textContent = `${{groupCounts(rows, 'previous_ad_network', 50).length}} networks`;
      renderTable(rows);
    }}

    populateSelect('service', 'service_level');
    populateSelect('vertical', 'vertical');
    populateSelect('owner', 'onboarding_owner');
    populateSelect('cadence', 'macro_cadence');
    Object.values(fields).forEach(control => control.addEventListener('input', render));
    Object.values(fields).forEach(control => control.addEventListener('change', render));
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
