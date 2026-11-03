-- K9 Repeat customer rate: share of active customers with >= 2 delivered orders.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
per_customer AS (
    SELECT customer_unique_id, count(DISTINCT order_id) AS n_orders
    FROM d
    WHERE customer_unique_id IS NOT NULL
    GROUP BY 1
)
SELECT NULL::VARCHAR AS item,
       avg(CASE WHEN n_orders >= 2 THEN 1.0 ELSE 0.0 END) AS value,
       NULL::INTEGER AS rank
FROM per_customer;
