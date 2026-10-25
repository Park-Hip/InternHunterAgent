"""The query service generates one statement with an injected model.

No agent runtime, provider SDK, prompt registry, or tracing implementation takes
part: a stub model stands in for the client, which is what makes the query path
testable on its own. The import checks are the boundary the module promises.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from src.services.query.executor import execute_bounded_select
from src.services.query.generator import build_prompt, generate_sql
from src.services.query.row_bound import resolve_bounds
from src.services.query.sql_validator import validate_sql

ROOT = Path(__file__).resolve().parents[3]
QUERY_SERVICE_DIRECTORY = ROOT / "src" / "services" / "query"
QUERY_TOOL_PATH = ROOT / "src" / "agents" / "tools" / "query_clean_jobs.py"

SQL_RULES = "Write one SELECT over clean_jobs."
SCHEMA_CONTEXT = "clean_jobs has id, title, and location."
REQUEST = "internships in Hanoi"


class _StubModel:
    """One injected model client that records what it was asked."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


class SqlGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_the_prompt_joins_rules_schema_and_request_in_order(self) -> None:
        self.assertEqual(
            build_prompt(
                sql_generation=SQL_RULES,
                schema_context=SCHEMA_CONTEXT,
                request=REQUEST,
            ),
            f"{SQL_RULES}\n\n{SCHEMA_CONTEXT}\n\nQuestion: {REQUEST}",
        )

    async def test_the_stub_model_receives_the_assembled_prompt(self) -> None:
        model = _StubModel("SELECT id FROM clean_jobs ORDER BY id")

        sql = await generate_sql(
            request=REQUEST,
            sql_generation=SQL_RULES,
            schema_context=SCHEMA_CONTEXT,
            model=model,
        )

        self.assertEqual(
            model.prompts,
            [f"{SQL_RULES}\n\n{SCHEMA_CONTEXT}\n\nQuestion: {REQUEST}"],
        )
        self.assertEqual(sql, "SELECT id FROM clean_jobs ORDER BY id")

    async def test_the_reply_is_stripped_before_validation(self) -> None:
        model = _StubModel("\n  SELECT id FROM clean_jobs ORDER BY id\n")

        self.assertEqual(
            await generate_sql(
                request=REQUEST,
                sql_generation=SQL_RULES,
                schema_context=SCHEMA_CONTEXT,
                model=model,
            ),
            "SELECT id FROM clean_jobs ORDER BY id",
        )

    async def test_an_empty_reply_is_left_for_the_validator_to_refuse(self) -> None:
        model = _StubModel("   ")

        sql = await generate_sql(
            request=REQUEST,
            sql_generation=SQL_RULES,
            schema_context=SCHEMA_CONTEXT,
            model=model,
        )

        self.assertEqual(sql, "")
        self.assertFalse(validate_sql(sql).valid)


def _mock_session(mock_agent_session_factory: MagicMock) -> MagicMock:
    session = mock_agent_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


def _result(columns: list[str], rows: list[list[Any]]) -> MagicMock:
    result = MagicMock()
    result.keys.return_value = list(columns)
    result.all.return_value = list(rows)
    result.scalar.return_value = len(rows)
    result.scalar_one.return_value = len(rows)
    return result


class GeneratedQueryPathTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.services.query.executor.agent_session_factory")
    async def test_a_stub_model_generates_validates_bounds_and_executes(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        """The whole deterministic path runs on the service with no agent."""
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(["id", "title"], [[1, "Data Intern"]])
        model = _StubModel("SELECT id, title FROM clean_jobs ORDER BY id")

        sql = await generate_sql(
            request=REQUEST,
            sql_generation=SQL_RULES,
            schema_context=SCHEMA_CONTEXT,
            model=model,
        )
        validation = validate_sql(sql)
        self.assertTrue(validation.valid)

        bounds = resolve_bounds(validation.sql, 20)
        bounded = execute_bounded_select(bounds.base_sql, bounds.limit, bounds.offset)

        self.assertEqual(bounded.columns, ["id", "title"])
        self.assertEqual(bounded.rows, [[1, "Data Intern"]])
        self.assertEqual(bounded.total_rows, 1)
        self.assertEqual(
            str(session.execute.call_args_list[-1].args[0]),
            "SELECT id, title FROM clean_jobs ORDER BY id LIMIT 20",
        )


class ImportBoundaryTests(unittest.TestCase):
    def test_the_query_service_imports_nothing_from_the_agents_layer(self) -> None:
        offenders = [
            f"{path.name}: {module}"
            for path in sorted(QUERY_SERVICE_DIRECTORY.glob("*.py"))
            for module in _imported_modules(path)
            if module == "src.agents" or module.startswith("src.agents.")
        ]

        self.assertEqual(offenders, [])

    def test_the_query_service_imports_no_model_or_tracing_sdk(self) -> None:
        offenders = [
            f"{path.name}: {module}"
            for path in sorted(QUERY_SERVICE_DIRECTORY.glob("*.py"))
            for module in _imported_modules(path)
            if module.split(".", 1)[0] in {"langchain", "langchain_core", "langfuse"}
        ]

        self.assertEqual(offenders, [])

    def test_the_query_tool_imports_no_langfuse_module(self) -> None:
        offenders = [
            module
            for module in _imported_modules(QUERY_TOOL_PATH)
            if "langfuse" in module.lower()
        ]

        self.assertEqual(offenders, [])
