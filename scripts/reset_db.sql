-- DESTRUCTIVE. Local development only. Drops all job data and Alembic history.
-- Production and any deployed schema change goes through Alembic (alembic upgrade head).
-- This script must never be pointed at Neon or any deployed database.
-- Run with: docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql

DROP TABLE IF EXISTS clean_jobs, raw_jobs, alembic_version CASCADE;
