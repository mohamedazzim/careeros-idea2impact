SELECT id, {{column_name}} AS job_id,
       {{timestamp_expr}} AS sort_value
FROM {{table_name}}
WHERE {{column_name}} = ANY(:job_ids)
