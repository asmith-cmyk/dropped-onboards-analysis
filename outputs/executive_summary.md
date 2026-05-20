# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 898 dropped onboarding creators/sites and 31 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 3.5%
- Install/conversion rate among dropped creators: 3.3%
- Median days to return: 118.0
- Re-engaged & Installed after 3/5/7 follow-up: 0/898

## Strongest Cohorts

- Vertical = Health and Wellness: 100.0% re-engagement (1/1).
- Onboarding Owner = Antoinette Smith: 10.0% re-engagement (1/10).
- Previous Ad Network = AdSense: 9.1% re-engagement (1/11).
- Creator Growth = Assisted: 3.7% re-engagement (1/27).
- Service Level = Unknown: 3.5% re-engagement (30/845).
- Vertical = Unknown: 3.5% re-engagement (30/844).
- Previous Ad Network = Unknown: 3.5% re-engagement (30/844).
- Creator Growth = None: 3.5% re-engagement (30/844).

## Creator Growth

- Assisted: 3.7% re-engagement across 27 creators.
- Non-Assisted: 0.0% re-engagement across 27 creators.
- None: 3.5% re-engagement across 844 creators.

## Rise Creators

- All Rise: 0.0% re-engagement and 0.0% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- Salesforce dropped records and Snowflake 2025 dropped site-history records define the table grain: one row per dropped onboarding creator/site.
- Returning Salesforce, Snowflake returned-site cohorts, Zendesk, Slack, Creator Growth, and Salesloft signals enrich that lifecycle row.
- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.
- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.
