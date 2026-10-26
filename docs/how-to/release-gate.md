# Release certification status

> **Retired:** 2026-09-18

The live semantic release-gate CI path is retired.
Release readiness for the portfolio release no longer requires a successful live semantic
judge run, and this release process publishes no current model-quality certification.

## What changed

The manual `workflow_dispatch` release-gate job was removed from `.github/workflows/ci.yml`.
There is no CI control to enable a live gate and no CI job that reads a judge-provider secret or
spends judge-provider credit.
The last maintainer-authorized live run failed closed, and maintainer direction was not to spend
provider credit on changing or rerunning the gate.

## What release readiness is now

Release readiness is the deterministic CI evidence plus local evaluation tooling:

- The `checks` job runs lint, type checks, the SQL prompt/column audit, and the full offline test
  suite on every pull request.
- The `sql-guard-gate` job loads the pinned fixture, runs the gate's own tests, and runs the
  reviewed SQL guard cases through the validator and the executor boundary.
- The `docs` and `migration-check` jobs run documentation hygiene and the migration chain.
- Local evaluation tooling under [`evals/`](../../evals/README.md) runs the same gate and the
  text-to-SQL baseline against the frozen snapshot.

A semantic judge score is not part of release certification. The judge was deleted with the legacy
harness ([ADR-0066](../decisions/adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)).

## What is not published

No current semantic model-quality certification is published from this release process.
The combined calibration corpus and the per-class bars were part of the deleted legacy harness;
their measurements remain in git history and in [ADR-0052](../decisions/adr-0052-per-class-release-thresholds-real-sweep.md),
but the release does not assert model quality from them.

## Why the gate was retired

The gate spent judge-provider credit on a certification that could not run reliably.
Its last authorized run collected unrelated serving-agent tests that lacked a required credential,
and the judge returned a provider error.
The retirement decision is issue
[#415](https://github.com/Park-Hip/InternHunterAgent/issues/415).
