-- C08 Item product_id exists in the product table (NULL keys are C01's business).
SELECT count(*) FILTER (WHERE i.product_id IS NOT NULL AND p.product_id IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{items}} i
LEFT JOIN (SELECT DISTINCT product_id FROM {{products}}) p USING (product_id);
