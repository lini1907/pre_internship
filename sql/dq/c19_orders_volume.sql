-- C19 Order row count vs the reference load: n_failed = |rows - reference|,
-- n_total = reference, so fail_share is the relative deviation.
SELECT abs(count(*) - $ref_orders) AS n_failed,
       $ref_orders AS n_total
FROM {{orders}};
