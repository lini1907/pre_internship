-- C03 Order with status 'delivered' has a customer delivery timestamp.
SELECT count(*) FILTER (WHERE delivered_customer_ts IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{orders}}
WHERE status = 'delivered';
