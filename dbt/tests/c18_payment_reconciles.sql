-- C18 payment_total = sum(price + freight_value) within 1 BRL. Thresholds as in
-- dq_checks.yaml: warn above 0.5 %, fail above 1 % of 98,665 reconcilable orders.
{{ config(severity='error', warn_if='> 493', error_if='> 986') }}
WITH i AS (
    SELECT order_id, sum(price + freight_value) AS amount
    FROM {{ ref('fact_order_items') }}
    GROUP BY 1
)
SELECT o.order_id, o.payment_total, i.amount
FROM {{ ref('fact_orders') }} o
JOIN i USING (order_id)
WHERE o.payment_total IS NOT NULL AND abs(o.payment_total - i.amount) > 1.0
