-- K8 Negative review share: reviews with score <= 2.
WITH w AS (
    SELECT *
    FROM fact_orders
    WHERE purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       avg(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END) AS value,
       NULL::INTEGER AS rank
FROM w
WHERE review_score IS NOT NULL;
