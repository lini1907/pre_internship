-- C06 (order_id, order_item_id) unique: item rows whose key occurs more than once.
WITH k AS (SELECT order_id, order_item_id, count(*) AS n FROM {{items}} GROUP BY 1, 2)
SELECT coalesce(sum(n) FILTER (WHERE n > 1), 0) AS n_failed,
       coalesce(sum(n), 0) AS n_total
FROM k;
