-- K1 Gross merchandise value: sum of item price over delivered orders in the window.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       CAST(sum(i.price) AS DOUBLE) AS value,
       NULL::INTEGER AS rank
FROM fact_order_items i
JOIN d USING (order_id);
