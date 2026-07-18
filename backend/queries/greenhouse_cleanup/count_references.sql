SELECT {{column_name}} AS job_id, COUNT(*) AS ref_count
FROM {{table_name}}
WHERE {{column_name}} = ANY(:job_ids)
GROUP BY {{column_name}}
