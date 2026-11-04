-- C14 Customer and seller state is one of the 27 federative units.
WITH s AS (
    SELECT state FROM {{customers}}
    UNION ALL
    SELECT state FROM {{sellers}}
)
SELECT count(*) FILTER (WHERE state IS NULL OR NOT list_contains($valid_states, state)) AS n_failed,
       count(*) AS n_total
FROM s;
