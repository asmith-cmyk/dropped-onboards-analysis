# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 54 dropped onboarding creators and 1 matched returning creators.

## Headline Metrics

- Re-engagement rate: 1.9%
- Install/conversion rate among dropped creators: 0.0%
- Median days to return: 41.0
- Re-engaged & Installed after 3/5/7 follow-up: 0/54

## Strongest Cohorts

- Vertical = Health and Wellness: 100.0% re-engagement (1/1).
- Onboarding Owner = Antoinette Smith: 10.0% re-engagement (1/10).
- Previous Ad Network = AdSense: 9.1% re-engagement (1/11).
- Creator Growth = Assisted: 3.7% re-engagement (1/27).
- Service Level = Insider: 3.3% re-engagement (1/30).
- Macro Cadence = None: 1.8% re-engagement (1/54).
- Creator Growth = Non-Assisted: 0.0% re-engagement (0/27).
- Previous Ad Network = Mediavine: 0.0% re-engagement (0/22).

## Creator Growth

- Assisted: 3.7% re-engagement across 27 creators.
- Non-Assisted: 0.0% re-engagement across 27 creators.

## Rise Creators

- All Rise: 0.0% re-engagement and 0.0% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- Salesforce dropped records define the table grain: one row per dropped onboarding creator.
- Returning Salesforce, Zendesk, Slack, Creator Growth, and Salesloft signals are enrichments on that lifecycle row.
- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.
- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.
