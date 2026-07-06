# Site Retention Analysis

Python analytics pipeline for the Raptive onboarding lifecycle dashboard. The rebuilt dashboard uses one full Snowflake site-history dataset as the source of truth, then derives lifecycle outcome, return date, installed year, cadence flags, dropped-reason buckets, widgets, and the static HTML dashboard from that dataset.

The central output is:

- `outputs/master_creator_lifecycle.csv`

The dashboard is generated to:

- `outputs/lifecycle_dashboard.html`
- `docs/index.html`
- `outputs/zendesk_context.html`
- `docs/zendesk_context.html`

## Source Of Truth

The pipeline expects one raw source file:

- `data/raw/snowflake_site_history.csv`

The Zendesk context analysis can also use an optional raw source file:

- `data/raw/zendesk_onboarding_context.csv`

That CSV should come from `queries/full_site_history_lifecycle.sql`. Paste the approved SQL into that file before running a forced Snowflake pull.

Expected query output columns include:

- `SITE_ID`
- `SITE_NAME`
- `SITE_OWNER_NAME`
- `INSTALL_DATE`
- `DROPPED_DATE`
- `SITE_STATUS`
- `SERVICE_LEVEL`
- `VERTICAL`
- `ONBOARD_OWNER_NAME`
- `PREVIOUS_AD_NETWORK`
- `HAS_3_DAY_FOLLOWUP`
- `HAS_5_DAY_FOLLOWUP`
- `HAS_7_DAY_FOLLOWUP`
- `HAS_ESCALATED_TO_CG`
- `CG_ASSISTED`
- `CG_INVOLVEMENT`
- `DROPPED_REASON` or `CANCELLED_REASON`

Optional columns such as `COMPANY_NAME`, `DOMAIN`, `URL`, `MONTHLY_PAGEVIEWS`, `RAW_DESCRIPTION`, and `RETURNED_REASON` are carried through when present.

Zendesk context exports can include any of these fields. Matching works best when at least one of `SITE_ID`, `DOMAIN`, `CREATOR`, or `REQUESTER` is present:

- `TICKET_ID`
- `SITE_ID`
- `DOMAIN`, `URL`, or `WEBSITE`
- `CREATOR` or `PROJECT_NAME`
- `REQUESTER` or `LEAD_CONTACT`
- `SUBJECT`
- `CREATED_AT`, `UPDATED_AT`, `SOLVED_AT`
- `TAGS`
- `ZENDESK_SUMMARY`, `ZENDESK_AI_SUMMARY`, `AI_SUMMARY`, or `SUMMARY`
- `COMMENTS`, `CONVERSATION_TEXT`, `DESCRIPTION`, or `TICKET_COMMENTS`
- `SENTIMENT`
- `MILESTONE`

## Lifecycle Logic

The master table is site-grain: one row per site.

Returned:

- The site has a historical dropped/cancelled event.
- The latest `INSTALL_DATE` is after the latest dropped/cancelled date.
- There is no newer dropped/cancelled event after that install.

Onboarding:

- The current `SITE_STATUS` is `Setup`.

Dropped:

- The site has a historical dropped/cancelled event.
- The site has no `INSTALL_DATE` after the latest dropped/cancelled date.

Installed:

- The site has an install record and no dropped/cancelled event after that install.

Sites without a prior dropped/cancelled event are retained as `Installed` so the dashboard can show full site history, not only dropped/returned rows.

## Filter Logic

- Installed Year: year from `INSTALL_DATE`
- Service Level: `SERVICE_LEVEL`
- Vertical: `PRIMARY_VERTICAL`, falling back to `VERTICALS`
- Onboarding Owner: `ONBOARD_OWNER_NAME`
- Cadence: `HAS_3_DAY_FOLLOWUP`, `HAS_5_DAY_FOLLOWUP`, `HAS_7_DAY_FOLLOWUP`, `HAS_ESCALATED_TO_CG`
- Previous Ad Network widget: `PREVIOUS_AD_NETWORK`

## Dropped Reason Filter

The dropped reason dropdown is grouped by the existing `DROPPED_REASON_CATEGORY` values. Category labels display as non-selectable dropdown headers, and each selectable option uses the existing raw `DROPPED_REASON` value.

The table keeps the dropped reason category and dropped reason values as they come from the data source. `normalized_dropped_reason` is still produced as a separate helper field for analysis, but it does not replace the displayed category or reason.

## Zendesk Context Analysis

`generate_outputs.py` also creates a first-pass Zendesk context layer for sites with a `DROPPED_DATE` in 2026. The year is intentionally scoped to 2026 for now and can be expanded later.

The analysis produces:

- Cancellation and ghosting signals, such as no response, competitor/provider movement, revenue concerns, ad-layout concerns, eligibility/verification blockers, timing constraints, and setup blockers.
- Communication and sentiment signals, such as negative/positive sentiment, repeated follow-up patterns, recurring questions, and technical/revenue/timeline questions.
- Drop-off and Community Growth signals, such as likely onboarding milestone, CG involvement, and whether Zendesk context suggests CG entered before or around the drop/cancel event.

The output intentionally does not commit raw Zendesk comment text. It keeps ticket IDs, Zendesk/native AI summaries when provided, and derived themes/signals.

The main dashboard table includes a `Zendesk Context` column for 2026 dropped/cancelled rows. Each link opens `zendesk_context.html` for that site, showing the related dropped site, dropped reason, ticket IDs, context summary, sentiment, likely milestone stage, theme signals, and Creator Growth fields.

The main site table and Zendesk context list are paginated for browser performance. Filters, charts, KPI cards, and CSV export still use the full filtered dataset; pagination only controls how many rows are rendered on screen at once.

## Running Locally

Import an exported full-history CSV:

```bash
python scripts/pull_snowflake_data.py --input-site-history-csv path/to/full_site_history.csv
python scripts/generate_outputs.py
```

Pull directly from Snowflake:

```bash
python scripts/pull_snowflake_data.py --force-api
python scripts/generate_outputs.py
```

Or run the pull and build together:

```bash
python scripts/generate_outputs.py --run-pulls --force-snowflake-api
```

Generate only the static dashboard after outputs exist:

```bash
python scripts/generate_visual_report.py
```

## Outputs

Generated files:

- `outputs/master_creator_lifecycle.csv`
- `outputs/reengaged_creators.csv`
- `outputs/cohort_analysis.csv`
- `outputs/cadence_analysis.csv`
- `outputs/cancellation_reason_analysis.csv`
- `outputs/creator_growth_analysis.csv`
- `outputs/rise_creator_analysis.csv`
- `outputs/zendesk_context_analysis.csv`
- `outputs/zendesk_context_theme_summary.csv`
- `outputs/executive_summary.md`
- `outputs/lifecycle_dashboard.html`

## GitHub Actions

`.github/workflows/nightly-analysis.yml` runs nightly and can also be triggered manually.

The workflow:

1. Installs Python dependencies.
2. Pulls the full site-history dataset from Snowflake.
3. Regenerates outputs and `docs/index.html`.
4. Commits refreshed outputs.

Snowflake requires:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD` for password auth, or `SNOWFLAKE_AUTHENTICATOR` for SSO/external auth
- optional `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE`

## Notes

- Raw source exports are ignored by Git because they can contain sensitive operational data.
- The old Salesforce dropped/returning report scripts remain for reference, but the rebuilt dashboard pipeline does not use them.
- `queries/full_site_history_lifecycle.sql` currently contains a placeholder until the approved SQL is pasted in.
