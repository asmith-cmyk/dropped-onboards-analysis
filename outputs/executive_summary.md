# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 778 dropped onboarding creators/sites and 353 returned creators/sites.

## Headline Metrics

- Re-engagement rate: 45.4%
- Install/conversion rate among dropped creators: 42.2%
- Median days to return: 334.0
- Returned after 3, 5, or 7 day follow up cadence: 6/778

## Strongest Cohorts

- Vertical = Education: 100.0% re-engagement (5/5).
- Vertical = Deals: 100.0% re-engagement (1/1).
- Vertical = Professional Finance: 100.0% re-engagement (1/1).
- Previous Ad Network = AdVally: 100.0% re-engagement (1/1).
- Previous Ad Network = Playwire: 100.0% re-engagement (1/1).
- Vertical = Arts & Creativity: 80.0% re-engagement (4/5).
- Vertical = Clean Eating: 75.0% re-engagement (3/4).
- Vertical = Food: 73.7% re-engagement (207/281).

## Creator Growth

- Assisted: 59.6% re-engagement across 344 creators.
- Not Assisted: 34.1% re-engagement across 434 creators.

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
- Zendesk follow-up cadence is matched by creator/lead plus ticket created-to-solved date overlap with the dropped date.
- Cancellation reason categories use OpenAI when `OPENAI_API_KEY` is present, with a deterministic rules fallback.
- Conversion is treated as install completion unless a dedicated conversion date/status is supplied.
