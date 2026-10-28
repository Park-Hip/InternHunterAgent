## Summary

<!-- What changed and why. Link the issue this PR implements with "Closes #<issue number>". -->

Closes #

## Verification

<!-- Automated gates you ran and their results (tests, docs lint, build check). -->

-

## Milestone evaluation

<!-- Required when this change touches a prompt, the model, a tool, or the query path; otherwise write "Not applicable".
     Commit the run, then attach:
     uv run python -m evals --diff <last-run> <this-run> [--explained <ids>]
     A newly failing question blocks unless it is explained here. A question that loses its evidence also blocks.
     Falling below a floor always blocks:
     B2 held-out >= 85%, B3 100%, B4 100%, and every safety case passes.
     A Layer 1 run supports the diff but not the B3, B4, or safety floors. -->

- Run:
- Diff:
- Explained regressions:

## Manual check

<!-- End-user or maintainer steps used to verify the change. Include expected results. -->

- [ ]

## Risks

<!-- Behavior, compatibility, data, deployment, or operational risks. Also record out-of-scope follow-ups here instead of fixing them silently. -->

-

## Docs impact

<!-- Which documentation claims this change makes true or false. Write "None." if not applicable. -->

- None.

## Known issues

<!-- If there are no known issues, write "None." Otherwise give each issue an id using KI-YYYY-MM-DD-slug. -->

- None.
