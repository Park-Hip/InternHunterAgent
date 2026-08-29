---
name: crew-pr-review
description: Publish a verifiable independent review for a crew ship pull request. Use after a crew PR has green checks when the mate asks to review a PR or a captain says review PR #<n>. Requires code-review-and-quality for the analysis and scripts/crew_pr_review.ps1 for GitHub publication.
---

# Crew PR review contract

This skill is the publication boundary for crew reviews. It does not replace the
`code-review-and-quality` skill: load and apply that skill first, then publish its
verdict through the adapter below.

1. Read the PR's issue/brief, current diff, checks, tests, and verification story.
   Review the current head; do not reuse a verdict after a new worker push.
2. Classify findings using the review skill's severity convention. Only required or
   Critical findings select `required-fixes`; Nit, Optional, and FYI findings do not.
3. Write any line-specific required findings to a temporary JSON file:

   ```json
   {
     "findings": [
       {
         "body": "Required: explain the failure and the remedy.",
         "path": "src/example.py",
         "line": 42,
         "side": "RIGHT"
       }
     ]
   }
   ```

   Put non-line-specific findings in the review summary. Omit `-FindingsPath` when
   there are no line-specific findings.
4. Publish exactly one review, never an approval:

   ```powershell
   # Passing internal verdict
   pwsh -File scripts/crew_pr_review.ps1 -Pr <n> -Verdict passing -Summary '<concise evidence-backed verdict>'

   # Required fixes
   pwsh -File scripts/crew_pr_review.ps1 -Pr <n> -Verdict required-fixes -Summary '<concise required-fixes summary>' -FindingsPath <path-to-findings.json>
   ```

5. Read the JSON receipt. It is the only completion evidence: report its review URL,
   review id, current head SHA, event, state, and inline-comment count to the mate.
   If the command fails or returns no valid receipt, report **blocked**; never say
   the review was posted.

The adapter uses `COMMENT` for a passing `/code-review` verdict and
`REQUEST_CHANGES` for required fixes. It never uses GitHub approval; that remains
reserved for the maintainer.
