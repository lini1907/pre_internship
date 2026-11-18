-- C22 Product category unchanged vs the reference snapshot (last accepted load):
-- n_failed = products whose category_en differs (NULL counts as a value),
-- n_total = products present in both loads.
SELECT count(*) FILTER (WHERE c.category_en IS DISTINCT FROM r.category_en) AS n_failed,
       count(*) AS n_total
FROM {{products}} c
JOIN {{ref_products}} r ON c.product_id = r.product_id;
