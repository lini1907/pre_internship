-- C09 Item seller_id exists in the seller table.
SELECT count(*) FILTER (WHERE i.seller_id IS NOT NULL AND s.seller_id IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{items}} i
LEFT JOIN (SELECT DISTINCT seller_id FROM {{sellers}}) s USING (seller_id);
