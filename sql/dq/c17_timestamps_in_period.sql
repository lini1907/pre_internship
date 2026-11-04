-- C17 Every order timestamp present falls in [data_start, data_end); a missing
-- purchase_ts also fails.
SELECT count(*) FILTER (
           WHERE purchase_ts IS NULL
              OR purchase_ts NOT BETWEEN CAST($data_start AS TIMESTAMP)
                                     AND CAST($data_end AS TIMESTAMP) - INTERVAL 1 MICROSECOND
              OR approved_ts NOT BETWEEN CAST($data_start AS TIMESTAMP)
                                     AND CAST($data_end AS TIMESTAMP) - INTERVAL 1 MICROSECOND
              OR delivered_carrier_ts NOT BETWEEN CAST($data_start AS TIMESTAMP)
                                     AND CAST($data_end AS TIMESTAMP) - INTERVAL 1 MICROSECOND
              OR delivered_customer_ts NOT BETWEEN CAST($data_start AS TIMESTAMP)
                                     AND CAST($data_end AS TIMESTAMP) - INTERVAL 1 MICROSECOND
       ) AS n_failed,
       count(*) AS n_total
FROM {{orders}};
