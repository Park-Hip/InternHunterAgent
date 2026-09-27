# Manage Langfuse prompts

The serving agent resolves `resumi-system`, `resumi-schema-context`, and `resumi-sql-generation` through the explicit `agent.prompts.deployment_label` in `config/settings.yaml`.
The default label is `production`.
The service never requests `latest`.

Each released image retains the reviewed text in `config/prompts.yaml` as its release-pinned fallback.
On startup, the service prefetches every required prompt before it creates the runtime.
If Langfuse is unavailable or credentials are intentionally absent, the service serves that fallback instead of failing a healthy request.
Fallback generations are intentionally not linked as native Langfuse prompt versions.

A managed prompt is linked to its generations by propagating the resolved Langfuse
prompt client around the model call.
The Langfuse Python SDK therefore carries a serving requirement, not a preference:
`propagate_attributes(prompt=...)` exists from SDK 4.14.0, and `pyproject.toml` and
`uv.lock` pin the floor.
`tests/agents/test_langfuse_tracing.py` and `tests/api/test_native_prompt_chat.py`
assert the installed SDK against the real propagation function, so a lockfile that
cannot link prompts fails the suite instead of answering a live request with an
in-band `error` event.

## Create a candidate

Run `uv run python scripts/register_langfuse_prompts.py --label candidate` to seed only candidate versions from the checked-in fallback text.
The command cannot assign the `production` label.
Use `--dry-run` to validate the source without contacting Langfuse.

In an isolated evaluation environment, set `agent.prompts.deployment_label: candidate` before running the existing scenario suite.
Record the resulting capture manifest, dataset run, and scores as review evidence.
The manifest records the exact resolved versions and content hashes for the system, schema-context, and SQL-generation prompts.
The capture cannot resume if that prompt lineage changes, and scoring refuses a capture whose recorded schema prompt no longer resolves.
See [the evaluation pipeline](../../evals/pipeline.md) for the capture and scoring commands.
The retired semantic release gate is not a promotion control; follow its current status in [the release certification guide](release-gate.md).
After review, a Langfuse project administrator moves `production` to the evaluated immutable version in the Langfuse UI.
Do not create a new production version merely to promote a candidate.

## Roll back

Move `production` back to the previously approved immutable version in the Langfuse UI.
After the client cache TTL, new requests resolve the restored version without an application deployment.
If remote prompt resolution remains unavailable, the deployed release keeps serving its checked-in fallback.
