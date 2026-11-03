-- K6 Mean delivery time in days, purchase to customer delivery.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       avg(date_diff('second', purchase_ts, delivered_customer_ts) / 86400.0) AS value,
       NULL::INTEGER AS rank
FROM d
WHERE delivered_customer_ts IS NOT NULL;
