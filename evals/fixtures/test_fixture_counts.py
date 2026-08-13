import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from evals.fixtures.loader import _fixture_database_url, load_fixture
from src.api.schema_guard import EXPECTED_COLUMNS


@pytest.fixture(scope="module")
def eval_engine():
    try:
        load_fixture()
    except OperationalError as exc:
        pytest.skip(f"eval Postgres not reachable: {exc}")

    engine = create_engine(_fixture_database_url())
    try:
        yield engine
    finally:
        engine.dispose()


def _scalar(engine, sql: str):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


def test_total_row_count(eval_engine) -> None:
    assert _scalar(eval_engine, "SELECT COUNT(*) FROM clean_jobs") == 22


def test_schema_matches_serving_contract(eval_engine) -> None:
    with eval_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'clean_jobs' AND table_schema = 'public'"
            )
        ).all()

    assert {row[0] for row in rows} == EXPECTED_COLUMNS


def test_role_distribution(eval_engine) -> None:
    with eval_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT role, COUNT(*) FROM clean_jobs GROUP BY role")
        ).all()
    counts = dict(rows)
    assert counts == {
        "AI Engineer": 5,
        "Data Scientist": 4,
        "Data Engineer": 4,
        "ML Engineer": 4,
        "Data Analyst": 4,
        "Other": 1,
    }


def test_python_count(eval_engine) -> None:
    assert _scalar(
        eval_engine, "SELECT COUNT(*) FROM clean_jobs WHERE tech_stack ILIKE '%Python%'"
    ) == 12


def test_python_and_hanoi_count(eval_engine) -> None:
    assert _scalar(
        eval_engine,
        "SELECT COUNT(*) FROM clean_jobs "
        "WHERE tech_stack ILIKE '%Python%' AND location ILIKE '%Hanoi%'",
    ) == 7


def test_cobol_count_is_zero(eval_engine) -> None:
    assert _scalar(
        eval_engine, "SELECT COUNT(*) FROM clean_jobs WHERE tech_stack ILIKE '%COBOL%'"
    ) == 0


def test_internship_count(eval_engine) -> None:
    assert _scalar(
        eval_engine, "SELECT COUNT(*) FROM clean_jobs WHERE is_internship"
    ) == 5


def test_max_salary_by_currency(eval_engine) -> None:
    with eval_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT salary_currency, MAX(salary_max) FROM clean_jobs "
                "WHERE salary_currency IS NOT NULL GROUP BY salary_currency"
            )
        ).all()
    max_by_currency = dict(rows)
    assert max_by_currency["VND"] == 40_000_000
    assert max_by_currency["USD"] == 5_000
