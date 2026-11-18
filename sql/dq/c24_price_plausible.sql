-- C24 Price plausible within its category. Reference statistics per category on
-- log(price): median and MAD (median absolute deviation). Categories with fewer than
-- $price_min_items reference lines, or MAD = 0, use the global median and MAD.
-- n_failed = lines with price > 0 and |log(price) - median| > $price_k * MAD,
-- n_total = lines with price > 0 (price <= 0 is C11's job).
WITH ref AS (
    SELECT coalesce(p.category_en, '(none)') AS category, ln(i.price::DOUBLE) AS lp
    FROM {{ref_items}} i
    LEFT JOIN {{ref_products}} p ON i.product_id = p.product_id
    WHERE i.price > 0
),
cat_med AS (
    SELECT category, median(lp) AS med, count(*) AS n FROM ref GROUP BY 1
),
cat AS (
    SELECT m.category, m.med, median(abs(r.lp - m.med)) AS mad
    FROM ref r
    JOIN cat_med m ON r.category = m.category
    WHERE m.n >= $price_min_items
    GROUP BY m.category, m.med
),
global_med AS (SELECT median(lp) AS med FROM ref),
global_stats AS (
    SELECT g.med, median(abs(r.lp - g.med)) AS mad FROM ref r CROSS JOIN global_med g GROUP BY g.med
),
cur AS (
    SELECT coalesce(p.category_en, '(none)') AS category, ln(i.price::DOUBLE) AS lp
    FROM {{items}} i
    LEFT JOIN {{products}} p ON i.product_id = p.product_id
    WHERE i.price > 0
)
SELECT count(*) FILTER (
           WHERE abs(c.lp - CASE WHEN s.mad > 0 THEN s.med ELSE g.med END)
                 > $price_k * CASE WHEN s.mad > 0 THEN s.mad ELSE g.mad END
       ) AS n_failed,
       count(*) AS n_total
FROM cur c
LEFT JOIN cat s ON c.category = s.category
CROSS JOIN global_stats g;
