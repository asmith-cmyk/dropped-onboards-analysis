-- Pull the denominator for the dashboard drop-off rate widget.
--
-- Export these results as CSV, then import them with:
-- python scripts/pull_snowflake_data.py --input-starts-csv path/to/export.csv
-- python scripts/generate_outputs.py
--
-- The dashboard counts one unique onboarding_start_id per site per Setup-start date.

WITH ordered_site_history AS (
    SELECT
        h.id AS site_id,
        h.status,
        TO_TIMESTAMP_NTZ(h.updated_at) AS status_updated_at,
        TO_DATE(h.install_date) AS install_date,
        LAG(h.status) OVER (
            PARTITION BY h.id
            ORDER BY TO_TIMESTAMP_NTZ(h.updated_at), h.status
        ) AS previous_status
    FROM ANALYTICS.ADTHRIVE.SITE_HISTORY h
    WHERE h.id IS NOT NULL
      AND h.updated_at IS NOT NULL
),

onboarding_start_events AS (
    SELECT
        h.site_id,
        h.status_updated_at AS onboarding_started_at,
        h.install_date,
        COALESCE(
            NULLIF(se.service_level, ''),
            NULLIF(se.service, ''),
            NULLIF(se.tier, '')
        ) AS service_level,
        NULLIF(se.primary_vertical, '') AS vertical,
        NULLIF(se.previous_ad_network, '') AS previous_ad_network,
        s.status AS current_site_status,
        ROW_NUMBER() OVER (
            PARTITION BY h.site_id, TO_DATE(h.status_updated_at)
            ORDER BY h.status_updated_at
        ) AS daily_start_row_num
    FROM ordered_site_history h
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON h.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE s
        ON h.site_id = s.id
    WHERE h.status = 'Setup'
      AND COALESCE(h.previous_status, '') != 'Setup'
      AND COALESCE(
          NULLIF(se.service_level, ''),
          NULLIF(se.service, ''),
          NULLIF(se.tier, '')
      ) IN ('Rise', 'Insider', 'Platinum', 'Platinum Elite', 'Luminary', 'Mid Market Enterprise')
)

SELECT
    site_id || '|' || TO_VARCHAR(onboarding_started_at, 'YYYY-MM-DD') AS onboarding_start_id,
    site_id,
    TO_VARCHAR(onboarding_started_at, 'YYYY-MM-DD') AS onboarding_started_date,
    YEAR(TO_DATE(onboarding_started_at)) AS onboarding_started_year,
    service_level,
    vertical,
    previous_ad_network,
    current_site_status,
    TO_VARCHAR(install_date, 'YYYY-MM-DD') AS install_date
FROM onboarding_start_events
WHERE daily_start_row_num = 1
ORDER BY onboarding_started_date DESC, site_id;
