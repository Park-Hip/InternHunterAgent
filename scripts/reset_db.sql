-- DESTRUCTIVE. Local development only. Drops all job data and Alembic history.
-- This script only drops objects; it contains no schema baseline DDL. The sole
-- canonical baseline is the Alembic revision chain. After running it, rebuild the
-- schema with `uv run alembic upgrade head` (or run scripts/reset_local_db.ps1).
-- Production and any deployed schema change goes through Alembic only.
-- This script must never be pointed at Neon or any deployed database.
-- Run with: Get-Content scripts/reset_db.sql | docker compose exec -T postgres psql -U internhunter -d internhunter

DROP TABLE IF EXISTS ingestion_runs, clean_jobs, raw_jobs, alembic_version CASCADE;
