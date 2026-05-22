# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 799 dropped onboarding creators/sites and 374 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 46.8%
- Install/conversion rate among dropped creators: 43.3%
- Median days to return: 312.5
- Re-engaged & Installed after any follow-up cadence: 25/799

## Strongest Cohorts

- Vertical = Education: 100.0% re-engagement (5/5).
- Vertical = Deals: 100.0% re-engagement (1/1).
- Vertical = Professional Finance: 100.0% re-engagement (1/1).
- Previous Ad Network = AdVally: 100.0% re-engagement (1/1).
- Previous Ad Network = Playwire: 100.0% re-engagement (1/1).
- Macro Cadence = 3 and 5 day follow up: 100.0% re-engagement (1/1).
- Macro Cadence = 3, 5 and 7 day follow up: 100.0% re-engagement (1/1).
- Vertical = Arts & Creativity: 80.0% re-engagement (4/5).

## Creator Growth

- Assisted: 61.7% re-engagement across 363 creators.
- Not Assisted: 34.4% re-engagement across 436 creators.

## Rise Creators

- All Rise: 0.0% re-engagement and 0.0% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- Salesforce dropped records and Snowflake Salesforce Onboarding project records define the table grain: one row per dropped onboarding creator/site.
- Returning Salesforce, Snowflake returned-site cohorts, Zendesk, Slack, Creator Growth, and Salesloft signals enrich that lifecycle row.
- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.
- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.
