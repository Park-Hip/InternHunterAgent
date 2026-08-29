# Destructive local-development reset: drop all job data and Alembic history,
# then rebuild the schema by applying the canonical Alembic revision chain to head.
#
# This script must never be pointed at Neon or any deployed database. Production
# schema changes go through Alembic only, as an explicit maintainer action.
#
# The schema baseline has no hand-maintained DDL: scripts/reset_db.sql only drops
# objects, and `uv run alembic upgrade head` is the single source of truth.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Dropping local job data and Alembic history..."
Get-Content "$PSScriptRoot/reset_db.sql" -Raw |
    docker compose exec -T postgres psql -U internhunter -d internhunter
if ($LASTEXITCODE -ne 0) { throw "reset_db.sql failed with exit code $LASTEXITCODE" }

Write-Host "Applying the canonical Alembic migration chain to head..."
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed with exit code $LASTEXITCODE" }

Write-Host "Reset complete. Local database is at Alembic head."