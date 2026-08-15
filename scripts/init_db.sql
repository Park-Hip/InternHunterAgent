-- Retired schema snapshot retained only for historical comparison.
-- Do not use this file to initialize an application or evaluation fixture database.
-- Apply the current schema with: uv run alembic upgrade head

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
    listing_expires_on    DATE,
    created_on            DATE,
    is_internship         BOOLEAN NOT NULL DEFAULT false,
    salary_min            NUMERIC,
    salary_max            NUMERIC,
    salary_currency       TEXT,
    is_salary_negotiable  BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (source, external_id)
);
