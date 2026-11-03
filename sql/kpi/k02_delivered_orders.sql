-- K2 Delivered orders: distinct delivered orders in the window.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       CAST(count(DISTINCT order_id) AS DOUBLE) AS value,
       NULL::INTEGER AS rank
FROM d;
