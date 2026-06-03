-- Search Salesforce MPM4 onboarding projects for records that still show
-- "No dropped reason captured" or "No reason captured" in the dashboard.
--
-- Refresh the missing_dashboard_rows CTE from outputs/master_creator_lifecycle.csv
-- whenever the dashboard output changes.

WITH missing_dashboard_rows AS (
    SELECT
        column1::STRING AS creator_project_name,
        column2::STRING AS site_id,
        column3::STRING AS original_project_id,
        column4::STRING AS lead_id,
        column5::STRING AS current_return_project_id,
        TRY_TO_DATE(column6::STRING) AS dashboard_dropped_date,
        TRY_TO_DATE(column7::STRING) AS dashboard_returned_date
    FROM VALUES
    -- creator_project_name, site_id, original_project_id, lead_id, current_return_project_id, dropped_date, returned_date
    ('3 Boys and a Dog', '5522f40fbe3448091ab7bcf4', NULL, '00QQQ000003eIDt2AM', 'a0zQQ000000slzlYAA', '2015-07-06', '2025-03-17'),
    ('Help Desk Geek', '55de4d1ea78f2e9878d0e898', NULL, '00QQQ00000aONLJ2A4', 'a0zQQ000001x1dpYAA', '2015-10-06', '2025-12-02'),
    ('My Korean Kitchen', '55380bb605cc33812da7c3d3', NULL, '00QQQ00000Htp1j2AB', 'a0zQQ000000uguEYAQ', '2015-10-06', '2025-03-04'),
    ('Pressure Cooking Today', '54d1050962b8716849f48e0f', NULL, '00QQQ00000HFxSb2AL', 'a0zQQ0000016RGHYA2', '2015-12-21', '2025-06-06'),
    ('Just a Taste', '52e41fac28963d1e058a10ae', NULL, '00Q5x00001vaFKhEAM', 'a0zQQ000000edkHYAQ', '2016-01-07', '2025-01-27'),
    ('Kitchen Confidante', '54d12abe62b8716849f48e64', NULL, '00Q5x00001xKsHxEAK', 'a0zQQ000001hskXYAQ', '2016-02-09', '2025-10-10'),
    ('Gluten Free on a Shoestring', '533f020b208f222c05b9ab95', NULL, '00QQQ00000Xw4OP2AZ', 'a0zQQ000001ntIvYAI', '2016-03-24', '2025-11-12'),
    ('Happy Food Healthy Life', '56f4279bdd56ec5643398ef6', NULL, '00QQQ000003eJv52AE', 'a0zQQ000000ntEfYAI', '2016-03-29', '2025-02-10'),
    ('Nums the Word', '570d5595fcce490d501b840e', NULL, '00QQQ00000cfyWz2AI', 'a0zQQ0000024uAXYAY', '2016-04-20', '2026-02-19'),
    ('Eat Move Make', '56d4acae237d8cd15edc1b38', NULL, '00QQQ000003eJHP2A2', 'a0zQQ000001tcorYAA', '2016-11-07', '2025-12-11'),
    ('Winners and Whiners', '5826285bbbb11e24413c230d', NULL, '00QQQ00000YbY8n2AF', 'a0zQQ0000023I5hYAE', '2016-11-18', '2025-12-16'),
    ('A Couple Cooks', '5533ffb81b46c7a36131c008', NULL, '00Q5x00001vaFGoEAM', 'a0zQQ000001WNaQYAW', '2017-02-17', '2025-12-15'),
    ('Bakerita', '54d24d60ec021aa13d386610', NULL, '00QQQ000003eHBW2A2', 'a0zQQ000000yEMfYAM', '2017-07-05', '2025-04-11'),
    ('Joyful Healthy Eats', '5472257891928b9f442a157c', NULL, '00Q5x00001vaFGzEAM', 'a0zQQ000001jtarYAA', '2017-07-05', '2025-10-29'),
    ('My Crazy Good Life', '54ea232532f8764f151df10a', NULL, '00QQQ000003eINR2A2', 'a0zQQ000001dzuHYAQ', '2017-07-05', '2025-09-22'),
    ('The Gunny Sack', '550c5a5d7606971a32702a9f', NULL, '00QQQ00000H0FRu2AN', 'a0zQQ000000qhH0YAI', '2017-07-05', '2025-02-24'),
    ('Dear Crissy', '5483d57f141d31737f20ce8f', NULL, '00QQQ0000065ldC2AQ', 'a0zQQ00000127CwYAI', '2018-06-04', '2025-04-24'),
    ('Mens Hairstyles Today', '582a237d9fd48e1540c4bdc8', NULL, '00QQQ00000Fhk8c2AB', 'a0zQQ000000nGYHYA2', '2018-11-20', '2025-01-09'),
    ('Live Laugh Rowe', '52e41fac28963d1e058a0fbe', NULL, '00QQQ000003eIgP2AU', 'a0zQQ000001ulWjYAI', '2018-12-20', '2026-01-08'),
    ('Fifteen Spatulas', '52e41fac28963d1e058a10ab', NULL, '00Q5x00001zzlcLEAQ', 'a0zQQ0000024TwjYAE', '2019-01-02', '2026-02-09'),
    ('Texanerin Baking', '52e41fac28963d1e058a111a', NULL, '00QQQ00000HeABl2AN', 'a0zQQ000000u19VYAQ', '2019-01-02', '2025-02-24'),
    ('WonkyWonderful', '54d0432d6a4dd9277372a375', NULL, '00Q5x00001vaFOgEAM', 'a0zQQ000000sVTRYA2', '2019-01-02', '2025-03-03'),
    ('My JoyFilled Life', '5ba5404602763b77649ff2a9', NULL, '00Q5x000021xzo9EAA', 'a0zQQ000001itjNYAQ', '2019-01-28', '2025-11-12'),
    ('The Forked Spoon', '5b914c3c377d57533c0af6f4', NULL, '00Q5x00001vaFOjEAM', 'a0zQQ000001RhczYAC', '2019-01-28', '2025-07-24'),
    ('Sweet and Savory Meals', '5705392d93a5b36d267b523a', NULL, '00Q5x00001vaFHYEA2', 'a0zQQ000002BkxdYAC', '2019-03-21', '2026-03-19'),
    ('How To Feed a Loon', '59790101d83d246969d21c87', NULL, '00Q5x00001vaFONEA2', 'a0zQQ000000tQ6kYAE', '2019-03-23', '2025-03-03'),
    ('Living Life and Learning', '59d398752867725e947abce6', NULL, '00QQQ000003eH2m2AE', 'a0zQQ000000slzkYAA', '2019-04-04', '2025-03-10'),
    ('Bites of Wellness', '5717ad1e6c368c7a243933d7', NULL, '00Q5x0000239pzCEAQ', 'a0zQQ0000028hUrYAI', '2019-04-18', '2026-02-24'),
    ('The Shortcut Kitchen', '546a0eacc90ce559719e4a9f', NULL, '00Q5x00001xKsI4EAK', 'a0zQQ000000vtmBYAQ', '2019-09-19', '2025-03-24'),
    ('Eat Plant Based', '5ace1689fdf4d60603ac26b7', NULL, '00Q5x00001vaFZXEA2', 'a0zQQ000001qV2LYAU', '2019-11-13', '2025-11-17'),
    ('The Teachers Corner', '5c1bb987d50b3a63b796d6db', NULL, '00Q5x000021xznREAQ', 'a0zQQ000000y82kYAA', '2021-08-17', '2025-02-28'),
    ('Fayetteville Flyer', '62b208b4d045780f5c6d8f99', 'a0z5x000007s1W9AAI', '00Q5x00001xHxDpEAK', NULL, '2022-07-08', NULL),
    ('Visa Traveler', '62a8af8a59ba352455ab9204', 'a0z5x000007s1QjAAI', '00Q5x00001vaCu1EAE', NULL, '2022-07-15', '2024-02-01'),
    ('Bake With Zoha', '64415c41eaccad32ac8465e5', 'a0z5x0000085KbLAAU', '00Q5x000021xpxNEAQ', NULL, '2023-05-01', '2026-05-20'),
    ('All Our Way', '5c080446fd6d033a22e8a49a', NULL, '00Q5x000021xznbEAA', 'a0zQQ000001RmftYAC', '2024-04-02', '2025-07-24'),
    ('Bake Play Smile', '6103edc7498239473fae8303', NULL, '00Q5x00001vaBaTEAU', 'a0zQQ000001GipJYAS', '2024-04-02', '2025-06-23'),
    ('Best Friends for Frosting', '552c7fbc26d3e4df4c3e3f2a', NULL, '00QQQ00000KHyPW2A1', 'a0zQQ00000195CqYAI', '2024-04-02', '2025-04-25'),
    ('Cooked By Julie', '5e590a1789dac4203c8dd5bc', NULL, '00Q5x000021xznaEAA', 'a0zQQ0000028hTFYAY', '2024-04-02', '2026-02-24'),
    ('Dishing Delish', '5898e280102dce663953a9ef', NULL, '00Q5x00001xKsILEA0', 'a0zQQ0000014V6IYAU', '2024-04-02', '2025-04-09'),
    ('Easy Chicken Recipes', '5e62bc086513c03504b0be1d', NULL, '00Q5x00001xKsHqEAK', 'a0zQQ000000vtmAYAQ', '2024-04-02', '2025-03-06'),
    ('Easy Dessert Recipes', '6023fc2d6f0af52a26150fb8', NULL, '00QQQ00000HYUeb2AH', 'a0zQQ000000wF57YAE', '2024-04-02', '2025-03-06'),
    ('Framed Cooks', '55f071e2cddcac1d5691a70c', NULL, '00QQQ000003Y3rP2AS', 'a0zQQ000000slzjYAA', '2024-04-02', '2025-03-03'),
    ('Guitar Chalk', '5d419d4961741c0f49d7dcae', NULL, '00Q5x00001vaBVDEA2', 'a0zQQ000001EdqXYAS', '2024-04-02', '2025-05-12'),
    ('Healthy Delicious', '5435faca308860033bbe959e', NULL, '00QQQ000003eHss2AE', 'a0zQQ000000z1vGYAQ', '2024-04-02', '2025-03-26'),
    ('Oh My Creative', '5637a1c5b82a4cb51248c0f6', NULL, '00QQQ000003eJI22AM', 'a0zQQ000001Uvl4YAC', '2024-04-02', '2025-08-11'),
    ('One Good Thing by Jillee', '54d189e462b8716849f48f81', NULL, '00QQQ000003eGjh2AE', 'a0zQQ000001PdgkYAC', '2024-04-02', '2025-07-21'),
    ('Spanish Sabores', '589337e52999a804e6ebea6a', NULL, '00QQQ000003eGjS2AU', 'a0zQQ0000017H0MYAU', '2024-04-02', '2025-05-20'),
    ('Spatula Desserts', '615e0f1e2b7fa25dd32afe34', NULL, '00Q5x000021xze6EAA', 'a0zQQ000001Z7fZYAS', '2024-04-02', '2025-09-02'),
    ('Tara Thueson', '5c4b7e6ff4b70d2a1d87a0dd', NULL, '00QQQ00000J8Qor2AF', 'a0zQQ000000yYIHYA2', '2024-04-02', '2025-04-16'),
    ('Trip Memos', '61001c514982396f63ae82ef', NULL, '00QQQ00000HeANA2A3', 'a0zQQ000000top1YAA', '2024-04-02', '2025-03-10'),
    ('Knicks X Factor', '6924a2bc67e0ae02c7f69ca4', NULL, '00QQQ00000eWSzr2AG', NULL, '2025-12-29', '2026-01-26'),
    ('30 Minutes Meals', '597f82716381da4ca308dfe2', NULL, '00Q5x0000239qKiEAI', 'a0zQQ000002NBw5YAG', '2026-02-13', '2026-03-31'),
    ('A Latte Food', '561288d945401d195f232e88', NULL, '00Q5x00001vaFOkEAM', 'a0zQQ000002Y9J3YAK', '2026-02-13', '2026-05-14'),
    ('Soap Opera Spy', '57c5f8a5caa6beea5b64965e', NULL, '00QQQ00000jqoLN2AY', 'a0zQQ000002T9rZYAS', '2026-02-13', '2026-05-06'),
    ('Hold To Reset', '5b27d8239be6984315ea479f', NULL, '00QQQ00000pGdko2AC', 'a0zQQ000002dlU9YAI', '2026-04-03', '2026-06-01')
),

project_candidates AS (
    SELECT
        m.creator_project_name AS dashboard_creator,
        m.site_id AS dashboard_site_id,
        m.original_project_id AS dashboard_original_project_id,
        m.lead_id AS dashboard_lead_id,
        m.current_return_project_id AS dashboard_current_return_project_id,
        m.dashboard_dropped_date,
        m.dashboard_returned_date,
        CASE
            WHEN p.id = m.original_project_id THEN 1
            WHEN p.id = m.current_return_project_id THEN 2
            WHEN p.related_lead_id__c = m.lead_id THEN 3
            WHEN a.site_id = m.site_id THEN 4
            ELSE 5
        END AS candidate_match_rank,
        p.id AS project_id,
        p.name AS project_name,
        p.record_type_name__c AS record_type_name,
        p.mpm4_base__status__c AS project_status,
        TO_VARCHAR(TRY_TO_TIMESTAMP_NTZ(p.createddate), 'YYYY-MM-DD') AS project_created_date,
        TO_VARCHAR(p.project_cancelled_date, 'YYYY-MM-DD') AS project_cancelled_date,
        l.id AS lead_id,
        l.name AS lead_contact,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        a.site_id,
        NULLIF(p.cancelled_reason__c, '') AS cancelled_reason,
        NULLIF(p.dropped_reason__c, '') AS dropped_reason_raw,
        NULLIF(dr.text, '') AS dropped_reason_lookup,
        NULLIF(p.dropped_reason_category__c, '') AS dropped_reason_category_raw,
        NULLIF(drc.text, '') AS dropped_reason_category_lookup,
        NULLIF(p.reason_they_left__c, '') AS reason_they_left,
        NULLIF(p.reasontheyleftspecifics__c, '') AS reason_they_left_specifics,
        NULLIF(
            TRIM(
                REGEXP_SUBSTR(
                    p.mpm4_base__description__c,
                    '(setup cancellation|setup cancelled|cancelled pre[-[:space:]]?onboarding).{0,300}',
                    1,
                    1,
                    'i'
                )
            ),
            ''
        ) AS setup_cancellation_description_match,
        NULLIF(p.mpm4_base__description__c, '') AS raw_description
    FROM missing_dashboard_rows m
    INNER JOIN ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
        ON p.id IN (m.original_project_id, m.current_return_project_id)
        OR p.related_lead_id__c = m.lead_id
    LEFT JOIN ANALYTICS.SALESFORCE.LEAD l
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON l.site__c = a.account_id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON dr
        ON p.dropped_reason__c = dr.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY drc
        ON COALESCE(p.dropped_reason_category__c, dr.dropped_reason_category_id) = drc.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
),

site_project_candidates AS (
    SELECT
        m.creator_project_name AS dashboard_creator,
        m.site_id AS dashboard_site_id,
        m.original_project_id AS dashboard_original_project_id,
        m.lead_id AS dashboard_lead_id,
        m.current_return_project_id AS dashboard_current_return_project_id,
        m.dashboard_dropped_date,
        m.dashboard_returned_date,
        4 AS candidate_match_rank,
        p.id AS project_id,
        p.name AS project_name,
        p.record_type_name__c AS record_type_name,
        p.mpm4_base__status__c AS project_status,
        TO_VARCHAR(TRY_TO_TIMESTAMP_NTZ(p.createddate), 'YYYY-MM-DD') AS project_created_date,
        TO_VARCHAR(p.project_cancelled_date, 'YYYY-MM-DD') AS project_cancelled_date,
        l.id AS lead_id,
        l.name AS lead_contact,
        COALESCE(NULLIF(l.company, ''), NULLIF(a.account_name, '')) AS company_name,
        a.site_id,
        NULLIF(p.cancelled_reason__c, '') AS cancelled_reason,
        NULLIF(p.dropped_reason__c, '') AS dropped_reason_raw,
        NULLIF(dr.text, '') AS dropped_reason_lookup,
        NULLIF(p.dropped_reason_category__c, '') AS dropped_reason_category_raw,
        NULLIF(drc.text, '') AS dropped_reason_category_lookup,
        NULLIF(p.reason_they_left__c, '') AS reason_they_left,
        NULLIF(p.reasontheyleftspecifics__c, '') AS reason_they_left_specifics,
        NULLIF(
            TRIM(
                REGEXP_SUBSTR(
                    p.mpm4_base__description__c,
                    '(setup cancellation|setup cancelled|cancelled pre[-[:space:]]?onboarding).{0,300}',
                    1,
                    1,
                    'i'
                )
            ),
            ''
        ) AS setup_cancellation_description_match,
        NULLIF(p.mpm4_base__description__c, '') AS raw_description
    FROM missing_dashboard_rows m
    INNER JOIN ANALYTICS.SALESFORCE.ACCOUNT a
        ON m.site_id = a.site_id
    INNER JOIN ANALYTICS.SALESFORCE.LEAD l
        ON l.site__c = a.account_id
    INNER JOIN ANALYTICS.SALESFORCE.MPM4_BASE__MILESTONE1_PROJECT__C p
        ON p.related_lead_id__c = l.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON dr
        ON p.dropped_reason__c = dr.id
    LEFT JOIN ANALYTICS.ADTHRIVE.DROPPED_REASON_CATEGORY drc
        ON COALESCE(p.dropped_reason_category__c, dr.dropped_reason_category_id) = drc.id
    WHERE COALESCE(p.isdeleted, FALSE) = FALSE
      AND p.record_type_name__c = 'Onboarding'
),

scored_candidates AS (
    SELECT DISTINCT
        *,
        CASE
            WHEN cancelled_reason = 'Blogger missed deadline' THEN 'Non-responsive'
            WHEN cancelled_reason = 'Blogger refused ads' THEN 'Refused ad layout'
            ELSE cancelled_reason
        END AS normalized_cancelled_reason,
        COALESCE(
            dropped_reason_lookup,
            dropped_reason_raw,
            reason_they_left,
            reason_they_left_specifics,
            CASE
                WHEN cancelled_reason = 'Blogger missed deadline' THEN 'Non-responsive'
                WHEN cancelled_reason = 'Blogger refused ads' THEN 'Refused ad layout'
                ELSE cancelled_reason
            END,
            setup_cancellation_description_match
        ) AS possible_dashboard_dropped_reason,
        COALESCE(dropped_reason_category_lookup, dropped_reason_category_raw) AS possible_dashboard_dropped_reason_category
    FROM (
        SELECT * FROM project_candidates
        UNION
        SELECT * FROM site_project_candidates
    )
)

SELECT
    dashboard_creator,
    dashboard_site_id,
    dashboard_dropped_date,
    dashboard_returned_date,
    candidate_match_rank,
    project_id,
    project_name,
    project_status,
    project_created_date,
    project_cancelled_date,
    lead_id,
    lead_contact,
    company_name,
    possible_dashboard_dropped_reason,
    possible_dashboard_dropped_reason_category,
    normalized_cancelled_reason,
    dropped_reason_lookup,
    dropped_reason_raw,
    reason_they_left,
    reason_they_left_specifics,
    setup_cancellation_description_match,
    raw_description
FROM scored_candidates
WHERE possible_dashboard_dropped_reason IS NOT NULL
   OR possible_dashboard_dropped_reason_category IS NOT NULL
   OR setup_cancellation_description_match IS NOT NULL
   OR REGEXP_LIKE(
        LOWER(COALESCE(raw_description, '')),
        '(cancel|drop|left|switched|switching|network|pause|ghost|mcm|gam|setup)'
   )
ORDER BY
    dashboard_creator,
    candidate_match_rank,
    project_cancelled_date DESC NULLS LAST,
    project_created_date DESC NULLS LAST,
    project_id;
