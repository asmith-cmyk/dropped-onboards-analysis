# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 574 dropped onboarding creators/sites and 146 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 25.4%
- Install/conversion rate among dropped creators: 25.3%
- Median days to return: 233.0
- Re-engaged & Installed after 3/5/7 follow-up: 0/574

## Strongest Cohorts

- Previous Ad Network = AdVally: 100.0% re-engagement (1/1).
- Vertical = Family and Parenting: 50.0% re-engagement (2/4).
- Previous Ad Network = Monumetric: 50.0% re-engagement (2/4).
- Vertical = Beauty: 50.0% re-engagement (1/2).
- Vertical = Green Living: 50.0% re-engagement (1/2).
- Vertical = Wedding: 50.0% re-engagement (1/2).
- Onboarding Owner = Kate Fitzpatrick: 50.0% re-engagement (1/2).
- Vertical = Food: 45.7% re-engagement (64/140).

## Creator Growth

- Assisted: 25.7% re-engagement across 187 creators.
- Not Assisted: 25.3% re-engagement across 387 creators.

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
