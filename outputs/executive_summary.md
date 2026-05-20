# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 158 dropped onboarding creators/sites and 11 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 7.0%
- Install/conversion rate among dropped creators: 6.3%
- Median days to return: 198.0
- Re-engaged & Installed after 3/5/7 follow-up: 0/158

## Strongest Cohorts

- Vertical = Health and Wellness: 50.0% re-engagement (1/2).
- Vertical = Tech: 25.0% re-engagement (1/4).
- Service Level = Platinum: 20.0% re-engagement (1/5).
- Vertical = Food: 16.7% re-engagement (9/54).
- Previous Ad Network = Mediavine: 13.4% re-engagement (9/67).
- Onboarding Owner = Michelle Stappert: 13.2% re-engagement (5/38).
- Onboarding Owner = Jade Carpenter: 11.8% re-engagement (2/17).
- Previous Ad Network = AdSense: 10.0% re-engagement (2/20).

## Creator Growth

- Assisted: 9.2% re-engagement across 87 creators.
- Not Assisted: 4.2% re-engagement across 71 creators.

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
