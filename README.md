# Onboarding Lifecycle Re-engagement Analysis

Python analytics pipeline for Raptive/CafeMedia dropped onboarding creators. It pulls dropped and returning Salesforce reports, Snowflake site-history cohorts, normalizes creator identity, enriches each creator with Zendesk and Slack signals, classifies cancellation reasons, and builds one master lifecycle dataset that serves as the source of truth for downstream views and summaries.

The central output is:

- `outputs/master_creator_lifecycle.csv`

All cohort, cadence, Creator Growth, Rise, re-engagement, and executive summary outputs are derived from that master table.

## Source Reports

Salesforce:

- Dropped onboards report: `00OQQ000007tl772AA`
- Returning / YoYo creators report: `00OQQ000007tlAL2AY`

Confirmed dropped report fields:

- `Project: Project Name`
- `Lead: Contact`
- `Lead: CG Involvement`
- `Lead: Current Ad Network`
- `Project: Owner Name`
- `Description`
- `Lead: Monthly Pageview Estimate`
- `Service Level`
- `Lead: Vertical`
- `Lead: CG Effort`
- `Cancelled Reason`

Confirmed returning report fields:

- `Onboarding Project Link: Project Name`
- `Lead`
- `Previous Ad Network`
- `Onboarding Project Link: Owner Name`
- `Onboarding Project Link: Scheduled Install Date`
- `Install Date`

Snowflake:

- `ANALYTICS.ADTHRIVE.SITE_HISTORY`
- `snowflake_dropped_2025.csv` captures all sites with `Dropped`, `Canceled`, or `Cancelled` history in 2025.
- `snowflake_returned_2026.csv` captures those 2025 dropped/canceled sites that later appear in `Install`, `Checkup`, or `Active` with a 2026 expected install date.

Zendesk:

- Primary Explore dashboard tracks onboarding tickets that received 3, 5, 7, and/or 10 day follow-up tags.
- The production script uses Zendesk Support API ticket search and tag normalization. A dashboard CSV export can also be supplied with `ZENDESK_EXPORT_CSV`.

Slack:

- `#onboarding-creatorgrowth`
- `#salesloft-meetings`

Slack messages are parsed into intervention events such as Creator Growth escalation, Salesloft meeting, onboarding call offer, and rescue intervention.

## Setup

```bash
cd dropped-onboards-analysis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` or export the relevant environment variables.

## Authentication

Salesforce supports either:

- `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, `SALESFORCE_SECURITY_TOKEN`, optional `SALESFORCE_DOMAIN`
- `SALESFORCE_SESSION_ID` and `SALESFORCE_INSTANCE_URL`

Zendesk requires:

- `ZENDESK_SUBDOMAIN`
- `ZENDESK_EMAIL`
- `ZENDESK_API_TOKEN`

Slack requires:

- `SLACK_BOT_TOKEN`
- bot access to `#onboarding-creatorgrowth` and `#salesloft-meetings`

Snowflake requires:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD` for password auth, or `SNOWFLAKE_AUTHENTICATOR` for SSO/external auth
- optional `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE`

OpenAI is optional:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

If no OpenAI key is present, cancellation reason classification falls back to deterministic rules.

## Running Locally

To use existing local CSV exports:

```bash
python scripts/pull_salesforce_reports.py \
  --input-dropped-csv data/raw/salesforce_dropped_onboards.csv \
  --input-returning-csv data/raw/salesforce_returning_yoyo.csv
python scripts/generate_outputs.py
```

To refresh from APIs:

```bash
python scripts/pull_salesforce_reports.py --force-api
python scripts/pull_snowflake_data.py --force-api
python scripts/pull_zendesk_data.py
python scripts/pull_slack_data.py
python scripts/generate_outputs.py
```

Or run the full source pull and analysis:

```bash
python scripts/generate_outputs.py --run-pulls --force-salesforce-api --force-snowflake-api
```

## Pipeline Stages

1. `pull_salesforce_reports.py` fetches the dropped and returning Salesforce reports.
2. `pull_snowflake_data.py` fetches 2025 dropped/canceled site history and 2026 returned-site cohorts.
3. `pull_zendesk_data.py` pulls Zendesk onboarding ticket/tag data or normalizes an exported CSV.
4. `pull_slack_data.py` pulls intervention messages from Slack.
5. `normalize_creators.py` canonicalizes creator, lead, network, owner, vertical, service level, and date fields.
6. `match_reengagements.py` matches dropped creators to returning creators.
7. `classify_cancellation_reasons.py` normalizes cancellation descriptions into business categories.
8. `build_master_lifecycle.py` creates `master_creator_lifecycle.csv`, the consolidated creator lifecycle table.
9. `generate_outputs.py` derives all CSV and markdown outputs from the master lifecycle table.

`build_creator_timelines.py` is retained as a compatibility alias and now delegates to `build_master_lifecycle.py`.

## Matching Logic

The creator matching system uses this priority order:

1. Salesforce project/account IDs when present
2. Normalized project/site name
3. Normalized lead contact name
4. Site/domain extracted from available text
5. Fuzzy project-name matching with RapidFuzz

Normalization lowercases text, strips punctuation/accents, collapses whitespace, removes common company suffixes, and extracts domains from descriptions where available.

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

## Master Lifecycle Schema

`master_creator_lifecycle.csv` is the canonical analytical model. Salesforce dropped records and Snowflake dropped site-history records define the table grain: one row per dropped onboarding creator/site. Returning Salesforce, Snowflake returned-site cohorts, Zendesk, Slack, Creator Growth, and Salesloft signals enrich that row.

Core field groups:

- Identity: `lifecycle_creator_id`, `creator_project_name`, `lead_contact`, `company_name`, `domain`, `site_id`, `salesforce_project_id`, `salesforce_account_id`, `salesforce_lead_id`, `creator_key`, `lead_key`
- Creator attributes: `vertical`, `service_level`, `previous_ad_network`, `onboarding_owner`, `monthly_pageviews`, `dropped_status`
- Lifecycle dates: `dropped_date`, `returned_date`, `scheduled_install_date`, `install_date`, `days_to_return`
- Cancellation intelligence: `cancellation_reason`, `raw_description`, `normalized_reason`, `reason_confidence_score`, `reason_classification_method`
- Zendesk cadence: `macro_cadence`, `zendesk_ticket_count`, `ticket_reopened`
- Creator Growth: `cg_involvement`, `cg_effort`, `cg_escalation_status`, `cg_escalation_timing`, `cg_first_touch_at`, `cg_days_from_drop`
- Human-touch indicators: `onboarding_call_offered`, `salesloft_meeting_detected`, `first_salesloft_meeting_at`, `slack_intervention_detected`, `slack_intervention_count`, `rescue_intervention_detected`
- Outcomes: `install_completed`, `converted`, `reengaged`, `outcome`
- Match diagnostics: `returning_project_name`, `returning_lead_contact`, `returning_previous_ad_network`, `returning_owner`, `returning_status`, `match_method`, `match_score`
- Source coverage: `source_salesforce_dropped`, `source_salesforce_returning`, `source_snowflake`

`reengaged_creators.csv` is now a leadership-friendly view derived from the master table. It includes:

- Creator
- Vertical
- Service Level
- Previous Ad Network
- Dropped Date
- Returned Date
- Days_to_Return
- CG Involvement
- Macro Cadence
- Meeting Offered
- Re-engaged
- Installed
- Converted

Additional fields include owner, lead contact, Creator Growth timing, and match details.

## Visual Dashboard

Generate the static HTML dashboard with:

```bash
python scripts/generate_visual_report.py
```

The dashboard is written to `outputs/lifecycle_dashboard.html`. It is self-contained and can be opened directly in Chrome. The regular `generate_outputs.py` pipeline also regenerates it automatically.

For GitHub Pages, the same dashboard is also written to `docs/index.html`.

To publish it with branch-based GitHub Pages:

1. Push this project to GitHub.
2. Go to repository Settings -> Pages.
3. Set Source to `Deploy from a branch`.
4. Choose the branch you use for the project and `/docs` as the folder.
5. Save.

After each nightly run, the workflow commits refreshed outputs plus `docs/index.html`, so Pages will serve the latest dashboard.

## GitHub Actions Automation

`.github/workflows/nightly-analysis.yml` runs every night at 08:00 UTC and can also be triggered manually.

The workflow:

1. Installs Python dependencies.
2. Pulls Salesforce reports from the Analytics Report API.
3. Pulls optional Zendesk and Slack enrichment data.
4. Regenerates outputs.
5. Commits changed files in `outputs/`.

Required GitHub secrets:

- `SALESFORCE_USERNAME`
- `SALESFORCE_PASSWORD`
- `SALESFORCE_SECURITY_TOKEN`
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD`
- `ZENDESK_SUBDOMAIN`
- `ZENDESK_EMAIL`
- `ZENDESK_API_TOKEN`
- `SLACK_BOT_TOKEN`
- `OPENAI_API_KEY`

Recommended GitHub variables:

- `SALESFORCE_API_VERSION`
- `SALESFORCE_DROPPED_REPORT_ID`
- `SALESFORCE_RETURNING_REPORT_ID`
- `SNOWFLAKE_AUTHENTICATOR`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_ROLE`
- `ZENDESK_SEARCH_QUERY`
- `SLACK_CHANNEL_NAMES`
- `SLACK_START_DATE`
- `OPENAI_MODEL`
- `USE_OPENAI_CLASSIFICATION`

## Notes And Assumptions

- `master_creator_lifecycle.csv` is the source of truth for lifecycle analysis and downstream reporting.
- Salesforce and Snowflake are the source of truth for dropped and returning creator/site records.
- Dropped date is read from a date column when present. If the report has no dropped-date column, the pipeline infers a date from cancellation/drop language in the description as a fallback.
- Returned date is install date when present, otherwise scheduled install date.
- Converted currently means install completed unless a dedicated conversion status/date is added later.
- Zendesk and Slack enrichments are optional and resilient to missing data.
- Raw source exports are ignored by Git because they can contain sensitive operational data.

## Future Extensions

- Add a dedicated Salesforce field for dropped/cancelled date to reduce description-date inference.
- Add explicit onboarding call offer fields to Salesforce or Zendesk tags for cleaner Rise creator testing.
- Add controlled experiment IDs for old vs. new cadence comparisons.
- Add ticket audit ingestion for exact macro execution timestamps.
- Add Slack permalink hydration for reviewable intervention timelines.
- Publish outputs to a warehouse or BI tool after the CSV contract stabilizes.
