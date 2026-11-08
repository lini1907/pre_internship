-- One row per invoice line. price holds the line revenue Quantity x Price, so the Olist
-- KPI queries (which sum price) give revenue. One synthetic seller, no freight.
SELECT l.invoice                                                        AS order_id,
       CAST(row_number() OVER (PARTITION BY l.invoice ORDER BY l.src_row) AS INTEGER)
                                                                        AS order_item_id,
       l.stock_code                                                     AS product_id,
       'online_retail_ii'                                               AS seller_id,
       CAST(round(l.quantity * l.unit_price, 2) AS DECIMAL(12,2))       AS price,
       CAST(0 AS DECIMAL(12,2))                                         AS freight_value,
       CAST(strftime(o.purchase_ts, '%Y%m%d') AS INTEGER)               AS purchase_date_key
FROM stg_retail_lines l
JOIN fact_orders o ON o.order_id = l.invoice
ORDER BY order_id, order_item_id;
