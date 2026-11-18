-- C21 Order has a customer key (protects K9 repeat rate and K10 active customers).
SELECT count(*) FILTER (WHERE customer_unique_id IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{orders}};
