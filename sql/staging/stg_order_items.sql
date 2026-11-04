-- One row per (order_id, order_item_id).
SELECT order_id,
       TRY_CAST(order_item_id AS INTEGER)         AS order_item_id,
       product_id,
       seller_id,
       TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
       TRY_CAST(price AS DECIMAL(12,2))           AS price,
       TRY_CAST(freight_value AS DECIMAL(12,2))   AS freight_value
FROM order_items
QUALIFY row_number() OVER (PARTITION BY order_id, order_item_id ORDER BY product_id) = 1
ORDER BY order_id, order_item_id;
