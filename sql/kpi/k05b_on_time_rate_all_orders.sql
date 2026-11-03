-- K5 alternative: all orders in the window with an estimated date; orders not
-- delivered (or with no delivery date) count as not on time. Robustness only.
WITH w AS (
    SELECT *
    FROM fact_orders
    WHERE purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       avg(CASE WHEN is_delivered
                 AND delivered_customer_ts IS NOT NULL
                 AND CAST(delivered_customer_ts AS DATE) <= estimated_delivery_date
                THEN 1.0 ELSE 0.0 END) AS value,
       NULL::INTEGER AS rank
FROM w
WHERE estimated_delivery_date IS NOT NULL;
