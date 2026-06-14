#!/bin/bash
PGPASSWORD=narrative123 psql -U narrative -h localhost -d narrative <<'SQL'
SELECT
  COUNT(*)                             AS total_articles,
  COUNT(*) FILTER (WHERE is_embedded)  AS embedded,
  COUNT(*) FILTER (WHERE is_clustered) AS clustered,
  COUNT(*) FILTER (WHERE is_processed) AS consequence_mapped
FROM articles;

SELECT COUNT(*) AS narrative_events FROM narrative_events;

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
SQL
