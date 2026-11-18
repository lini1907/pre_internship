-- A05 Late deliveries and negative reviews by customer state (window and late as A04).
-- share_of_late = the state's late orders / all late orders;
-- share_of_negative = the state's negative reviews (score <= 2) / all negative reviews.
WITH w AS (
    SELECT o.*,
           coalesce(c.state, $unknown_label) AS state,
           CASE WHEN o.is_delivered AND o.delivered_customer_ts IS NOT NULL
                THEN CAST(o.delivered_customer_ts AS DATE) > o.estimated_delivery_date END AS late
    FROM fact_orders o
    LEFT JOIN dim_customer c ON c.customer_unique_id = o.customer_unique_id
    WHERE o.purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND o.purchase_ts <  CAST($window_end AS TIMESTAMP)
),
g AS (
    SELECT state,
           count(*) FILTER (WHERE late IS NOT NULL) AS n_delivered,
           count(*) FILTER (WHERE late) AS n_late,
           count(*) FILTER (WHERE review_score IS NOT NULL) AS n_reviews,
           count(*) FILTER (WHERE review_score <= 2) AS n_negative
    FROM w
    GROUP BY 1
)
SELECT state,
       n_delivered,
       n_late,
       1 - n_late / n_delivered AS on_time_rate,
       n_late / sum(n_late) OVER () AS share_of_late,
       n_delivered / sum(n_delivered) OVER () AS share_of_delivered,
       n_negative,
       n_negative / n_reviews AS negative_share,
       n_negative / sum(n_negative) OVER () AS share_of_negative
FROM g
ORDER BY on_time_rate;
