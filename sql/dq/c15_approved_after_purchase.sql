-- C15 approved_ts >= purchase_ts, over orders where both are present.
SELECT count(*) FILTER (WHERE approved_ts < purchase_ts) AS n_failed,
       count(*) AS n_total
FROM {{orders}}
WHERE approved_ts IS NOT NULL AND purchase_ts IS NOT NULL;
