-- C04 A review row (review_id present) has a score.
SELECT count(*) FILTER (WHERE review_score IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{reviews}}
WHERE review_id IS NOT NULL;
