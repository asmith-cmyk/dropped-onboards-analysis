# Onboarding Lifecycle Executive Summary

Generated from the master lifecycle dataset with 10569 lifecycle sites and 429 returned sites.

## Headline Metrics

- Re-engagement rate: 4.1%
- Install/conversion rate across filtered lifecycle sites: 72.6%
- Median days to return: 236.0
- Returned after 3, 5, or 7 day follow up cadence: 19/10569

## Strongest Cohorts

- Macro Cadence = 3, 5 and 7 day follow up: 100.0% re-engagement (1/1).
- Vertical = Pregnancy: 20.0% re-engagement (1/5).
- Previous Ad Network = Mediavine: 14.4% re-engagement (272/1883).
- Vertical = Careers: 14.3% re-engagement (2/14).
- Onboarding Owner = Antoinette Smith: 14.3% re-engagement (93/652).
- Onboarding Owner = Whitney Harrist: 13.7% re-engagement (89/650).
- Creator Growth = Assisted: 12.6% re-engagement (56/445).
- Previous Ad Network = Freestar: 11.5% re-engagement (7/61).

## Creator Growth

- Assisted: 12.6% re-engagement across 445 creators.
- Not Assisted: 3.7% re-engagement across 10124 creators.

## Rise Creators

- All Rise: 3.5% re-engagement and 75.2% install rate.
- Onboarding Call Offered: 0.0% re-engagement and 0.0% install rate.
- No Onboarding Call Offered: 3.5% re-engagement and 75.2% install rate.
- Salesloft Meeting Detected: 0.0% re-engagement and 0.0% install rate.
- Slack Intervention Detected: 0.0% re-engagement and 0.0% install rate.

## Data Notes

- `master_creator_lifecycle.csv` is the single source of truth for downstream lifecycle analysis.
- The table grain is one row per site from the full Snowflake site-history dataset.
- Returned date is the latest `INSTALL_DATE` after the most recent dropped/cancelled date.
- Cadence filters use `HAS_3_DAY_FOLLOWUP`, `HAS_5_DAY_FOLLOWUP`, and `HAS_7_DAY_FOLLOWUP` from the source dataset.
- Dropped reasons are normalized into the approved dashboard buckets, with unmatched freeform text grouped under `Everything Else`.
- Missing dashboard values are displayed as `N/A`.
