# MVP Technical Design (Execution Sandbox)

## 1. High-Level Architecture Map
The MVP follows a strict, unidirectional data flow.
- **API Entrypoint (`src/api/`):** FastAPI handles HTTP boundaries and Pydantic validation.
- **Application Tier (`src/services/`):** Orchestrates the request, initializes tracing IDs, and calls the agent.
- **Agent Runtime (`src/agents/runtime/`):** A single LangChain ReAct agent wrapper.
- **Isolated Adapters (`src/agents/tools/` & `src/core/`):** Tools and database connections are strictly isolated from the core request logic.

## 2. Component Isolation Laws
- **Rule 1:** `src/core` must remain entirely engine-agnostic.
- **Rule 2:** The API layer (`src/api/`) must NOT contain any LangChain prompts, LLM invocations, or SQL queries.
- **Rule 3:** SQL execution logic MUST live exclusively within isolated tools in `src/agents/tools/`.
- **Rule 4:** Langfuse tracing callbacks must be injected at the orchestration layer, not scattered across route definitions.

## 3. Database & Tool Interface Specifications
We are introducing the first real database tool (Milestone 6). It must adhere to these exact constraints:
- **Database Engine:** PostgreSQL.
- **Adapter Strategy:** SQLAlchemy. Adapters must be scoped and isolated; avoid polluting global state with unmanaged connection pools.
- **Target Schema:** The tool will query a table named `clean_jobs`.
  - Required Columns: `title` (String), `company` (String), `description` (Text), `tech_stack` (String/Array).
- **Tool Capabilities (Strictly Read-Only):**
  - The tool is explicitly restricted to `SELECT` operations only.
  - Do NOT grant the LLM raw SQL execution capabilities. Instead, wrap the SQLAlchemy queries in parameterized LangChain tools (e.g., exposing `tech_stack` or `title` as safe input arguments).
  - Implement basic error handling to catch and return database connection timeouts gracefully without crashing the FastAPI process.

## 4. Strict "Out of Scope" Boundaries
To maintain MVP stability, the following features are strictly FORBIDDEN during this implementation phase. Do not write code or setup infrastructure for:
- RAG (Retrieval-Augmented Generation) or Vector Databases.
- Multi-agent routing or complex autonomous loops.
- Long-term memory or database-backed conversation history (short-term thread memory only).
- Multi-tenant authentication or user management.
- Modifying data (INSERT, UPDATE, DELETE).
