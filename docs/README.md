# Documentation

Each document has one owner and one intended reader.

| Doc | Owns | Reader |
|---|---|---|
| [Architecture](architecture.md) | Product scope, architecture, layer laws, serving design | Product and engineering |
| [Operate how-to](how-to/operate.md) | Deploy topology, configuration, database procedures, ingestion pipeline and cron, incidents | Operators |
| [Latency observability how-to](how-to/latency-observability.md) | Stream latency metric definitions, dimensions, and percentile publication gate | Operators and engineering |
| [Evaluate how-to](how-to/evaluate.md) | Running, grading, freezing, and inspecting evaluations | Evaluation work |
| [Release-gate how-to](how-to/release-gate.md) | Invoking and interpreting the live semantic release gate | Release maintainers |
| [Configuration reference](reference/configuration.md) | Stack, dependencies, tunables, hosted services, quotas | Engineering |
| [Schema reference](reference/schema.md) | Frozen agent-visible `clean_jobs` columns and evolution path | Engineering and evaluation |
| [Agent behavior reference](reference/agent-behavior.md) | Frozen agent behavior requirements and probe protocol | Agent and evaluation work |
| [Decision records](decisions/README.md) | Durable decision rationale, one record per decision | Decision makers |
| [Conventions](Docs_Conventions.md) | Documentation rules and exemptions | Documentation authors |

Related documentation outside this folder: the root [`README`](../README.md) for the five-minute
quickstart, [`CONTRIBUTING`](../CONTRIBUTING.md) for the change workflow,
[`evals/README`](../evals/README.md) for the instrument layout, and
[`AGENTS.md`](../AGENTS.md) for agent policy.
Active work lives in GitHub Issues; historical records live on git tag docs-history-pre-redesign.
