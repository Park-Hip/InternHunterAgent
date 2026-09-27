# LiteLLM serves trusted configured deployments

> **Status:** Active · **Decided:** 2026-09-25

## Context

The serving runtime used dedicated LangChain constructors for each provider.
Adding a provider required changing runtime control flow even when profiles, timeouts, retries, and tracing semantics were already provider-neutral.
The system needs configuration-selected deployments without allowing API callers to select a model, endpoint, or credential.

## Decision

Serving uses the in-process `langchain-litellm` `ChatLiteLLM` integration.
`config/settings.yaml` contains the trusted named deployment allowlist, each provider-qualified LiteLLM model, and only the name of its credential environment variable.
The `react` and `sql_generation` profiles select a named deployment and retain independent portable generation settings.
Provider-specific settings live in a validated profile `provider_options` object.
The runtime rejects invalid options and a selected but unavailable credential before constructing a model.
Langfuse resolves provider and model attribution from the same deployment contract.

The project does not deploy LiteLLM Proxy, automatic fallback, semantic routing, or tenant billing.

## Consequences

Provider integrations no longer require provider-specific model-constructor branches in the agent runtime.
The existing `DEEPSEEK_API_KEY` and `GROQ_API_KEY` deployment variables remain valid.
A model migration requires adding or editing a reviewed allowlisted deployment and assigning the target profile to it.
A configuration change cannot expose credential values because configuration stores environment variable names only.

The direct integration avoids a new network hop and operational service, but it does not centrally enforce organization-wide gateway policy.
A future gateway proposal must justify its operational benefit and preserve this configuration boundary.

## Rollback

Revert the LiteLLM dependency, runtime resolver, configuration entries, and tracing lookup together.
Restore the prior native provider adapters and profile fields.
Keep existing provider environment variables provisioned until the rollback window closes.

## Evidence

[LangChain ChatLiteLLM integration](https://docs.langchain.com/oss/python/integrations/chat/litellm).
[DeepSeek thinking-mode API guidance](https://api-docs.deepseek.com/guides/thinking_mode/).
[Groq reasoning guidance](https://console.groq.com/docs/reasoning).