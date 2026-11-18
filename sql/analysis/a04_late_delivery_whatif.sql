-- A04 What if fewer deliveries were late? Direct standardisation, not a causal estimate.
-- Late = delivered order with a delivery date after the estimated date (as K5).
-- For a target late share t, m = n_late - t * n_delivered late orders (with a review) are
-- moved to on time and take the mean score / negative share of on-time orders. K7 and K8
-- are then recomputed on their own populations (all reviewed orders in the window), so
-- the 'current' row reproduces K7 and K8 of the KPI spec.
WITH w AS (
    SELECT *,
           CASE WHEN is_delivered AND delivered_customer_ts IS NOT NULL
                THEN CAST(delivered_customer_ts AS DATE) > estimated_delivery_date END AS late
    FROM fact_orders
    WHERE purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
s AS (
    SELECT count(*) FILTER (WHERE late IS NOT NULL) AS n_delivered,
           count(*) FILTER (WHERE late) AS n_late,
           count(*) FILTER (WHERE review_score IS NOT NULL) AS n_reviews,
           sum(review_score) AS sum_score,
           sum(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) AS n_negative,
           count(*) FILTER (WHERE late AND review_score IS NOT NULL) AS n_late_reviewed,
           avg(review_score) FILTER (WHERE late) AS mean_late,
           avg(review_score) FILTER (WHERE NOT late) AS mean_on_time,
           avg(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END)
               FILTER (WHERE late AND review_score IS NOT NULL) AS neg_late,
           avg(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END)
               FILTER (WHERE NOT late AND review_score IS NOT NULL) AS neg_on_time
    FROM w
),
t AS (
    SELECT 'current' AS scenario, NULL::DOUBLE AS target UNION ALL
    SELECT '5 %', 0.05 UNION ALL
    SELECT '3 %', 0.03 UNION ALL
    SELECT '0 %', 0.0
),
m AS (
    SELECT t.scenario,
           coalesce(t.target, s.n_late / s.n_delivered) AS late_share,
           -- reviewed late orders moved to on time, in proportion to all late orders moved
           greatest(0.0, s.n_late - coalesce(t.target, s.n_late / s.n_delivered) * s.n_delivered)
               * s.n_late_reviewed / s.n_late AS moved,
           s.*
    FROM t CROSS JOIN s
)
SELECT scenario,
       late_share,
       1 - late_share AS on_time_share,
       round(moved) AS moved_reviews,
       (sum_score + moved * (mean_on_time - mean_late)) / n_reviews AS avg_review_score,
       (n_negative + moved * (neg_on_time - neg_late)) / n_reviews AS negative_share,
       mean_on_time,
       mean_late,
       neg_on_time,
       neg_late,
       n_delivered,
       n_late,
       n_reviews
FROM m
ORDER BY late_share DESC;
