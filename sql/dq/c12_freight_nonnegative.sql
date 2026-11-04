-- C12 freight_value >= 0 (a NULL value also fails).
SELECT count(*) FILTER (WHERE freight_value IS NULL OR freight_value < 0) AS n_failed,
       count(*) AS n_total
FROM {{items}};
