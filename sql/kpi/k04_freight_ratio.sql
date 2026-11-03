-- K4 Freight ratio: sum(freight_value) / sum(price) over delivered orders.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       CAST(sum(i.freight_value) / nullif(sum(i.price), 0) AS DOUBLE) AS value,
       NULL::INTEGER AS rank
FROM fact_order_items i
JOIN d USING (order_id);
