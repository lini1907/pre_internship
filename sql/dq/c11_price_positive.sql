-- C11 price > 0 (a NULL price, e.g. failed cast, also fails).
SELECT count(*) FILTER (WHERE price IS NULL OR price <= 0) AS n_failed,
       count(*) AS n_total
FROM {{items}};
