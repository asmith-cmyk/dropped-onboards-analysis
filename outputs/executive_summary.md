# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 12550 lifecycle sites and 483 returned sites.

## Headline Metrics

- Re-engagement rate: 3.8%
- Install/conversion rate across filtered lifecycle sites: 68.1%
- Median days to return: 246.0
- Returned after 3, 5, or 7 day follow up cadence: 32/12550

## Strongest Cohorts

- Previous Ad Network = Custom ad placements on the sidebar: 100.0% re-engagement (1/1).
- Previous Ad Network = BlogHer: 33.3% re-engagement (1/3).
- Previous Ad Network = Newor Media: 25.0% re-engagement (1/4).
- Vertical = Pregnancy: 20.0% re-engagement (1/5).
- Onboarding Owner = Antoinette Smith: 15.5% re-engagement (114/736).
- Previous Ad Network = Mediavine: 15.1% re-engagement (300/1984).
- Macro Cadence = 7 day follow up: 14.8% re-engagement (9/61).
- Previous Ad Network = Playwire: 13.3% re-engagement (2/15).

## Creator Growth

- Assisted: 11.2% re-engagement across 609 creators.
- Not Assisted: 3.5% re-engagement across 11941 creators.

## Rise Creators

- All Rise: 3.2% re-engagement and 58.6% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 3.2% re-engagement and 58.6% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- The table grain is one row per site from the full Snowflake site-history dataset.
- Returned date is the latest `INSTALL_DATE` after the most recent dropped/cancelled date.
- Cadence filters use `HAS_3_DAY_FOLLOWUP`, `HAS_5_DAY_FOLLOWUP`, and `HAS_7_DAY_FOLLOWUP` from the source dataset.
- Dropped reasons are normalized into the approved dashboard buckets, with unmatched freeform text grouped under `Everything Else`.
- Missing dashboard values are displayed as `N/A`.
