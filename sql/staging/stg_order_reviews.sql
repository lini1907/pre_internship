-- One review per order: latest review_answer_timestamp, ties broken by review_id
-- (KPI decision 3). review_id stays non-unique where one review covers several orders.
SELECT review_id,
       order_id,
       TRY_CAST(review_score AS INTEGER)              AS review_score,
       TRY_CAST(review_creation_date AS TIMESTAMP)    AS review_creation_ts,
       TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_ts
FROM order_reviews
QUALIFY row_number() OVER (
    PARTITION BY order_id
    ORDER BY TRY_CAST(review_answer_timestamp AS TIMESTAMP) DESC NULLS LAST, review_id
) = 1
ORDER BY order_id;
