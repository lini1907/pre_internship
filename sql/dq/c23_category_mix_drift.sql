-- C23 Category mix drift: aggregate counts only, no per-product snapshot.
-- Expected lines of a category = n_ref * N_cur / N_ref. A category drifts when
-- |n_cur - n_exp| > $drift_z * sqrt(n_exp) + $drift_min_abs.
-- n_failed = drifting categories, n_total = categories in either load.
WITH ref AS (
    SELECT coalesce(p.category_en, '(none)') AS category, count(*) AS n
    FROM {{ref_items}} i
    LEFT JOIN {{ref_products}} p ON i.product_id = p.product_id
    GROUP BY 1
),
cur AS (
    SELECT coalesce(p.category_en, '(none)') AS category, count(*) AS n
    FROM {{items}} i
    LEFT JOIN {{products}} p ON i.product_id = p.product_id
    GROUP BY 1
),
tot AS (
    SELECT (SELECT sum(n) FROM ref)::DOUBLE AS n_ref_all,
           (SELECT sum(n) FROM cur)::DOUBLE AS n_cur_all
),
j AS (
    SELECT coalesce(r.n, 0) * t.n_cur_all / t.n_ref_all AS n_exp,
           coalesce(c.n, 0) AS n_cur
    FROM ref r
    FULL JOIN cur c ON r.category = c.category
    CROSS JOIN tot t
)
SELECT count(*) FILTER (
           WHERE abs(n_cur - n_exp) > $drift_z * sqrt(n_exp) + $drift_min_abs
       ) AS n_failed,
       count(*) AS n_total
FROM j;
