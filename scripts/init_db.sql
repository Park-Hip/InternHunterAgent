-- Idempotent schema initialisation for InternHunterAgent
-- Run with: docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql

CREATE TABLE IF NOT EXISTS raw_jobs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    source_url  TEXT,
    raw_payload JSONB NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS clean_jobs (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source                TEXT NOT NULL,
    external_id           TEXT NOT NULL,
    source_url            TEXT,
    title                 TEXT NOT NULL,
    company               TEXT NOT NULL,
    role                  TEXT NOT NULL,
    description           TEXT,
    tech_stack            TEXT,
    job_level             TEXT,
    location              TEXT,
    posted_date           DATE,
    is_internship         BOOLEAN NOT NULL DEFAULT false,
    salary_min            NUMERIC,
    salary_max            NUMERIC,
    salary_currency       TEXT,
    is_salary_negotiable  BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (source, external_id)
);
