-- C07 review_id unique among rows that carry a review. Olist reuses a review_id when one
-- review covers several orders, so the clean data has a residual level (dq_catalogue.md).
WITH k AS (
    SELECT review_id, count(*) AS n FROM {{reviews}} WHERE review_id IS NOT NULL GROUP BY 1
)
SELECT coalesce(sum(n) FILTER (WHERE n > 1), 0) AS n_failed,
       coalesce(sum(n), 0) AS n_total
FROM k;
