-- K5 On-time delivery rate: delivered orders with a delivery date, delivered on or
-- before the estimated date.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       avg(CASE WHEN CAST(delivered_customer_ts AS DATE) <= estimated_delivery_date
                THEN 1.0 ELSE 0.0 END) AS value,
       NULL::INTEGER AS rank
FROM d
WHERE delivered_customer_ts IS NOT NULL;
