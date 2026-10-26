# Documentation

Each document has one owner and one intended reader.

| Doc | Owns | Reader |
|---|---|---|
| [Architecture](architecture.md) | Product scope, architecture, layer laws, serving design | Product and engineering |
| [Composition module guide](modules/composition.md) | How the web service boots: import versus lifespan, the boot guards, the shared MCP server, teardown, and what would now be decided differently | Maintainers |
| [Model config module guide](modules/model-config.md) | Which models serve, why two profiles, what the timeouts, retries, and turn deadline protect against, and what would now be decided differently | Maintainers |
| [Prompts module guide](modules/prompts.md) | What the models read, how a turn gets its prompt text, why git is the authority and Langfuse only a link, how lineage reaches the trace, and what would now be decided differently | Maintainers |
| [Runtime module guide](modules/runtime.md) | What happens in one turn, the stream machinery, conversation memory, failure paths, and what would now be decided differently | Maintainers |
| [Tools and query module guide](modules/tools-and-query.md) | How a question becomes validated SQL and a bounded read: the tool pair, the validator, limits, the 16-column contract, and the two boot guards | Maintainers |
| [Ingestion module guide](modules/ingestion.md) | How the nightly VietnamWorks ingestion works: stages, gates, field mapping, reading a run, safe changes | Maintainers |
| [Desktop UI foundation](ui/desktop-foundation.md) | Approved employer overview and Vietnamese demo design intent, with implementation gates | UI maintainers and implementers |
| [Operate how-to](how-to/operate.md) | Deploy topology, configuration, database procedures, ingestion pipeline and cron, incidents | Operators |
| [Latency observability how-to](how-to/latency-observability.md) | Stream latency metric definitions, dimensions, and percentile publication gate | Operators and engineering |
| [Langfuse prompt management how-to](how-to/manage-langfuse-prompts.md) | Release-pinned prompt text, native trace linkage, drift checks, and rollback | Operators and evaluation work |
| [Evaluate how-to](how-to/evaluate.md) | Running the SQL guard gate and the text-to-SQL baseline against the frozen fixture and snapshot | Evaluation work |
| [Release certification how-to](how-to/release-gate.md) | Why no live semantic model-quality certification is published, and what deterministic release evidence remains | Release maintainers |
| [Configuration reference](reference/configuration.md) | Stack, dependencies, tunables, hosted services, quotas | Engineering |
| [Schema reference](reference/schema.md) | Frozen agent-visible `clean_jobs` columns and evolution path | Engineering and evaluation |
| [Agent behavior baseline](reference/agent-behavior.md) | MVP user, needs, expected behaviors, and how they are measured | Agent and evaluation work |
| [Refactor charter](refactor/charter.md), [component index](refactor/component-index.md), [layer map](refactor/target-layer-dependency-map.md), [active backlog](refactor/active-backlog.md) | Active in-place module-layer refactor scope, current component status, target dependencies, next slices | Maintainers and implementers |
| [Decision records](decisions/README.md) | Durable decision rationale, one record per decision | Decision makers |
| [Conventions](Docs_Conventions.md) | Documentation rules and exemptions | Documentation authors |

Related documentation outside this folder: the root [`README`](../README.md) for the five-minute
quickstart, [`CONTRIBUTING`](../CONTRIBUTING.md) for the change workflow,
[`evals/README`](../evals/README.md) for the instrument layout, and
[`AGENTS.md`](../AGENTS.md) for agent policy.
Active work lives in GitHub Issues; historical records live on git tag docs-history-pre-redesign.
The preserved [`discovery/`](discovery/) collection is historical source evidence, not the active
module-layer refactor plan.
