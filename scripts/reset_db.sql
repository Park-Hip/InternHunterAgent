-- Destructive schema reset for InternHunterAgent — DROPS ALL job data, then recreates the schema.
-- Run ONLY when the schema shape changes (both tables are reproducible: clean_jobs is rebuilt
-- every ingestion run, raw_jobs is re-fetchable). Routine runs should use init_db.sql instead.
-- Run with: docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql

DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE;
\i scripts/init_db.sql
