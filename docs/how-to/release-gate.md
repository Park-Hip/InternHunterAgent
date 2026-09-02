# Release gate

> **Eviction:** This procedure leaves when the gate corpus, threshold, or CI
> integration changes.

How to invoke the bounded live semantic release gate and interpret its output.
The gate is the final quality barrier before a release candidate reaches production.

## What the gate does

The release gate runs a **narrow, release-critical subset** of the semantic
calibration corpus against a live judge model and enforces a recall-first
threshold:

- **Corpus:** `evals/calibration_release_gate.yaml` — six cases (one PASS + one
  FAIL per class: SAF, HON, HLP).  The full 44-case calibration in
  `evals/calibration_v7.yaml` remains available for diagnostic runs but is not
  part of the gate.
- **Threshold:** `RELEASE_THRESHOLD = 0.30` (see [ADR-0047](../decisions/adr-0047-release-threshold-is-recall-first-at-030.md)).
- **Policy:** every class (SAF, HON, HLP) and the overall group must have recall
  = 1.00.  Any unavailable case (provider outage, judge crash) fails the gate
  closed — partial runs cannot certify the release.

## How to invoke it

### Locally

```bash
# Set the judge provider key for your configured provider (see config/settings.yaml).
export GOOGLE_API_KEY="..."   # or GROQ_API_KEY / OPENROUTER_API_KEY

# Settings requires these URLs, but the gate scores recorded trajectories and
# never connects to either database.  Use non-production placeholder values.
export DATABASE_URL="postgresql+psycopg://ci:ci@localhost:5432/ci"
export AGENT_DATABASE_URL="postgresql+psycopg://ci_agent:ci@localhost:5432/ci"

# The gate runs against the narrowed corpus; no database service is needed.
uv run pytest -m eval -v
```

A missing credential fails early with a clear `RuntimeError` rather than an
opaque stack trace deep inside the judge client.

### In CI

The gate is **off by default**.  It runs only when explicitly enabled:

1. **Workflow dispatch:** go to the Actions tab, select *CI*, click *Run workflow*,
   and check *Enable the live semantic release gate*.
2. **Repository variable:** set `RELEASE_GATE_ENABLED=true` on the repository
   Settings → Variables page.

The CI job (`release-gate` in `.github/workflows/ci.yml`) reads the judge key
from the `JUDGE_API_KEY` repository secret.  If the secret is absent the job
fails at the prerequisite-check step with a actionable error message.

## Interpreting output

The gate prints a summary like:

```
=== release-gate: 6 scored, 0 unavailable, threshold=0.3 ===
  [PASS] assertion_type:semantic: n=6, recall=1.000, precision=1.000
  [PASS] class:HLP: n=2, recall=1.000, precision=1.000
  [PASS] class:HON: n=2, recall=1.000, precision=1.000
  [PASS] class:SAF: n=2, recall=1.000, precision=1.000
  [PASS] language:vi: n=6, recall=1.000, precision=1.000
  [PASS] overall: n=6, recall=1.000, precision=1.000
  [PASS] prompt_version:v6: n=6, recall=1.000, precision=1.000
```

- **PASS** means recall ≥ 1.0 for that group.
- **FAIL** means recall < 1.0 — the gate will abort with the breached groups
  listed.
- **unavailable** lists any case the judge could not score; the gate aborts
  rather than silently passing on a partial run.

## Operational constraints

| Constraint | How it is handled |
|---|---|
| **Provider cost** | The narrowed six-case corpus keeps judge spend minimal (~pennies). |
| **Flakiness** | Unavailable cases fail the gate closed; no partial pass is allowed. |
| **Secret availability** | A missing `JUDGE_API_KEY` secret produces a clear CI error before any model call. |
| **Database isolation** | The gate scores recorded trajectories; no database connection is required. |

## Changing the gate

- **Adding cases:** edit `evals/calibration_release_gate.yaml`.  Every case must
  reference a scenario in `evals/scenarios_v1.yaml` that has a semantic
  assertion.
- **Changing the threshold:** edit `RELEASE_THRESHOLD` in
  `evals/calibration.py`.  A fresh maintainer-authorized sweep is required
  before changing it (see ADR-0047).
- **Switching the judge provider:** update `config/settings.yaml` and the CI
  secret reference in `.github/workflows/ci.yml` accordingly.
