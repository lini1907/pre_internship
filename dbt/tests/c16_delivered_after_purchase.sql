-- C16 delivered_customer_ts >= purchase_ts.
SELECT * FROM {{ ref('fact_orders') }} WHERE delivered_customer_ts < purchase_ts
