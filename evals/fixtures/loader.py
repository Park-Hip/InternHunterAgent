"""Build/reset the seeded evaluation fixture database (internhunter_eval).

Offline tooling for the eval harness — kept entirely separate from the live
ingestion path and the `internhunter` production database.
"""

import os
import socket
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
import yaml

from src.core.column_contract import HIDDEN_COLUMN_NAMES, VISIBLE_COLUMN_NAMES
from src.services.ingestion.models import ingestion_teardown_statements

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_SQL_PATH = Path(__file__).resolve().parent / "seed_eval_db.sql"
SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"

# Seconds to wait for the fixture database to accept a TCP connection before
# declaring it unavailable. This is a socket preflight only, never a SQL round
# trip: a full psycopg connect can spend the OS-level IPv6 and IPv4 timeouts
# before failing, which is what made a missing local Postgres cost minutes.
FIXTURE_REACHABILITY_TIMEOUT_SECONDS = 2.0


def _fixture_config() -> dict:
    settings_yaml = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))
    eval_cfg = (settings_yaml or {}).get("eval")
    if not isinstance(eval_cfg, dict):
        raise ValueError("Missing 'eval' section in config/settings.yaml")

    fixture_cfg = eval_cfg.get("fixture")
    if not isinstance(fixture_cfg, dict):
        raise ValueError("Missing 'eval.fixture' section in config/settings.yaml")
    return fixture_cfg


def _required_fixture_url(fixture_cfg: dict, key: str) -> str:
    value = fixture_cfg.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Missing or empty 'eval.fixture.{key}' in config/settings.yaml"
        )
    return value


def fixture_database_url() -> str:
    """Resolve the fixture owner DSN, used only to build and seed the fixture.

    Reads the YAML directly instead of going through ``src.core.config.settings``,
    and that is load-bearing rather than lazy. ``load_settings()`` constructs and
    *caches* ``Settings()``, which takes both database URLs from the environment
    and ``.env``. ``evals/driver.py`` calls this to discover the fixture DSN and
    only then writes it into both database URLs. Resolving through ``settings`` would
    freeze the cache against the serving database first, and every later write
    would be ignored - so a capture would silently run the agent against
    production data instead of the frozen fixture.
    """
    return _required_fixture_url(_fixture_config(), "database_url")


def fixture_reader_database_url() -> str:
    """Resolve the non-owner DSN the evaluation path reads the fixture through.

    The loader owns ``eval.fixture.database_url`` and must keep it for rebuilds.
    The tool, executor, and SQL scoring use this DSN instead, so the evaluation
    path exercises the same column-level boundary as production (#730). The URL
    is validated as the same database under a different login role here, before
    any connection is attempted.
    """
    fixture_cfg = _fixture_config()
    owner = make_url(_required_fixture_url(fixture_cfg, "database_url"))
    reader = make_url(_required_fixture_url(fixture_cfg, "reader_database_url"))

    def endpoint(url):
        return (url.host or "localhost", url.port or 5432, url.database)

    if endpoint(owner) != endpoint(reader):
        raise ValueError(
            "'eval.fixture.reader_database_url' must name the same database as "
            "'eval.fixture.database_url'"
        )
    if not reader.username:
        raise ValueError(
            "'eval.fixture.reader_database_url' must name a login role"
        )
    if reader.username == owner.username:
        raise ValueError(
            "'eval.fixture.reader_database_url' must name a non-owner role, not "
            f"the fixture owner {owner.username!r}"
        )
    if not reader.password:
        raise ValueError(
            "'eval.fixture.reader_database_url' must include the fixture reader "
            "password so the loader can provision the role"
        )
    return _required_fixture_url(fixture_cfg, "reader_database_url")


def fixture_database_endpoint() -> tuple[str, int]:
    """Return the (host, port) the fixture DSN targets.

    Defaults to PostgreSQL's own host and port when the DSN omits them, so the
    preflight stays correct across every dialect spelling this project uses.
    """
    url = make_url(fixture_database_url())
    return url.host or "localhost", url.port or 5432


def fixture_database_reachable() -> bool:
    """Return whether the fixture database accepts a short TCP connection.

    Bounded preflight for ``load_fixture()``. It never performs a database
    round trip, only a socket connect against the host/port in the fixture DSN,
    so a local Postgres instance that has not been started is detected in well
    under a second instead of the multi-minute psycopg timeout it would
    otherwise take before the fixture-backed test module can skip.
    """
    host, port = fixture_database_endpoint()
    try:
        with socket.create_connection(
            (host, port), timeout=FIXTURE_REACHABILITY_TIMEOUT_SECONDS
        ):
            return True
    except OSError:
        return False


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


@contextmanager
def _fixture_migration_url(dsn: str):
    """Temporarily direct Alembic at the offline fixture database."""
    previous_url = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = dsn
    try:
        yield
    finally:
        if previous_url is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous_url


def _upgrade_schema(dsn: str) -> None:
    """Apply the production migration chain to the fixture database."""
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    with _fixture_migration_url(dsn):
        command.upgrade(alembic_cfg, "head")


def _drop_fixture_schema(dsn: str) -> None:
    """Clear the dedicated fixture schema before recreating its pinned dataset.

    Two steps, and the second is the one that matters.

    The derived teardown drops every table the models declare, plus the
    append-only trigger function. That alone is enough to stop the schema being
    wedged by a trigger on a table nobody declares.

    It is not enough to make the fixture actually clean. The database outlives
    the branch that created it, so it can still carry a table from an abandoned
    experiment - and a stale table is worse than a stale row, because it can
    satisfy a query or fail a test for a reason that has nothing to do with the
    code under test. The fixture contract is "empty", so this reads what is
    actually there and drops it too, rather than trusting a list to have
    stayed complete.

    Reading the catalog is what makes this safe to rely on: it cannot drift. The
    named list is still done first, so a failure names the table that caused it
    instead of a bulk drop.
    """
    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            for statement in ingestion_teardown_statements(version_table="alembic_version"):
                conn.execute(text(statement))
            for leftover in _unlisted_tables(conn):
                conn.execute(text(f'DROP TABLE IF EXISTS "{leftover}" CASCADE'))
    finally:
        engine.dispose()


def _unlisted_tables(conn: Connection) -> list[str]:
    """Base tables in the target schema that the derived teardown did not name."""
    schema = conn.execute(text("SELECT current_schema()")).scalar_one()
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ),
        {"schema": schema},
    ).scalars()
    return list(rows)


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


def _quote_ident(value: str) -> str:
    """Quote one PostgreSQL identifier, including the role and database names."""
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    """Quote one PostgreSQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _provision_reader_role(dsn: str) -> None:
    """Create or refresh the fixture reader and re-apply its column grants.

    PostgreSQL grants belong to the table object, so every rebuild drops them.
    This runs after the migration chain and seed on every ``load_fixture()``,
    which is what makes "rebuild the fixture" sufficient: no separate grant step
    can be forgotten. The role is dedicated to the fixture, never the production
    ``internhunter_agent`` role, so resetting its password cannot touch a serving
    credential.

    The post-condition is checked in the database rather than assumed: the role
    must read the 16 contract columns, must have no table-level ``SELECT``, and
    must be refused every hidden column. If any of that is false the loader
    fails instead of leaving an evaluation path that measures the wrong boundary.
    """
    reader = make_url(fixture_reader_database_url())
    owner = make_url(dsn)
    role = reader.username
    password = reader.password
    # fixture_reader_database_url() has already validated both.
    assert role is not None and password is not None

    quoted_role = _quote_ident(role)
    quoted_database = _quote_ident(owner.database or "")
    visible = ", ".join(_quote_ident(column) for column in VISIBLE_COLUMN_NAMES)
    hidden = ", ".join(_quote_ident(column) for column in HIDDEN_COLUMN_NAMES)

    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
            ).scalar()
            if exists:
                conn.execute(
                    text(
                        f"ALTER ROLE {quoted_role} LOGIN PASSWORD "
                        f"{_quote_literal(password)}"
                    )
                )
            else:
                conn.execute(
                    text(
                        f"CREATE ROLE {quoted_role} LOGIN PASSWORD "
                        f"{_quote_literal(password)}"
                    )
                )

            conn.execute(
                text(f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}")
            )
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted_role}"))
            # Table-level SELECT implies every column, including the hidden five.
            # Revoking it first is what makes the column grants the boundary.
            conn.execute(
                text(
                    f"REVOKE ALL PRIVILEGES ON TABLE public.clean_jobs "
                    f"FROM {quoted_role}"
                )
            )
            # A table-level revoke does not clear column grants, so drop any
            # stale hidden-column grant explicitly before adding the visible set.
            conn.execute(
                text(
                    f"REVOKE SELECT ({hidden}) ON TABLE public.clean_jobs "
                    f"FROM {quoted_role}"
                )
            )
            conn.execute(
                text(
                    f"GRANT SELECT ({visible}) ON TABLE public.clean_jobs "
                    f"TO {quoted_role}"
                )
            )
            conn.execute(
                text(
                    f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE "
                    f"public.clean_jobs FROM {quoted_role}"
                )
            )

            owner_role = conn.execute(
                text(
                    "SELECT pg_get_userbyid(relowner) FROM pg_class "
                    "WHERE oid = 'public.clean_jobs'::regclass"
                )
            ).scalar_one()
            if owner_role == role:
                raise ValueError("the fixture reader role must not own clean_jobs")
            if conn.execute(
                text(
                    "SELECT has_table_privilege(:role, 'public.clean_jobs', "
                    "'SELECT')"
                ),
                {"role": role},
            ).scalar_one():
                raise ValueError(
                    "the fixture reader role still has table-level SELECT on "
                    "clean_jobs"
                )
            for column in HIDDEN_COLUMN_NAMES:
                if conn.execute(
                    text(
                        "SELECT has_column_privilege(:role, 'public.clean_jobs', "
                        ":column, 'SELECT')"
                    ),
                    {"role": role, "column": column},
                ).scalar_one():
                    raise ValueError(
                        "the fixture reader role can read hidden column "
                        f"{column!r}"
                    )
            if not conn.execute(
                text(
                    "SELECT has_column_privilege(:role, 'public.clean_jobs', "
                    "'id', 'SELECT')"
                ),
                {"role": role},
            ).scalar_one():
                raise ValueError(
                    "the fixture reader role cannot read the contract columns"
                )
    finally:
        engine.dispose()


def load_fixture() -> None:
    """Rebuild the dedicated fixture schema through Alembic and load seed data."""
    dsn = fixture_database_url()
    _ensure_database_exists(dsn)
    _drop_fixture_schema(dsn)
    _upgrade_schema(dsn)
    _run_sql_file(dsn, SEED_SQL_PATH)
    _provision_reader_role(dsn)


def reset_fixture() -> None:
    """Drop the fixture tables and rebuild them from scratch."""
    load_fixture()


if __name__ == "__main__":
    load_fixture()
    engine = create_engine(fixture_database_url())
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM clean_jobs")).scalar()
    finally:
        engine.dispose()
    print(f"COUNT(*) = {count}")
