-- C16 delivered_customer_ts >= purchase_ts, over orders where both are present.
SELECT count(*) FILTER (WHERE delivered_customer_ts < purchase_ts) AS n_failed,
       count(*) AS n_total
FROM {{orders}}
WHERE delivered_customer_ts IS NOT NULL AND purchase_ts IS NOT NULL;
