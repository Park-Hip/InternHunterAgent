"""Audit the serving SQL-generation prompt for column-contract drift.

Issue #604 found `prompts.sql_generation` contradicting itself: it ordered the
model to `SELECT id` first on every listing, then, further down the same prompt,
told it `id` was not a real column. Nothing rejected a listing generated from the
losing half of that contradiction, so the answer looked fine and the follow-up
detail request could not chain on an id the reader never saw.

This script is the check that would have caught it. It reads the prompt the
generator actually serves (`sql_generation` + `schema_context`, joined exactly
as `src.agents.tools.query_clean_jobs.generate_sql` joins them), takes the
declared allowlist from the prompt's own "Reference only real columns" line,
tokenises the body, and reports every `clean_jobs` column as declared or not and
used or not.

Scope is deliberate: `id` used to read as used-but-undeclared, which is the
contradiction. `source` read the same way only because three column descriptions
phrased provenance with the bare word "source", a hidden ingestion column, so it
is a real risk of the same kind. Tokenising English prose will match an ordinary
word occasionally; that only produces a false positive for a column the prompt
does not declare, which is the exact case under audit, so the gate stays honest.

Run:  uv run python scripts/audit_sql_prompt_columns.py

Exits non-zero when a column is used but undeclared, or when the declared list
names a column the agent may not see. No database, no network, no secrets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.ingestion.models import CleanJob  # noqa: E402

PROMPTS_PATH = ROOT / "config" / "prompts.yaml"
GENERATOR_SURFACES = ("sql_generation", "schema_context")
SURFACE_SEPARATOR = "\n\n"

# The one line in the prompt that declares which columns the model may reference.
DECLARED_PATTERN = re.compile(
    r"Reference only real columns:\s*(.+?)\.\s+Never invent a column", re.DOTALL
)
# Whole words only, so `source` never matches inside `source_url`.
WORD_PATTERN = re.compile(r"[a-z_][a-z0-9_]*")

# Ingestion bookkeeping and lifecycle columns. The agent must not name any of
# them: they are not in the prompt's column guide, and the schema guard that
# checks the physical table does not check a model's projection.
HIDDEN_COLUMNS = (
    "source",
    "external_id",
    "posted_date",
    "is_active",
    "first_seen_at",
    "last_seen_at",
)


def load_prompts() -> dict[str, str]:
    config = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))
    return config["prompts"]


def served_prompt_text(prompts: dict[str, str]) -> str:
    """Rebuild the exact message the SQL generator sends to the model."""

    return SURFACE_SEPARATOR.join(prompts[surface] for surface in GENERATOR_SURFACES)


def declared_columns(prompt: str) -> set[str]:
    match = DECLARED_PATTERN.search(prompt)
    if match is None:
        raise SystemExit(
            "sql_generation has no 'Reference only real columns: ...' line, so the "
            "audit cannot tell a declared column from an invented one"
        )
    return {column.strip() for column in match.group(1).split(",") if column.strip()}


def clean_jobs_columns() -> set[str]:
    return {column.name for column in CleanJob.__table__.columns}


def report(prompt: str) -> list[str]:
    declared = declared_columns(prompt)
    known = clean_jobs_columns()
    words = set(WORD_PATTERN.findall(prompt.lower()))

    # Only the columns the prompt fails to declare are worth a row: a column it
    # declares cannot be the contradiction. Hidden columns are always listed so
    # that a regression shows up as "used" rather than as a silent row.
    undeclared = sorted(known - declared)
    rows = undeclared + [column for column in HIDDEN_COLUMNS if column not in undeclared]

    print(f"{'COLUMN':<18}{'DECLARED':<12}{'USED':<8}")
    problems: list[str] = []
    for column in sorted(set(rows)):
        is_declared = column in declared
        is_used = column in words
        print(
            f"{column:<18}{'yes' if is_declared else 'no':<12}"
            f"{'yes' if is_used else 'no':<8}"
        )
        if is_used and not is_declared:
            problems.append(
                f"the prompt uses `{column}` but never declares it a real column"
            )
        if is_declared and column in HIDDEN_COLUMNS:
            problems.append(f"the prompt declares `{column}`, which is a hidden column")

    print(f"\ndeclared columns: {len(declared)} of {len(known)} clean_jobs columns")
    print(f"undeclared and unused: {sorted(set(undeclared) - words) or 'none'}")
    return problems


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python < 3.7 on Windows
        pass

    prompt = served_prompt_text(load_prompts())
    problems = report(prompt)

    if not problems:
        print("\nOK: every column the prompt names is a declared column.")
        return

    print("\nFAIL:")
    for problem in problems:
        print(f"  - {problem}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()