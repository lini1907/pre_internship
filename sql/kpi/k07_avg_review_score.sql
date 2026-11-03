-- K7 Average review score, one review per order, all orders in the window.
WITH w AS (
    SELECT *
    FROM fact_orders
    WHERE purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       avg(CAST(review_score AS DOUBLE)) AS value,
       NULL::INTEGER AS rank
FROM w
WHERE review_score IS NOT NULL;
