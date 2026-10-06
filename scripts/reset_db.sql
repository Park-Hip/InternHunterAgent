-- DESTRUCTIVE. Local development only. Drops all job data and Alembic history.
-- This script only drops objects; it contains no schema baseline DDL. The sole
-- canonical baseline is the Alembic revision chain. After running it, rebuild the
-- schema with `uv run alembic upgrade head` (or run scripts/reset_local_db.ps1).
-- Production and any deployed schema change goes through Alembic only.
-- This script must never be pointed at Neon or any deployed database.
-- Run with: Get-Content scripts/reset_db.sql | docker compose exec -T postgres psql -U internhunter -d internhunter

-- Legacy evidence tables (dropped by ADR-0058) are listed so a database at an
-- older revision is cleared too; IF EXISTS makes them no-ops otherwise.
DROP TABLE IF EXISTS field_provenance, normalization_results, duplicate_deliveries, raw_observations, raw_artifacts, collection_request_executions, collection_request_bodies, collection_runs, collection_plans, ingestion_runs, clean_jobs, raw_jobs, alembic_version CASCADE;
DROP FUNCTION IF EXISTS reject_ingestion_evidence_mutation() CASCADE;
