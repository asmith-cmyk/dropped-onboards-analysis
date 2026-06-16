# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 10566 lifecycle sites and 428 returned sites.

## Headline Metrics

- Re-engagement rate: 4.1%
- Install/conversion rate across filtered lifecycle sites: 72.8%
- Median days to return: 235.0
- Returned after 3, 5, or 7 day follow up cadence: 12/10566

## Strongest Cohorts

- Vertical = Pregnancy: 20.0% re-engagement (1/5).
- Previous Ad Network = Mediavine: 14.4% re-engagement (271/1882).
- Vertical = Careers: 14.3% re-engagement (2/14).
- Onboarding Owner = Antoinette Smith: 14.1% re-engagement (92/652).
- Onboarding Owner = Whitney Harrist: 13.7% re-engagement (89/648).
- Creator Growth = Assisted: 12.8% re-engagement (59/461).
- Previous Ad Network = Freestar: 11.5% re-engagement (7/61).
- Previous Ad Network = I manage my own ad setup using one or more ad provider: 11.5% re-engagement (7/61).

## Creator Growth

- Assisted: 12.8% re-engagement across 461 creators.
- Not Assisted: 3.6% re-engagement across 10105 creators.

## Rise Creators

- All Rise: 3.5% re-engagement and 75.1% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 3.5% re-engagement and 75.1% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- The table grain is one row per site from the full Snowflake site-history dataset.
- Returned date is the latest `INSTALL_DATE` after the most recent dropped/cancelled date.
- Cadence filters use `HAS_3_DAY_FOLLOWUP`, `HAS_5_DAY_FOLLOWUP`, and `HAS_7_DAY_FOLLOWUP` from the source dataset.
- Dropped reasons are normalized into the approved dashboard buckets, with unmatched freeform text grouped under `Everything Else`.
- Missing dashboard values are displayed as `N/A`.
