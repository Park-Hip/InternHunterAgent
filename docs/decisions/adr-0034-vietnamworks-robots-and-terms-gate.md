# VietnamWorks automation requires human review and current robots permission

> **Status:** Active · **Decided:** 2026-07-16, ratified 2026-08-13 · **Amended:** 2026-08-27 and 2026-09-27

## Context

Scheduled ingestion needs a recorded review of the source's terms and robots policy, but a dated
capture cannot prove that the policy still permits an unattended run.

## Decision

VietnamWorks automation needs both of these gates:

1. The maintainer's human terms/robots review remains recorded and ratified here.
2. Before every ingestion fetch, the VietnamWorks adapter retrieves the current robots policy for
   the API host, evaluates the configured honest `InternHunterAgent` user agent against
   `/job-search/v1.0/search`, and applies the reviewed exact-host HTTP 404 policy when the host publishes no policy.

The runtime policy is retrieved from `https://ms.vietnamworks.com/robots.txt`.
The reviewed VietnamWorks configuration permits only an exact HTTP 404 from that exact host because it means the host publishes no robots policy.
The adapter records `ingestion.robots_policy_absent_permitted` with the source, policy URL, target path, and status code before it makes the job API request.
The 404 result is never cached, so a later run observes a newly published policy.

A network failure, malformed policy, matching disallow rule, HTTP 403, HTTP 429, every 5xx response, and every other non-successful response block the run before any job API request.
The adapter records `ingestion.compliance_gate_blocked` with a safe reason (`robots_unavailable`, `robots_malformed`, or `robots_disallowed`) and raises the normal ingestion safety error.
Successful parsed policies are cached only in the source instance for the configured five-minute TTL.

This remains deliberately fail-closed except for the reviewed exact-host 404 case.
The archived 2026-07-16 evidence found that the API host returned 404, while `www.vietnamworks.com` had a permissive policy.
Those are different origins, so the archived `www` result cannot authorize current access to the API host.

## Scope

Automated *access* only.
This decision neither interprets the terms beyond the recorded human review nor bypasses explicit robots restrictions.
The separate ToS section 7 *republishing* restriction concerns what the public demo displays and remains tracked separately.

## Evidence

Non-repeatable 2026-07-16 captures remain in the evidence folder beside this record. The current
runtime check is the operational evidence for each attempted run; repeat the human review if source
behavior or terms change materially.
