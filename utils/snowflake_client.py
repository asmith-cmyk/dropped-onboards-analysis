from __future__ import annotations

import pandas as pd

try:
    import snowflake.connector
except ImportError:
    snowflake = None

from utils.config import Settings


DROPPED_2025_QUERY = """
WITH dropped_2025 AS (
    SELECT DISTINCT
        id AS site_id,
        name AS creator_name,
        company_name,
        status,
        TO_TIMESTAMP_NTZ(updated_at) AS actual_close_date
    FROM ANALYTICS.ADTHRIVE.SITE_HISTORY
    WHERE status IN ('Dropped', 'Canceled', 'Cancelled')
      AND YEAR(TO_TIMESTAMP_NTZ(updated_at)) = 2025
)

SELECT
    site_id,
    creator_name,
    company_name,
    status,
    actual_close_date
FROM dropped_2025
ORDER BY actual_close_date DESC
"""


RETURNED_2026_QUERY = """
WITH history AS (
    SELECT
        id AS site_id,
        name AS creator_name,
        company_name,
        status,
        install_date AS expected_install_date,
        TO_TIMESTAMP_NTZ(updated_at) AS updated_ts
    FROM ANALYTICS.ADTHRIVE.SITE_HISTORY
),

returned_2026 AS (
    SELECT DISTINCT
        h1.site_id,
        h1.creator_name,
        h1.company_name,
        h1.status AS current_status,
        h1.expected_install_date,
        MAX(h2.updated_ts) AS actual_close_date
    FROM history h1
    INNER JOIN history h2
        ON h1.site_id = h2.site_id
    WHERE h1.status IN ('Install', 'Checkup', 'Active')
      AND YEAR(h1.expected_install_date) = 2026
      AND h2.status IN ('Dropped', 'Canceled', 'Cancelled')
      AND YEAR(h2.updated_ts) = 2025
      AND h2.updated_ts < h1.updated_ts
    GROUP BY 1,2,3,4,5
)

SELECT
    site_id,
    creator_name,
    company_name,
    current_status,
    actual_close_date,
    expected_install_date
FROM returned_2026
ORDER BY creator_name, current_status
"""


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
