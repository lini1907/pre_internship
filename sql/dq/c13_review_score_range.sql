-- C13 review_score in 1..5 where present (missing scores are C04's business).
SELECT count(*) FILTER (WHERE review_score NOT BETWEEN 1 AND 5) AS n_failed,
       count(*) AS n_total
FROM {{reviews}}
WHERE review_score IS NOT NULL;
