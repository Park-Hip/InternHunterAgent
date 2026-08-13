# T0025.6 Holdout Report

> **Last verified:** 2026-08-13.

The six-scenario holdout covers two safety, two honesty, and two helpfulness scenarios.
The crafted evidence was authored from the frozen behavior specification and was not copied from
the 2026-07-14 recorded answers.

| Tier | Cases | Precision | Recall |
|---|---:|---:|---:|
| Structural | 6 | 1.00 | 1.00 |
| Textual | 5 | 1.00 | 1.00 |

Overall holdout accuracy is 1.00 across all six cases.
The judge tier remains an adapter for existing persisted harness scores and adds no new judge
metric or threshold.

The structural cross-currency case deliberately includes the canonical caveat and still names a
highest-paid job.
It fails at tier 1, proving that a recited phrase cannot override the binding structural rule.
