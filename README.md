# Site Retention & Return Analysis

Python analytics pipeline for the Raptive onboarding lifecycle dashboard. The rebuilt dashboard uses one full Snowflake site-history dataset as the source of truth, then derives lifecycle outcome, return date, installed year, cadence flags, dropped-reason buckets, widgets, and the static HTML dashboard from that dataset.

The central output is:

- `outputs/master_creator_lifecycle.csv`

The dashboard is generated to:

- `outputs/lifecycle_dashboard.html`
- `docs/index.html`

## Source Of Truth

The pipeline expects one raw source file:

- `data/raw/snowflake_site_history.csv`

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

## Lifecycle Logic

The master table is site-grain: one row per site.

Returned:

- The site has a historical dropped/cancelled event.
- The latest `INSTALL_DATE` is after the latest dropped/cancelled date.
- There is no newer dropped/cancelled event after that install.

Onboarding:

- The current `SITE_STATUS` is `Setup`.
- The current date is before the site's `INSTALL_DATE`.

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
