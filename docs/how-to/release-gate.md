# Release gate

> **Last verified:** 2026-09-02
>
> **Eviction:** This procedure leaves when the gate corpus, threshold, or CI
> integration changes.

How to invoke the bounded live semantic release gate and interpret its output.
The gate validates a release candidate's safety, honesty, and core-helpfulness checks.

## What the gate does

The release gate runs the **full combined calibration corpus** (v7 + v8, 66 cases)
against a live judge model and enforces the recall-first per-class thresholds defined
in [ADR-0052](../decisions/adr-0052-per-class-release-thresholds-real-sweep.md):

- **Corpus:** `evals/calibration_v7.yaml` (54 cases) + `evals/calibration_v8.yaml` (12 holdout cases).
- **Thresholds (per ADR-0052):**

  | Class | Threshold | Cases |
  |---|---:|---:|
  | `SAF` | 1.0 | 18 |
  | `HON` | 1.0 | 24 |
  | `HLP` | 0.5 | 24 |
  | overall | 0.5 | 66 |

The ten new v7 cases require a fresh maintainer-authorized sweep before current
precision, recall, or false-pass statistics can be published. The configured
thresholds remain in force until that sweep changes them.

- **Policy:** every class (SAF, HON, HLP) and the overall group must have recall
  = 1.00.  Any unavailable case (provider outage, judge crash) fails the gate
  closed — partial runs cannot certify the release.

## How to invoke it

### Locally

```bash
# The configured judge provider is Google (see config/settings.yaml).
export GOOGLE_API_KEY="..."

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

The gate is **manual-only** — it runs **exclusively** via GitHub Actions
`workflow_dispatch` with the *Enable the live semantic release gate* input checked.
It never fires on ordinary PRs, merges, or tag pushes.  Deterministic checks
(run fixtures, replay, grading) run on every change in the `checks` CI job.

1. Go to the Actions tab, select *CI*, click *Run workflow*, and check
   **Enable the live semantic release gate**.

The CI job (`release-gate` in `.github/workflows/ci.yml`) reads the judge key
from the `JUDGE_API_KEY` repository secret.  If the secret is absent the job
fails at the prerequisite-check step with an actionable error message.

## Interpreting output

The gate prints a summary like:

```
=== release-gate: 66 scored, 0 unavailable, threshold=per-class ===
  [PASS] class:SAF: n=18, threshold=1.0, recall=<recall>, precision=<precision>, false_passes=<count>
  [PASS] class:HON: n=24, threshold=1.0, recall=<recall>, precision=<precision>, false_passes=<count>
  [PASS] class:HLP: n=24, threshold=0.5, recall=<recall>, precision=<precision>, false_passes=<count>
  [PASS] overall: n=66, recall=<recall>, precision=<precision>, false_passes=<count>
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
- **Changing the threshold:** edit `RELEASE_THRESHOLDS_BY_CLASS` in
  `evals/calibration.py`.  A fresh maintainer-authorized sweep over the combined
  v7+v8 corpus is required before changing it (see [ADR-0052](../decisions/adr-0052-per-class-release-thresholds-real-sweep.md)).
- **Switching the judge provider:** update `config/settings.yaml` and the CI
  secret reference in `.github/workflows/ci.yml` accordingly.
