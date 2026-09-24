# InternHunterAgent MVP specification

> **Status:** Active MVP system of record for [issue #426](https://github.com/Park-Hip/InternHunterAgent/issues/426).
>
> **Scope:** This specification defines the first product workflow only.

## Outcome

InternHunterAgent's first release is an evidence-backed AI-agent-engineering portfolio slice for Vietnamese university students and early-career candidates seeking AI-related internships or jobs.
The user asks one supported question about technologies in a selected AI-job scope.
The system returns a bounded frequency analysis from a fixed, permitted, versioned corpus.
It does not claim to describe the current market, all Vietnamese jobs, future demand, or requirements outside that corpus.

The supported question is: **Which normalized technologies appear most frequently in the selected AI-job scope in corpus version `<version>`?**
For example: "Which technologies occur most often in entry-level AI Engineer postings in corpus v1?"
A selected scope uses only corpus-supplied filters.
If the question cannot be expressed with those filters, the system must say that it is unsupported rather than infer a scope.

## Corpus and truth boundary

The first release uses a fixed corpus with explicit permission for the project to retain and analyze it.
The corpus is versioned and immutable for a given answer.
No live collection, scraping, provider call, source selection, or refresh is part of this MVP.
A future corpus version is a separately prepared and identified input, not an implicit update to earlier answers.

Every corpus record used in a result needs a stable record identifier, retained source evidence, corpus version, and the fields used for scope filtering.
The corpus also contains a reviewed, fixed normalized-technology label set and supporting evidence.
A normalized label represents a technology named in retained evidence, not a semantic skill category, inferred capability, or model-created grouping.
The MVP does not automatically classify or broaden labels through embeddings, similarity search, or LLM judgment.

The system must exclude records that lack the requested scope evidence or a retained technology-evidence link needed for the answer.
It must state the exclusion or limitation when that affects the result.

## One-turn workflow

1. The user submits one technology-frequency question and supported scope filters.
2. The system validates the supported question shape and the available corpus version and filters.
3. A deterministic analysis selects the matching records, de-duplicates them by stable record identity, and counts the fixed normalized labels under a documented counting rule.
4. The system returns the ranked counts and percentages with evidence and limits.

The calculation is deterministic for the same version, filters, label set, and counting rule.
An answer must identify its version, scope, matching-record count, de-duplication rule, labels, calculation, and retained source evidence.
It must state relevant limitations, including the fixed-corpus boundary, incomplete evidence, unsupported filters, and that frequencies are observed labels rather than wider-market estimates.

The answer may use natural language to present deterministic results, but it must not add factual claims that are absent from the analysis or retained evidence.
When no matching evidence exists, it must report that outcome plainly and avoid a substitute recommendation.

## Definition of done

The MVP is complete when an early-career Vietnamese candidate can submit the supported question once and receive an answer whose scope, version, calculation, labels, record count, evidence, and limitations are inspectable.
A reviewer must be able to reproduce the ranking from the version, filters, counting rule, and evidence links.
The result must remain bounded when evidence is missing, a filter is unsupported, or no records match.

## Explicit non-goals

This release does not provide semantic skill grouping, general career advice, skill-gap analysis, role or level comparisons, trend analysis, learning roadmaps, résumé analysis, or multi-turn memory.
It does not decide the corpus source, collect data, call a live provider, or claim live or market-wide coverage.
It does not select an agent framework, prompt design, model provider, model routing or fallback, tracing service, memory design, retrieval technology, or single-agent versus multi-agent topology.
Those choices are deferred until this workflow has a concrete implementation and evaluation need.

## Relationship to discovery records

[mvp-discovery.md](mvp-discovery.md) records the rationale and evidence history for this narrower decision.
[decisions.md](decisions.md) records the active product decisions and deferred source-research history.
Neither document expands this specification's supported workflow or authorizes collection, architecture, API, schema, deployment, prompt, model, tracing, evaluation, or test-code changes.
