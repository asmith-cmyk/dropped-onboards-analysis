from __future__ import annotations

import pandas as pd

try:
    import snowflake.connector
except ImportError:
    snowflake = None

from utils.config import Settings


DROPPED_ONBOARDS_QUERY = """
WITH dropped_onboards AS (
    SELECT
        p.id AS project_id,
        a.site_id AS site_id,
        p.name AS creator_name,
        l.name AS lead_contact,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        COALESCE(NULLIF(l.website, ''), NULLIF(a.website, '')) AS domain,
        a.account_id AS salesforce_account_id,
        l.id AS salesforce_lead_id,
        p.mpm4_base__status__c AS status,
        TO_VARCHAR(p.project_cancelled_date, 'YYYY-MM-DD') AS actual_close_date,
        COALESCE(
            NULLIF(l.forecasted_service_level__c, ''),
            NULLIF(se.service_level, ''),
            NULLIF(se.service, ''),
            NULLIF(se.tier, '')
        ) AS service_level,
        COALESCE(NULLIF(l.vertical__c, ''), NULLIF(se.primary_vertical, '')) AS vertical,
        COALESCE(NULLIF(l.current_ad_network__c, ''), NULLIF(se.previous_ad_network, '')) AS previous_ad_network,
        u.name AS onboarding_owner,
        l.monthly_pageview_estimate__c AS monthly_pageviews,
        l.cg_involvement__c AS cg_involvement,
        l.cg_effort__c AS cg_effort,
        CASE
            WHEN p.cancelled_reason__c = 'Blogger missed deadline' THEN 'Non-responsive'
            WHEN p.cancelled_reason__c = 'Blogger refused ads' THEN 'Refused ad layout'
            ELSE COALESCE(NULLIF(p.cancelled_reason__c, ''), 'No reason captured')
        END AS dropped_reason,
        p.mpm4_base__description__c AS raw_description
    FROM ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
    LEFT JOIN ANALYTICS.SALESFORCE.LEAD l
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON l.site__c = a.account_id
    LEFT JOIN ANALYTICS.SALESFORCE.USER u
        ON p.ownerid = u.id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON a.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON dr
        ON se.dropped_reason_id = dr.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
      AND p.mpm4_base__status__c = 'Cancelled'
      AND p.project_cancelled_date IS NOT NULL
      AND COALESCE(
          NULLIF(l.forecasted_service_level__c, ''),
          NULLIF(se.service_level, ''),
          NULLIF(se.service, ''),
          NULLIF(se.tier, '')
      ) IN ('Rise', 'Insider', 'Platinum', 'Platinum Elite', 'Luminary', 'Mid Market Enterprise')
      AND COALESCE(p.cancelled_reason__c, '') NOT IN ('Cancelled Pre-onboarding', 'Never Engaged')
      AND NOT REGEXP_LIKE(
          LOWER(COALESCE(dr.text, se.non_standard_reason, '')),
          '(cancelled pre-onboarding|pre-onboarding|never engaged|duplicate|merged|new owner did not want to stay with adthrive|retiring site|left raptive|offboarding)'
      )
)

SELECT
    project_id,
    site_id,
    creator_name,
    lead_contact,
    company_name,
    domain,
    salesforce_account_id,
    salesforce_lead_id,
    status,
    actual_close_date,
    service_level,
    vertical,
    previous_ad_network,
    onboarding_owner,
    monthly_pageviews,
    cg_involvement,
    cg_effort,
    dropped_reason,
    raw_description
FROM dropped_onboards
ORDER BY actual_close_date DESC
"""


RETURNED_ONBOARDS_QUERY = """
WITH dropped_onboards AS (
    SELECT
        p.id AS project_id,
        a.site_id AS site_id,
        p.name AS creator_name,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        TO_VARCHAR(p.project_cancelled_date, 'YYYY-MM-DD') AS actual_close_date,
        p.project_cancelled_date AS actual_close_ts
    FROM ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
    LEFT JOIN ANALYTICS.SALESFORCE.LEAD l
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON l.site__c = a.account_id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON a.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON dr
        ON se.dropped_reason_id = dr.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
      AND p.mpm4_base__status__c = 'Cancelled'
      AND p.project_cancelled_date IS NOT NULL
      AND COALESCE(
          NULLIF(l.forecasted_service_level__c, ''),
          NULLIF(se.service_level, ''),
          NULLIF(se.service, ''),
          NULLIF(se.tier, '')
      ) IN ('Rise', 'Insider', 'Platinum', 'Platinum Elite', 'Luminary', 'Mid Market Enterprise')
      AND COALESCE(p.cancelled_reason__c, '') NOT IN ('Cancelled Pre-onboarding', 'Never Engaged')
      AND NOT REGEXP_LIKE(
          LOWER(COALESCE(dr.text, se.non_standard_reason, '')),
          '(cancelled pre-onboarding|pre-onboarding|never engaged|duplicate|merged|new owner did not want to stay with adthrive|retiring site|left raptive|offboarding)'
      )
),

returned_onboards AS (
    SELECT
        d.project_id,
        d.site_id,
        d.creator_name,
        d.company_name,
        h1.status AS current_status,
        TO_VARCHAR(h1.install_date, 'YYYY-MM-DD') AS expected_install_date,
        d.actual_close_date,
        ROW_NUMBER() OVER (
            PARTITION BY d.project_id
            ORDER BY
                h1.install_date,
                CASE h1.status
                    WHEN 'Active' THEN 1
                    WHEN 'Checkup' THEN 2
                    WHEN 'Install' THEN 3
                    ELSE 9
                END,
                TO_TIMESTAMP_NTZ(h1.updated_at)
        ) AS row_num
    FROM dropped_onboards d
    INNER JOIN ANALYTICS.ADTHRIVE.SITE_HISTORY h1
        ON d.site_id = h1.id
    WHERE h1.status IN ('Install', 'Checkup', 'Active')
      AND h1.install_date IS NOT NULL
      AND TO_DATE(h1.install_date) >= TO_DATE(d.actual_close_ts)
      AND TO_TIMESTAMP_NTZ(h1.updated_at) > TO_TIMESTAMP_NTZ(d.actual_close_ts)
)

SELECT
    project_id,
    site_id,
    creator_name,
    company_name,
    current_status,
    actual_close_date,
    expected_install_date
FROM returned_onboards
WHERE row_num = 1
ORDER BY expected_install_date DESC, creator_name, current_status
"""


DROPPED_2025_QUERY = DROPPED_ONBOARDS_QUERY
RETURNED_2026_QUERY = RETURNED_ONBOARDS_QUERY


def _connection_kwargs(settings: Settings) -> dict[str, str]:
    kwargs = {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "authenticator": settings.snowflake_authenticator,
    }
    optional = {
        "password": settings.snowflake_password,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
        "schema": settings.snowflake_schema,
        "role": settings.snowflake_role,
    }
    kwargs.update({key: value for key, value in optional.items() if value})
    return kwargs


def fetch_query_dataframe(settings: Settings, query: str) -> pd.DataFrame:
    if snowflake is None:
        raise RuntimeError("snowflake-connector-python is not installed. Run `pip install -r requirements.txt`.")
    if not settings.has_snowflake_credentials:
        raise RuntimeError(
            "Snowflake credentials are missing. Provide SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
            "and either SNOWFLAKE_PASSWORD or a non-password SNOWFLAKE_AUTHENTICATOR."
        )

    with snowflake.connector.connect(**_connection_kwargs(settings)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
