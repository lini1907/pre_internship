-- C05 order_id unique: rows whose order_id occurs more than once.
WITH k AS (SELECT order_id, count(*) AS n FROM {{orders}} GROUP BY 1)
SELECT coalesce(sum(n) FILTER (WHERE n > 1), 0) AS n_failed,
       coalesce(sum(n), 0) AS n_total
FROM k;
