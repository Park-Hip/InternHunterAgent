# Milestone 6 SQL Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one safe production SQL tool over `clean_jobs` so the agent can answer real job-data questions while keeping the public API answer-only for fast MVP shipping.

**Architecture:** Keep the route thin, keep SQL safety deterministic, and keep the agent tool interface separate from SQL internals. The LangChain tool should be a thin adapter that calls a dedicated query service pipeline: schema context -> SQL generation -> SQL validation -> execution -> internal result shaping. Table-shaped data should remain internal for tracing and future UX expansion, not part of the public API yet.

**Tech Stack:** FastAPI, LangChain, Pydantic, SQLAlchemy/PostgreSQL, Langfuse, YAML-backed prompts, Python `unittest`

---

## Scope

This plan covers one narrow, shippable tool:

- one `query_clean_jobs` tool
- one allowed table: `clean_jobs`
- read-only SQL only
- answer-only public API
- internal structured result for debugging/tracing
- refusal path for unsafe or unsupported SQL

This plan does **not** include:

- short-term memory
- multiple tools
- persistent memory
- RAG
- agent router layer
- exposing raw SQL in the API response
- exposing table data in the public API response in this milestone

---

## File Structure

### Create

- `src/services/query/schema_context.py`
  Build the allowed schema description for `clean_jobs`
- `src/services/query/sql_validator.py`
  Validate generated SQL and reject unsafe statements
- `src/services/query/executor.py`
  Execute validated SQL against the database
- `src/services/query/table_formatter.py`
  Convert database rows into an internal table/debug structure for tracing and future UX
- `src/services/query/models.py`
  Pydantic models for internal query output and refusal output
- `src/agents/tools/query_clean_jobs.py`
  LangChain tool adapter that calls the query pipeline
- `tests/services/query/test_sql_validator.py`
  SQL validator tests
- `tests/services/query/test_table_formatter.py`
  Table formatting tests
- `tests/agents/tools/test_query_clean_jobs.py`
  Tool behavior tests with mocks

### Modify

- `config/prompts.yaml`
  Add prompt(s) for SQL generation and answer shaping
- `src/agents/runtime/factory.py`
  Register the new SQL tool with the agent
- `src/agents/runtime/prompts.py`
  Add prompt-loading helper(s) for the SQL tool prompt if needed
- `src/agents/service.py`
  Keep only the public answer/trace fields while preserving internal structured tool output
- `tests/api/test_query.py`
  Keep API tests focused on answer-only output

### Optional later

- `src/services/query/answer_builder.py`
  Only add this if answer shaping becomes complex. Do not add it now by default.

---

## Architectural Rules

- The agent decides whether to call the SQL tool, but the system prompt must strongly require SQL tool usage for job-data questions.
- The SQL tool must be thin. It should not own route logic, prompt loading for the whole app, or tracing.
- SQL validation must happen before execution, always.
- Table shaping should be deterministic and independent of the agent runtime.
- The route should never see raw SQL generation internals.

---

## Response Shape

Milestone 6 should keep the public API simple:

```json
{
  "answer": "Found 10 remote data analyst roles in New York.",
  "session_id": "abc123",
  "trace_id": "optional-trace-id",
  "trace_url": null
}
```

Internal tool output can still carry structured fields like:

- `rows`
- `columns`
- `row_count`
- validated SQL
- refusal reason

Do **not** expose raw SQL or table data in the public API response for this milestone.

---

## Task 1: Define Query Output Models

**Files:**
- Create: `src/services/query/models.py`
- Test: `tests/services/query/test_table_formatter.py`

- [ ] **Step 1: Define service-layer output models**

Create service-level models for:

- `TableArtifact`
  - `columns: list[str]`
  - `rows: list[list[str | int | float | None]]`
  - `row_count: int`
- `QueryRefusal`
  - `reason: str`
- `QueryToolResult`
  - `answer: str`
  - `table: TableArtifact | None`
  - `refusal: QueryRefusal | None`

Pseudocode:

```python
class TableArtifact(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int


class QueryRefusal(BaseModel):
    reason: str


class QueryToolResult(BaseModel):
    answer: str
    table: TableArtifact | None = None
    refusal: QueryRefusal | None = None
```

- [ ] **Step 2: Add one model-shape test**

Test that a `TableArtifact` with columns, rows, and row_count serializes correctly.

Pseudocode:

```python
def test_table_artifact_serializes():
    table = TableArtifact(
        columns=["title"],
        rows=[["Data Analyst"]],
        row_count=1,
    )
    assert table.row_count == 1
```

- [ ] **Step 3: Run the focused test**

Run:

```bash
uv run python -m unittest tests.services.query.test_table_formatter -v
```

Expected:
- test file imports
- model serialization test passes

- [ ] **Step 4: Commit**

```bash
git add src/services/query/models.py tests/services/query/test_table_formatter.py
git commit -m "feat: define internal query result models"
```

---

## Task 2: Build Deterministic Table Formatting

**Files:**
- Create: `src/services/query/table_formatter.py`
- Test: `tests/services/query/test_table_formatter.py`

- [ ] **Step 1: Write the failing formatter tests**

Cover:

- simple row formatting
- empty result formatting
- stable column order

Pseudocode:

```python
def test_format_rows_returns_columns_rows_and_count():
    rows = [
        {"title": "Data Analyst", "company": "A"},
        {"title": "ML Intern", "company": "B"},
    ]
    table = format_rows(rows)
    assert table.columns == ["title", "company"]
    assert table.row_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m unittest tests.services.query.test_table_formatter -v
```

Expected:
- FAIL because formatter does not exist yet

- [ ] **Step 3: Implement minimal formatter**

Formatter responsibilities:

- detect empty result sets
- preserve column order from first row
- convert row objects into list-of-lists form

Pseudocode:

```python
def format_rows(rows):
    if not rows:
        return TableArtifact(columns=[], rows=[], row_count=0)

    first = rows[0]
    columns = list(first.keys())
    formatted_rows = [[row.get(col) for col in columns] for row in rows]
    return TableArtifact(columns=columns, rows=formatted_rows, row_count=len(formatted_rows))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run python -m unittest tests.services.query.test_table_formatter -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/query/table_formatter.py tests/services/query/test_table_formatter.py
git commit -m "feat: add deterministic table formatter"
```

---

## Task 3: Define Schema Context for `clean_jobs`

**Files:**
- Create: `src/services/query/schema_context.py`
- Modify: `config/prompts.yaml`

- [ ] **Step 1: Create one explicit schema context function**

Keep it small and hardcoded for MVP.

Responsibilities:

- describe `clean_jobs`
- describe only the columns you want the model to use
- include read-only rules in the text if useful

Pseudocode:

```python
def build_clean_jobs_schema_context() -> str:
    return '''
    Table: clean_jobs
    Columns:
    - title
    - company
    - location
    - salary_min
    - salary_max
    - remote
    ...
    '''
```

- [ ] **Step 2: Add SQL-generation prompt text**

Update `config/prompts.yaml` with a focused prompt for SQL generation.

Prompt should say:

- use only `clean_jobs`
- output one read-only SQL statement
- no markdown fences
- no explanation
- prefer explicit filters and limits

Do not write a giant prompt. Keep it short.

- [ ] **Step 3: Smoke-check prompt loading**

Run:

```bash
uv run python -c "from src.core.config import settings; print(settings.prompts_yaml.keys())"
```

Expected:
- prompt config loads

- [ ] **Step 4: Commit**

```bash
git add src/services/query/schema_context.py config/prompts.yaml
git commit -m "feat: add clean_jobs schema context and sql prompt"
```

---

## Task 4: Implement SQL Validation

**Files:**
- Create: `src/services/query/sql_validator.py`
- Test: `tests/services/query/test_sql_validator.py`

- [ ] **Step 1: Write failing validator tests**

Cover:

- safe `SELECT` on `clean_jobs` is allowed
- `DELETE`, `UPDATE`, `INSERT`, `DROP` are rejected
- multi-statement SQL is rejected
- unknown table is rejected

Pseudocode:

```python
def test_validate_sql_allows_simple_select():
    result = validate_sql("SELECT title FROM clean_jobs LIMIT 10")
    assert result.valid is True


def test_validate_sql_rejects_delete():
    result = validate_sql("DELETE FROM clean_jobs")
    assert result.valid is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.services.query.test_sql_validator -v
```

Expected:
- FAIL because validator does not exist yet

- [ ] **Step 3: Implement minimal validator**

Validator responsibilities:

- trim SQL
- require it to begin with `SELECT`
- forbid semicolon-separated multiple statements
- forbid dangerous keywords
- require `clean_jobs` table usage only

Pseudocode:

```python
def validate_sql(sql: str) -> ValidationResult:
    normalized = sql.strip()
    if not normalized.upper().startswith("SELECT"):
        return invalid("Only SELECT statements are allowed")
    if ";" in normalized[:-1]:
        return invalid("Multiple statements are not allowed")
    if contains_forbidden_keyword(normalized):
        return invalid("Unsafe SQL detected")
    if "clean_jobs" not in normalized.lower():
        return invalid("Only clean_jobs is allowed")
    return valid(normalized)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run python -m unittest tests.services.query.test_sql_validator -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/query/sql_validator.py tests/services/query/test_sql_validator.py
git commit -m "feat: add read-only sql validator"
```

---

## Task 5: Add Execution Layer

**Files:**
- Create: `src/services/query/executor.py`
- Modify: `src/core/config.py` only if database env/config is missing

- [ ] **Step 1: Define one executor function**

Responsibilities:

- accept validated SQL only
- use your read-only DB session
- return rows in a formatter-friendly structure

Pseudocode:

```python
def execute_validated_sql(sql: str) -> list[dict]:
    with session_factory() as session:
        result = session.execute(text(sql))
        return [dict(row) for row in result.mappings().all()]
```

- [ ] **Step 2: Add one local smoke check strategy**

Do not add a full integration DB test first if the DB wiring is not stable yet.

Instead:
- smoke-check import path
- confirm session factory exists
- defer full DB integration test until the first manual end-to-end query

- [ ] **Step 3: Manual verification note**

Run later, once tool wiring is complete:

```bash
uv run python -c "from src.services.query.executor import execute_validated_sql; print(execute_validated_sql('SELECT * FROM clean_jobs LIMIT 1'))"
```

Expected:
- returns one row or an empty list without write behavior

- [ ] **Step 4: Commit**

```bash
git add src/services/query/executor.py src/core/config.py
git commit -m "feat: add validated sql execution layer"
```

---

## Task 6: Build the LangChain Tool Adapter

**Files:**
- Create: `src/agents/tools/query_clean_jobs.py`
- Test: `tests/agents/tools/test_query_clean_jobs.py`

- [ ] **Step 1: Write failing tool tests**

Cover:

- safe question returns `answer + table`
- unsafe generated SQL returns refusal
- tool calls validator before executor

Use mocks for:

- SQL generation
- validator
- executor

Pseudocode:

```python
async def test_tool_returns_answer_and_table_with_valid_sql():
    mock_generated_sql = "SELECT title FROM clean_jobs LIMIT 5"
    mock_validation = valid(...)
    mock_rows = [{"title": "Data Analyst"}]
    result = await query_clean_jobs("show jobs")
    assert result.table.row_count == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.agents.tools.test_query_clean_jobs -v
```

Expected:
- FAIL because tool does not exist yet

- [ ] **Step 3: Implement the thin tool adapter**

Responsibilities:

- build schema context
- generate SQL using the model or a dedicated helper
- validate SQL
- refuse if invalid
- execute if valid
- format rows into `TableArtifact`
- return `QueryToolResult`

Pseudocode:

```python
async def query_clean_jobs(question: str) -> QueryToolResult:
    schema_context = build_clean_jobs_schema_context()
    sql = await generate_sql(question=question, schema_context=schema_context)
    validation = validate_sql(sql)
    if not validation.valid:
        return QueryToolResult(answer="I can't safely answer that with SQL.", refusal=...)
    rows = execute_validated_sql(validation.sql)
    table = format_rows(rows)
    answer = build_answer_from_rows(question, table)
    return QueryToolResult(answer=answer, table=table)
```

Keep this tool thin. If a helper gets too large, split it later.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run python -m unittest tests.agents.tools.test_query_clean_jobs -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/tools/query_clean_jobs.py tests/agents/tools/test_query_clean_jobs.py
git commit -m "feat: add clean_jobs sql tool adapter"
```

---

## Task 7: Register the Tool in the Agent Runtime

**Files:**
- Modify: `src/agents/runtime/factory.py`
- Modify: `config/prompts.yaml`

- [ ] **Step 1: Add the tool to the runtime**

Register `query_clean_jobs` alongside `get_current_time`.

Pseudocode:

```python
tools = [
    get_current_time,
    query_clean_jobs,
]
```

- [ ] **Step 2: Strengthen the system prompt**

Update the agent prompt with one strong rule:

- if the user asks job-data questions, the agent must use `query_clean_jobs`

Do not write a vague hint. Make it explicit.

- [ ] **Step 3: Manual smoke check**

Run:

```bash
uv run python -c "from src.agents.runtime.factory import agent_factory; print(agent_factory())"
```

Expected:
- agent builds successfully with both tools

- [ ] **Step 4: Commit**

```bash
git add src/agents/runtime/factory.py config/prompts.yaml
git commit -m "feat: register clean_jobs tool in agent runtime"
```

---

## Task 8: Keep Public API Answer-Only While Preserving Internal Structured Output

**Files:**
- Modify: `src/agents/service.py`
- Modify: `tests/api/test_query.py`

- [ ] **Step 1: Keep service contract answer-focused**

Service should return:

- `answer`
- `trace_id`
- `trace_url`

Pseudocode:

```python
return {
    "answer": runtime_result["answer"],
    "trace_id": runtime_result["trace_id"],
    "trace_url": None,
}
```

- [ ] **Step 2: Update API test**

Keep the API test focused on answer-only output even if the internal tool result contains structured data.

Pseudocode:

```python
fake_response = {
    "answer": "...",
    "trace_id": None,
    "trace_url": None,
}
```

- [ ] **Step 3: Run API tests**

Run:

```bash
uv run python -m unittest tests.api.test_query -v
```

Expected:
- API tests pass

- [ ] **Step 4: Commit**

```bash
git add src/agents/service.py tests/api/test_query.py
git commit -m "feat: keep milestone 6 api answer-only"
```

---

## Task 9: End-to-End Manual Verification

**Files:**
- No new files required

- [ ] **Step 1: Start the API**

Run:

```bash
uv run uvicorn src.api.app:app --reload
```

Expected:
- app starts successfully

- [ ] **Step 2: Send one real job-data request**

Example request:

```json
{
  "query": "Show me 10 remote data analyst jobs"
}
```

Expected:
- `200` response
- natural-language answer
- SQL/tool activity visible in Langfuse

- [ ] **Step 3: Send one unsafe/out-of-scope request**

Example internal validator check:

- generated SQL with `DELETE`
- generated SQL against the wrong table

Expected:
- refusal path
- no execution

- [ ] **Step 4: Confirm Langfuse trace appears**

Expected:
- one trace visible in Langfuse UI
- tool activity visible in the trace

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: complete milestone 6 clean_jobs sql tool flow"
```

---

## Recommended Order

Build in this order:

1. models
2. table formatter
3. schema context + prompt
4. validator
5. executor
6. tool adapter
7. runtime registration
8. API response extension
9. manual end-to-end verification

This order isolates failure sources:

- if formatting fails, it is not a DB problem
- if validation fails, it is not an agent runtime problem
- if runtime registration fails, the tool logic can still be unit-tested independently

---

## Definition of Done

Milestone 6 is done when:

- the agent can answer one real `clean_jobs` question end-to-end
- unsafe SQL is refused before execution
- the public response returns a trustworthy natural-language answer
- structured rows/columns remain available internally for tracing and future UX
- the SQL tool is invoked for job-data questions
- at least one success-path and one failure/refusal-path test pass
- the SQL path is visible in Langfuse traces

---

## Notes for the Engineer

- Keep the SQL validator deterministic and boring. This is not the place for cleverness.
- Keep the tool adapter thin. If it starts growing, split helpers into `src/services/query/`.
- Do not add memory in this milestone.
- Do not add multiple SQL tools.
- Do not expose raw SQL in the public API.
- Do not expose table data in the public API in this milestone unless MVP priorities change.
