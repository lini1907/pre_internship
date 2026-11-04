-- C10 Item order_id exists in the order table.
SELECT count(*) FILTER (WHERE i.order_id IS NOT NULL AND o.order_id IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{items}} i
LEFT JOIN (SELECT DISTINCT order_id FROM {{orders}}) o USING (order_id);
