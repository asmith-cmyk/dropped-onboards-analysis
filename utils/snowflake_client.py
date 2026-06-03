from __future__ import annotations

import pandas as pd

try:
    import snowflake.connector
except ImportError:
    snowflake = None

from utils.config import Settings


DROPPED_ONBOARDS_QUERY = """
WITH qualifying_dropped_onboards AS (
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
        END AS cancelled_reason,
        CASE
            WHEN p.mpm4_base__description__c ILIKE 'SETUP CANCELLATION NOTE%' THEN 'Cancelled Pre-onboarding'
            ELSE COALESCE(
                NULLIF(hdr.text, ''),
                NULLIF(dr.text, ''),
                NULLIF(p.dropped_reason__c, ''),
                CASE
                    WHEN p.cancelled_reason__c = 'Blogger missed deadline' THEN 'Non-responsive'
                    WHEN p.cancelled_reason__c = 'Blogger refused ads' THEN 'Refused ad layout'
                    ELSE NULLIF(p.cancelled_reason__c, '')
                END,
                'No dropped reason captured'
            )
        END AS dropped_reason,
        COALESCE(
            NULLIF(p.dropped_reason_category__c, ''),
            NULLIF(hdrc.text, ''),
            NULLIF(drc.text, '')
        ) AS dropped_reason_category,
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
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY drc
        ON dr.dropped_reason_category_id = drc.id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_HISTORY h
        ON a.site_id = h.id
       AND h.status IN ('Dropped', 'Canceled', 'Cancelled')
       AND TO_TIMESTAMP_NTZ(h.updated_at) >= DATEADD(day, -30, TO_TIMESTAMP_NTZ(p.project_cancelled_date))
       AND TO_TIMESTAMP_NTZ(h.updated_at) <= DATEADD(day, 7, TO_TIMESTAMP_NTZ(p.project_cancelled_date))
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON hdr
        ON h.dropped_reason_id = hdr.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY hdrc
        ON hdr.dropped_reason_category_id = hdrc.id
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
      AND COALESCE(p.cancelled_reason__c, '') != 'Never Engaged'
      AND (
          COALESCE(p.cancelled_reason__c, '') != 'Cancelled Pre-onboarding'
          OR p.mpm4_base__description__c ILIKE '%setup cancellation%'
      )
      AND (
          p.mpm4_base__description__c ILIKE '%setup cancellation%'
          OR NOT REGEXP_LIKE(
              LOWER(COALESCE(dr.text, se.non_standard_reason, '')),
              '(cancelled pre[-[:space:]0]?onboarding|pre[-[:space:]0]?onboarding|never engaged|duplicate|merged|new owner did not want to stay with adthrive|retiring site|left raptive|offboarding)'
          )
      )
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY p.id
        ORDER BY
            CASE WHEN h.id IS NULL THEN 1 ELSE 0 END,
            ABS(DATEDIFF('second', TO_TIMESTAMP_NTZ(h.updated_at), TO_TIMESTAMP_NTZ(p.project_cancelled_date))),
            TO_TIMESTAMP_NTZ(h.updated_at) DESC
    ) = 1
),

current_return_projects AS (
    SELECT
        p.id AS return_project_id,
        a.site_id AS site_id,
        p.name AS creator_name,
        l.name AS lead_contact,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        COALESCE(NULLIF(l.website, ''), NULLIF(a.website, '')) AS domain,
        a.account_id AS salesforce_account_id,
        l.id AS salesforce_lead_id,
        TO_TIMESTAMP_NTZ(p.createddate) AS project_created_at,
        TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c)) AS return_date,
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
        ROW_NUMBER() OVER (
            PARTITION BY a.site_id, TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c))
            ORDER BY TO_TIMESTAMP_NTZ(p.createddate) DESC, p.id DESC
        ) AS project_row_num
    FROM ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
    LEFT JOIN ANALYTICS.SALESFORCE.LEAD l
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON l.site__c = a.account_id
    LEFT JOIN ANALYTICS.SALESFORCE.USER u
        ON p.ownerid = u.id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON a.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE s
        ON a.site_id = s.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
      AND p.mpm4_base__status__c IN ('Active', 'Completed')
      AND COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c) IS NOT NULL
      AND YEAR(TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c))) >= 2025
      AND COALESCE(
          NULLIF(l.forecasted_service_level__c, ''),
          NULLIF(se.service_level, ''),
          NULLIF(se.service, ''),
          NULLIF(se.tier, '')
      ) IN ('Rise', 'Insider', 'Platinum', 'Platinum Elite', 'Luminary', 'Mid Market Enterprise')
      AND a.site_id IS NOT NULL
),

prior_cancelled_onboarding_projects AS (
    SELECT
        rp.return_project_id,
        p.id AS prior_project_id,
        CASE
            WHEN p.cancelled_reason__c = 'Blogger missed deadline' THEN 'Non-responsive'
            WHEN p.cancelled_reason__c = 'Blogger refused ads' THEN 'Refused ad layout'
            ELSE NULLIF(p.cancelled_reason__c, '')
        END AS prior_cancelled_reason,
        NULLIF(p.dropped_reason__c, '') AS prior_dropped_reason,
        NULLIF(p.dropped_reason_category__c, '') AS prior_dropped_reason_category,
        NULLIF(p.reason_they_left__c, '') AS prior_reason_they_left,
        NULLIF(p.reasontheyleftspecifics__c, '') AS prior_reason_left_specifics,
        NULLIF(
            TRIM(
                SPLIT_PART(
                    REGEXP_REPLACE(
                        IFF(
                            POSITION('setup cancellation' IN LOWER(COALESCE(p.mpm4_base__description__c, ''))) > 0,
                            SUBSTR(
                                p.mpm4_base__description__c,
                                POSITION('setup cancellation' IN LOWER(p.mpm4_base__description__c)) + LENGTH('setup cancellation'),
                                240
                            ),
                            NULL
                        ),
                        '^[:[:space:]-]*(note[:[:space:]-]*)?',
                        '',
                        1,
                        0,
                        'i'
                    ),
                    CHR(10),
                    1
                )
            ),
            ''
        ) AS setup_cancellation_reason,
        p.mpm4_base__description__c AS prior_raw_description,
        ROW_NUMBER() OVER (
            PARTITION BY rp.return_project_id
            ORDER BY p.project_cancelled_date DESC NULLS LAST, TO_TIMESTAMP_NTZ(p.createddate) DESC, p.id DESC
        ) AS prior_project_row_num
    FROM current_return_projects rp
    INNER JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON rp.site_id = a.site_id
    INNER JOIN ANALYTICS.SALESFORCE.LEAD l
        ON l.site__c = a.account_id
    INNER JOIN ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
        ON p.related_lead_id__c = l.id
    WHERE rp.project_row_num = 1
      AND COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
      AND p.mpm4_base__status__c = 'Cancelled'
      AND TO_TIMESTAMP_NTZ(p.createddate) < rp.project_created_at
),

site_offboarding_records AS (
    SELECT
        OBJECT_CONSTRUCT_KEEP_NULL(*) AS offboarding_record
    FROM ANALYTICS.ADTHRIVE.SITE_OFFBOARDING
),

site_offboarding_events AS (
    SELECT
        offboarding_record,
        COALESCE(
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'site_id')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'siteid')::STRING, '')
        ) AS site_id,
        COALESCE(
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'site_offboarding_id')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'offboarding_id')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'id')::STRING, '')
        ) AS offboarding_id,
        COALESCE(
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'offboarded_at')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'offboarded_date')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'offboarding_date')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'completed_at')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'effective_date')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'updated_at')::STRING),
            TRY_TO_TIMESTAMP_NTZ(GET_IGNORE_CASE(offboarding_record, 'created_at')::STRING)
        ) AS offboarded_at,
        COALESCE(
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'dropped_reason')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'offboarding_reason')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'reason')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'reason_text')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'status_reason')::STRING, ''),
            'Offboarded'
        ) AS offboarding_reason,
        COALESCE(
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'dropped_reason_category')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'offboarding_reason_category')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'reason_category')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'category')::STRING, ''),
            'Offboarding'
        ) AS offboarding_reason_category,
        COALESCE(
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'reason_details')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'details')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'description')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'notes')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'note')::STRING, ''),
            NULLIF(GET_IGNORE_CASE(offboarding_record, 'comments')::STRING, ''),
            TO_JSON(offboarding_record)
        ) AS offboarding_description
    FROM site_offboarding_records
),

prior_site_offboardings AS (
    SELECT
        rp.return_project_id,
        so.site_id,
        so.offboarding_id,
        so.offboarded_at,
        so.offboarding_reason,
        so.offboarding_reason_category,
        so.offboarding_description,
        ROW_NUMBER() OVER (
            PARTITION BY rp.return_project_id
            ORDER BY so.offboarded_at DESC, so.offboarding_id DESC
        ) AS prior_offboarding_row_num
    FROM current_return_projects rp
    INNER JOIN site_offboarding_events so
        ON rp.site_id = so.site_id
    WHERE rp.project_row_num = 1
      AND so.offboarded_at IS NOT NULL
      AND so.offboarded_at < rp.project_created_at
),

supplemental_returning_site_drops AS (
    SELECT
        '' AS project_id,
        rp.site_id,
        rp.creator_name,
        rp.lead_contact,
        rp.company_name,
        rp.domain,
        rp.salesforce_account_id,
        rp.salesforce_lead_id,
        IFF(pso.site_id IS NOT NULL, 'Offboarded', 'Dropped') AS status,
        TO_VARCHAR(COALESCE(pso.offboarded_at, TO_TIMESTAMP_NTZ(h.updated_at)), 'YYYY-MM-DD') AS actual_close_date,
        rp.service_level,
        rp.vertical,
        rp.previous_ad_network,
        rp.onboarding_owner,
        rp.monthly_pageviews,
        rp.cg_involvement,
        rp.cg_effort,
        COALESCE(pso.offboarding_reason, pcop.prior_cancelled_reason, 'No reason captured') AS cancelled_reason,
        COALESCE(
            pso.offboarding_reason,
            IFF(
                REGEXP_LIKE(LOWER(COALESCE(pcop.prior_raw_description, '')), '^setup[[:space:]]+cancellation[[:space:]]+note'),
                'Cancelled Pre-onboarding',
                NULL
            ),
            IFF(
                LOWER(pcop.setup_cancellation_reason) IN ('note', 'notes', 'dropped')
                OR REGEXP_LIKE(LOWER(COALESCE(pcop.setup_cancellation_reason, '')), '(pre[-[:space:]0]?onboarding|never engaged)'),
                NULL,
                pcop.setup_cancellation_reason
            ),
            IFF(REGEXP_LIKE(LOWER(COALESCE(hdr.text, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, NULLIF(hdr.text, '')),
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_cancelled_reason, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_cancelled_reason),
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_dropped_reason, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_dropped_reason),
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_dropped_reason_category, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_dropped_reason_category),
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_reason_they_left, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_reason_they_left),
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_reason_left_specifics, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_reason_left_specifics),
            IFF(REGEXP_LIKE(LOWER(COALESCE(dr.text, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, NULLIF(dr.text, '')),
            IFF(REGEXP_LIKE(LOWER(COALESCE(se.non_standard_reason, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, NULLIF(se.non_standard_reason, '')),
            'No dropped reason captured'
        ) AS dropped_reason,
        COALESCE(
            pso.offboarding_reason_category,
            IFF(REGEXP_LIKE(LOWER(COALESCE(pcop.prior_dropped_reason_category, '')), '(pre[-[:space:]0]?onboarding|never engaged)'), NULL, pcop.prior_dropped_reason_category),
            NULLIF(hdrc.text, ''),
            NULLIF(drc.text, ''),
            IFF(pso.site_id IS NOT NULL, 'Offboarding', NULL)
        ) AS dropped_reason_category,
        COALESCE(
            NULLIF(pso.offboarding_description, ''),
            NULLIF(pcop.prior_raw_description, ''),
            'Supplemental return signal from current Salesforce onboarding project ' || rp.return_project_id
        ) AS raw_description,
        ROW_NUMBER() OVER (
            PARTITION BY rp.site_id, rp.return_project_id
            ORDER BY
                CASE WHEN pso.site_id IS NULL THEN 1 ELSE 0 END,
                COALESCE(pso.offboarded_at, TO_TIMESTAMP_NTZ(h.updated_at)) DESC
        ) AS prior_drop_row_num
    FROM current_return_projects rp
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_HISTORY h
        ON rp.site_id = h.id
       AND h.status IN ('Dropped', 'Canceled', 'Cancelled')
       AND TO_TIMESTAMP_NTZ(h.updated_at) < rp.project_created_at
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON hdr
        ON h.dropped_reason_id = hdr.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY hdrc
        ON hdr.dropped_reason_category_id = hdrc.id
    LEFT JOIN qualifying_dropped_onboards q
        ON rp.site_id = q.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON rp.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON dr
        ON se.dropped_reason_id = dr.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY drc
        ON dr.dropped_reason_category_id = drc.id
    LEFT JOIN prior_cancelled_onboarding_projects pcop
        ON rp.return_project_id = pcop.return_project_id
       AND pcop.prior_project_row_num = 1
    LEFT JOIN prior_site_offboardings pso
        ON rp.return_project_id = pso.return_project_id
       AND pso.prior_offboarding_row_num = 1
    WHERE rp.project_row_num = 1
      AND q.site_id IS NULL
      AND (pso.site_id IS NOT NULL OR h.id IS NOT NULL)
      AND (
        pso.site_id IS NOT NULL
        OR NOT REGEXP_LIKE(
          LOWER(
              COALESCE(
                  pcop.setup_cancellation_reason,
                  hdr.text,
                  pcop.prior_cancelled_reason,
                  pcop.prior_dropped_reason,
                  pcop.prior_dropped_reason_category,
                  pcop.prior_reason_they_left,
                  pcop.prior_reason_left_specifics,
                  pcop.prior_raw_description,
                  dr.text,
                  se.non_standard_reason,
                  ''
              )
          ),
          '(cancelled pre[-[:space:]0]?onboarding|pre[-[:space:]0]?onboarding|never engaged|duplicate|merged|new owner did not want to stay with adthrive|retiring site|left raptive|offboarding)'
        )
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
    cancelled_reason,
    dropped_reason,
    dropped_reason_category,
    raw_description
FROM qualifying_dropped_onboards

UNION ALL

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
    cancelled_reason,
    dropped_reason,
    dropped_reason_category,
    raw_description
FROM supplemental_returning_site_drops
WHERE prior_drop_row_num = 1
ORDER BY actual_close_date DESC
"""


RETURNED_ONBOARDS_QUERY = """
WITH qualifying_dropped_onboards AS (
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
      AND COALESCE(p.cancelled_reason__c, '') != 'Never Engaged'
      AND (
          COALESCE(p.cancelled_reason__c, '') != 'Cancelled Pre-onboarding'
          OR p.mpm4_base__description__c ILIKE '%setup cancellation%'
      )
      AND (
          p.mpm4_base__description__c ILIKE '%setup cancellation%'
          OR NOT REGEXP_LIKE(
              LOWER(COALESCE(dr.text, se.non_standard_reason, '')),
              '(cancelled pre[-[:space:]0]?onboarding|pre[-[:space:]0]?onboarding|never engaged|duplicate|merged|new owner did not want to stay with adthrive|retiring site|left raptive|offboarding)'
          )
      )
),

current_return_projects AS (
    SELECT
        p.id AS return_project_id,
        a.site_id AS site_id,
        p.name AS creator_name,
        l.name AS lead_contact,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        COALESCE(s.status, p.mpm4_base__status__c) AS current_status,
        TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c)) AS return_date,
        TO_TIMESTAMP_NTZ(p.createddate) AS project_created_at,
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
        ROW_NUMBER() OVER (
            PARTITION BY a.site_id, TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c))
            ORDER BY TO_TIMESTAMP_NTZ(p.createddate) DESC, p.id DESC
        ) AS project_row_num
    FROM ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
    LEFT JOIN ANALYTICS.SALESFORCE.LEAD l
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON l.site__c = a.account_id
    LEFT JOIN ANALYTICS.SALESFORCE.USER u
        ON p.ownerid = u.id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE_EXTENDED se
        ON a.site_id = se.site_id
    LEFT JOIN ANALYTICS.ADTHRIVE.SITE s
        ON a.site_id = s.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
      AND p.mpm4_base__status__c IN ('Active', 'Completed')
      AND COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c) IS NOT NULL
      AND YEAR(TO_DATE(COALESCE(s.install_date, p.scheduledinstalldate__c, p.expected_install_date__c))) >= 2025
      AND COALESCE(
          NULLIF(l.forecasted_service_level__c, ''),
          NULLIF(se.service_level, ''),
          NULLIF(se.service, ''),
          NULLIF(se.tier, '')
      ) IN ('Rise', 'Insider', 'Platinum', 'Platinum Elite', 'Luminary', 'Mid Market Enterprise')
      AND a.site_id IS NOT NULL
),

supplemental_returning_site_drops AS (
    SELECT
        '' AS project_id,
        rp.site_id,
        rp.creator_name,
        rp.company_name,
        TO_VARCHAR(TO_TIMESTAMP_NTZ(h.updated_at), 'YYYY-MM-DD') AS actual_close_date,
        TO_TIMESTAMP_NTZ(h.updated_at) AS actual_close_ts,
        rp.return_project_id,
        rp.current_status,
        rp.return_date,
        rp.project_created_at,
        ROW_NUMBER() OVER (
            PARTITION BY rp.site_id, rp.return_project_id
            ORDER BY TO_TIMESTAMP_NTZ(h.updated_at) DESC
        ) AS prior_drop_row_num
    FROM current_return_projects rp
    INNER JOIN ANALYTICS.ADTHRIVE.SITE_HISTORY h
        ON rp.site_id = h.id
    LEFT JOIN qualifying_dropped_onboards q
        ON rp.site_id = q.site_id
    WHERE rp.project_row_num = 1
      AND q.site_id IS NULL
      AND h.status IN ('Dropped', 'Canceled', 'Cancelled')
      AND TO_TIMESTAMP_NTZ(h.updated_at) < rp.project_created_at
),

dropped_onboards AS (
    SELECT
        project_id,
        site_id,
        creator_name,
        company_name,
        actual_close_date,
        actual_close_ts
    FROM qualifying_dropped_onboards

    UNION ALL

    SELECT
        project_id,
        site_id,
        creator_name,
        company_name,
        actual_close_date,
        actual_close_ts
    FROM supplemental_returning_site_drops
    WHERE prior_drop_row_num = 1
),

returned_candidates AS (
    SELECT
        d.project_id,
        d.site_id,
        COALESCE(rp.creator_name, d.creator_name) AS creator_name,
        COALESCE(rp.company_name, d.company_name) AS company_name,
        rp.current_status,
        TO_VARCHAR(rp.return_date, 'YYYY-MM-DD') AS expected_install_date,
        d.actual_close_date,
        rp.lead_contact,
        rp.service_level,
        rp.vertical,
        rp.previous_ad_network,
        rp.onboarding_owner,
        rp.monthly_pageviews,
        rp.project_created_at AS status_updated_at,
        0 AS source_priority
    FROM dropped_onboards d
    INNER JOIN current_return_projects rp
        ON d.site_id = rp.site_id
    WHERE rp.project_row_num = 1
      AND rp.return_date >= TO_DATE(d.actual_close_ts)
      AND rp.project_created_at > TO_TIMESTAMP_NTZ(d.actual_close_ts)

    UNION ALL

    SELECT
        d.project_id,
        d.site_id,
        d.creator_name,
        d.company_name,
        h1.status AS current_status,
        TO_VARCHAR(h1.install_date, 'YYYY-MM-DD') AS expected_install_date,
        d.actual_close_date,
        '' AS lead_contact,
        '' AS service_level,
        '' AS vertical,
        '' AS previous_ad_network,
        '' AS onboarding_owner,
        '' AS monthly_pageviews,
        TO_TIMESTAMP_NTZ(h1.updated_at) AS status_updated_at,
        1 AS source_priority
    FROM dropped_onboards d
    INNER JOIN ANALYTICS.ADTHRIVE.SITE_HISTORY h1
        ON d.site_id = h1.id
    WHERE (
          h1.status IN ('Install', 'Checkup', 'Active')
          OR (
              h1.status = 'Setup'
              AND YEAR(h1.install_date) = YEAR(CURRENT_DATE())
          )
      )
      AND h1.install_date IS NOT NULL
      AND TO_DATE(h1.install_date) >= TO_DATE(d.actual_close_ts)
      AND TO_TIMESTAMP_NTZ(h1.updated_at) > TO_TIMESTAMP_NTZ(d.actual_close_ts)

    UNION ALL

    SELECT
        d.project_id,
        d.site_id,
        d.creator_name,
        d.company_name,
        s.status AS current_status,
        TO_VARCHAR(s.install_date, 'YYYY-MM-DD') AS expected_install_date,
        d.actual_close_date,
        '' AS lead_contact,
        '' AS service_level,
        '' AS vertical,
        '' AS previous_ad_network,
        '' AS onboarding_owner,
        '' AS monthly_pageviews,
        TO_TIMESTAMP_NTZ(s.updated_at) AS status_updated_at,
        2 AS source_priority
    FROM dropped_onboards d
    INNER JOIN ANALYTICS.ADTHRIVE.SITE s
        ON d.site_id = s.id
    WHERE s.status = 'Setup'
      AND s.install_date IS NOT NULL
      AND YEAR(s.install_date) = YEAR(CURRENT_DATE())
      AND TO_DATE(s.install_date) >= TO_DATE(d.actual_close_ts)
      AND TO_TIMESTAMP_NTZ(s.updated_at) > TO_TIMESTAMP_NTZ(d.actual_close_ts)
),

returned_onboards AS (
    SELECT
        project_id,
        site_id,
        creator_name,
        company_name,
        current_status,
        expected_install_date,
        actual_close_date,
        lead_contact,
        service_level,
        vertical,
        previous_ad_network,
        onboarding_owner,
        monthly_pageviews,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(NULLIF(project_id, ''), site_id || '|' || actual_close_date)
            ORDER BY
                source_priority,
                TO_DATE(expected_install_date),
                CASE current_status
                    WHEN 'Active' THEN 1
                    WHEN 'Checkup' THEN 2
                    WHEN 'Install' THEN 3
                    WHEN 'Setup' THEN 4
                    ELSE 9
                END,
                status_updated_at
        ) AS row_num
    FROM returned_candidates
)

SELECT
    project_id,
    site_id,
    creator_name,
    company_name,
    current_status,
    actual_close_date,
    expected_install_date,
    lead_contact,
    service_level,
    vertical,
    previous_ad_network,
    onboarding_owner,
    monthly_pageviews
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
