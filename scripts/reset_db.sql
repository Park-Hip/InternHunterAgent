-- DESTRUCTIVE. Local development only. DROPS ALL job data, then recreates the schema.
-- Production and any deployed schema change goes through Alembic (alembic upgrade head).
-- This script must never be pointed at Neon or any deployed database.
-- Run with: docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql

DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE;
\i scripts/init_db.sql
