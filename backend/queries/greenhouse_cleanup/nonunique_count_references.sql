SELECT COUNT(*) AS total_references
FROM {{table_name}}
WHERE {{column_name}} = ANY(:job_ids)
