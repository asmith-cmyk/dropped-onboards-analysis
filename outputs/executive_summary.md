# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 898 dropped onboarding creators/sites and 31 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 3.5%
- Install/conversion rate among dropped creators: 3.3%
- Median days to return: 118.0
- Re-engaged & Installed after 3/5/7 follow-up: 0/898

## Strongest Cohorts

- Onboarding Owner = Marianne Seel: 50.0% re-engagement (1/2).
- Previous Ad Network = SHE Media: 33.3% re-engagement (1/3).
- Onboarding Owner = Jeff McLaughlin: 12.5% re-engagement (1/8).
- Onboarding Owner = Theresa Marigny: 12.5% re-engagement (1/8).
- Service Level = Rise: 10.5% re-engagement (8/76).
- Vertical = Family and Parenting: 10.3% re-engagement (3/29).
- Vertical = Food: 10.2% re-engagement (22/215).
- Vertical = Education: 10.0% re-engagement (1/10).

## Creator Growth

- Assisted: 3.7% re-engagement across 27 creators.
- Not Assisted: 3.4% re-engagement across 871 creators.

## Rise Creators

- All Rise: 5.9% re-engagement and 5.9% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 5.9% re-engagement and 5.9% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- Salesforce dropped records and Snowflake 2025 dropped site-history records define the table grain: one row per dropped onboarding creator/site.
- Returning Salesforce, Snowflake returned-site cohorts, Zendesk, Slack, Creator Growth, and Salesloft signals enrich that lifecycle row.
- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.
- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.
