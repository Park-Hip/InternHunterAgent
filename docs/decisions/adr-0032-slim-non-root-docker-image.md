# Production uses a slim, non-root Python Docker image

> **Status:** Active · **Decided:** 2026-07-16

## Decision

Production images build on `python:3.12-slim`, install with `uv sync --frozen --no-dev`, and run as
a non-root application user.

## Consequences

Smaller attack surface and image size; dependency installs are reproducible from the lockfile.
