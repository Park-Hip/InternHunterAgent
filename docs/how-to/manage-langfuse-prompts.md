# Manage Langfuse prompts

> **Last verified:** 2026-10-19

> **Eviction:** This guide leaves when the serving text stops coming from `config/prompts.yaml`.

The text the model reads is always the release text in `config/prompts.yaml`.
Langfuse holds registered prompt versions that traces can link to; it never supplies the serving text.
For that link, the tracing layer reads the prompt names `resumi-system`, `resumi-schema-context`, and `resumi-sql-generation` at the explicit `agent.prompts.deployment_label` in `config/settings.yaml`, whose allowed values are `candidate` and `production`.
The service never requests `latest`.

## What serves

Every surface serves the checked-in YAML text (`prompts.system_prompt`, `prompts.schema_context`, `prompts.sql_generation`), and its version is the first 12 hex of the SHA-256 of that text, so an edit changes the version by itself; whatever Langfuse holds and whatever the label points to, that text and that version serve.
A refresh never changes the text and never fails a request: absent credentials, a failed fetch, an SDK fallback, a version that was never registered, or a version whose text differs all leave the surface unlinked on the release text.

The registry reads each labelled version once at boot and a background task refreshes it every `agent.prompts.refresh_interval_seconds`, so no turn ever calls Langfuse (#698).
Each lookup is bounded by `agent.prompts.fetch_timeout_seconds` and is never retried: boot waits at most one timeout for a surface, and the next refresh interval is the retry.
Both bounds are required, and a missing or malformed value refuses boot.
When the managed text equals the release text, the resolved prompt client is propagated around the model call, so the generation links to that immutable Langfuse version, while trace tags keep reading the served text's content hash (`prompt:system:<hash>`).
Traces older than the hash rollout carry hand-typed labels like `prompt:system:v1`; filter by date to keep them apart from hash tags.
When the two texts differ, the release text keeps serving and the registry logs `prompt.drift` once per transition with `surface`, `prompt_name`, `label`, `release_version`, `managed_version`, `release_hash`, and `managed_hash`.
A formed link logs `prompt.linked` once per transition with the same identifying fields minus the hashes.
A link means the registered version and the deployed YAML agree; drift means they moved apart, and the fix is the register step below, not an edit in the running service.

On startup the service resolves every surface before it creates the runtime, so a boot with credentials logs a link or drift line for every surface whose labelled version resolves, and `langfuse.prompts_prefetched` reports the content-hash versions that serve together with a `linked` flag per surface.
A lookup that raises is logged as `langfuse.prompt_resolution_failed`, the surface keeps serving the release text and its last confirmed link, and the next refresh is the retry; a failed refresh is logged and never ends the background loop.
`LANGFUSE_ENABLED=false` or absent keys only disable tracing and prompt linking; the release text still serves.

## Why the SDK version matters

A linked generation depends on `propagate_attributes(prompt=...)`, which exists from Langfuse SDK 4.14.0, so `pyproject.toml` and `uv.lock` pin the floor.
`tests/agents/test_langfuse_tracing.py` and `tests/api/test_native_prompt_chat.py` assert the installed SDK against the real propagation function, so a lockfile that cannot link prompts fails the suite instead of answering a live request with an in-band `error` event.

## Ship a prompt change

1. Edit the YAML text in `config/prompts.yaml`; the trace lineage is the text's content hash, so it changes with the text in the same commit by construction.
2. Review, merge to `main`, and let Render deploy the release.
   Until the register step below runs, the deployed release serves the new text unlinked and logs `prompt.drift`; that window is expected and does not affect answers.
3. Register the release with Langfuse: `uv run python scripts/register_langfuse_prompts.py --label production`.
   The command needs `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` in the environment.
   It creates an immutable version from the checked-in text when the `production` version differs and moves the label to it in the same call; when the texts already match it creates nothing.
4. Verify: `uv run python scripts/register_langfuse_prompts.py --check` compares every `production` version with the checked-in YAML and exits non-zero on drift, a missing version, or an unreadable lookup, so a deployment job can gate on it.

`--dry-run` validates and lists the checked-in prompts without contacting Langfuse.
The retired semantic release gate is not a promotion control; its current status is in [the release certification guide](release-gate.md).

## Roll back

Revert the prompt commit so the text, and with it the content hash, returns together; deploy the revert, then register the restored text with `--label production`.
Git keeps the reverted text as history, and Langfuse keeps every immutable version, so the trace link restores on the first refresh after the register run, within `agent.prompts.refresh_interval_seconds`.
Move labels only through the script: a hand-moved `production` label on text that differs from the deployed YAML only produces drift, and on text that matches it is exactly what the script produces.
If remote resolution is unavailable, the deployed release keeps serving its checked-in text unlinked, and no turn waits on the outage (#698).

## Evaluate a candidate

The evaluation harness resolves the prompt bundle once through the same registry, so a candidate run serves the branch's `config/prompts.yaml` text, exactly as serving would.
The one-shot driver has no background refresh, so it resolves its own links at startup.
Put the proposed text on a branch and run the scenario suite there; treat the report and its traces as review evidence.
In an isolated evaluation environment with its own Langfuse credentials, set `agent.prompts.deployment_label: candidate` and seed the branch's text with `uv run python scripts/register_langfuse_prompts.py --label candidate`.
The `candidate` label shapes only the trace link: the suite still serves the branch's checked-in text, and the label names the version its traces linked to.
The script refuses any label other than `candidate` or `production`, so a candidate run can never rewrite the `production` lineage or the serving text.
Promotion is the merge-and-deploy procedure above; nothing is promoted by moving labels in the Langfuse UI.
