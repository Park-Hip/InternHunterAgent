"""Build/reset the seeded evaluation fixture database (internhunter_eval).

Offline tooling for the eval harness — kept entirely separate from the live
ingestion path and the `internhunter` production database.
"""

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.core.config import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL_PATH = REPO_ROOT / "scripts" / "init_db.sql"
SEED_SQL_PATH = Path(__file__).resolve().parent / "seed_eval_db.sql"


def _load_fixture_cfg() -> dict:
    eval_cfg = settings.config_yaml.get("eval")
    if not isinstance(eval_cfg, dict):
        raise ValueError("Missing 'eval' section in config/settings.yaml")

    fixture_cfg = eval_cfg.get("fixture")
    if not isinstance(fixture_cfg, dict):
        raise ValueError("Missing 'eval.fixture' section in config/settings.yaml")

    return fixture_cfg


def _fixture_database_url() -> str:
    fixture_cfg = _load_fixture_cfg()
    database_url = fixture_cfg.get("database_url")
    if not isinstance(database_url, str) or not database_url.strip():
        raise ValueError("Missing or empty 'eval.fixture.database_url' in config/settings.yaml")
    return database_url


def _split_sql_statements(sql: str) -> list[str]:
    """Split a .sql file into individual statements, respecting quoted strings.

    Needed because psycopg3's extended query protocol rejects a multi-statement
    execute() call, and `''`-escaped quotes inside our seeded text otherwise
    confuse a naive split on ';'.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if not in_string and ch == "-" and i + 1 < n and sql[i + 1] == "-":
            newline = sql.find("\n", i)
            if newline == -1:
                break
            i = newline + 1
            continue
        if ch == "'":
            in_string = not in_string
            current.append(ch)
            i += 1
            continue
        if ch == ";" and not in_string:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _run_sql_file(dsn: str, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql)
    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
    finally:
        engine.dispose()


def _ensure_database_exists(dsn: str) -> None:
    url = make_url(dsn)
    target_db = url.database
    maintenance_url = url.set(database="postgres")

    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    finally:
        engine.dispose()


def load_fixture() -> None:
    """Ensure internhunter_eval exists, then (re)apply schema + seed data."""
    dsn = _fixture_database_url()
    _ensure_database_exists(dsn)
    _run_sql_file(dsn, SCHEMA_SQL_PATH)
    _run_sql_file(dsn, SEED_SQL_PATH)


def reset_fixture() -> None:
    """Drop the fixture tables and rebuild them from scratch."""
    dsn = _fixture_database_url()
    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE"))
    finally:
        engine.dispose()
    load_fixture()


if __name__ == "__main__":
    load_fixture()
    engine = create_engine(_fixture_database_url())
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM clean_jobs")).scalar()
    finally:
        engine.dispose()
    print(f"COUNT(*) = {count}")
