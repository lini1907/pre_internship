-- C18 payment_total = sum(price + freight_value) per order within $payment_tolerance BRL,
-- over orders that have both items and a payment. Mart only (needs payment_total).
WITH i AS (
    SELECT order_id, sum(price + freight_value) AS amount
    FROM {{items}}
    GROUP BY 1
)
SELECT count(*) FILTER (WHERE abs(o.payment_total - i.amount) > $payment_tolerance) AS n_failed,
       count(*) AS n_total
FROM {{orders}} o
JOIN i USING (order_id)
WHERE o.payment_total IS NOT NULL;
