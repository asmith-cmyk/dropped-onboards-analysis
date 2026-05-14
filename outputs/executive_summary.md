# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 54 dropped onboarding creators and 0 matched returning creators.

## Headline Metrics

- Re-engagement rate: 0.0%
- Install/conversion rate among dropped creators: 0.0%
- Median days to return: unavailable
- Zendesk-enriched creators: 0/54
- Slack-enriched creators: 0/54

## Strongest Cohorts

- Macro Cadence = Unknown: 0.0% re-engagement (0/54).
- Service Level = Insider: 0.0% re-engagement (0/30).
- Creator Growth Involvement = Assisted: 0.0% re-engagement (0/27).
- Creator Growth Involvement = Non-Assisted: 0.0% re-engagement (0/27).
- Creator Growth Timing = CG involvement - timing unknown: 0.0% re-engagement (0/27).
- Creator Growth Timing = No CG involvement: 0.0% re-engagement (0/27).
- Previous Ad Network = Mediavine: 0.0% re-engagement (0/22).
- Service Level = Rise: 0.0% re-engagement (0/20).

## Creator Growth

- CG involvement - timing unknown: 0.0% re-engagement across 27 creators.
- No CG involvement: 0.0% re-engagement across 27 creators.

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
