-- K10 Active customers: distinct customers with >= 1 delivered order.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       CAST(count(DISTINCT customer_unique_id) AS DOUBLE) AS value,
       NULL::INTEGER AS rank
FROM d;
