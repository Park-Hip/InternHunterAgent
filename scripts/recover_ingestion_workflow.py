"""Unattended REST recovery for the `Nightly ingestion` workflow.

GitHub automatically disables a public repository's scheduled workflows after 60 days of
repository inactivity. This script is the idempotent, externally scheduled recovery job for
``.github/workflows/ingestion.yml`` (issue #325, approved plan ``.crew/325-approved-plan.md``).

Contract (maintainer-approved):

- Read the workflow state without mutation while it is ``active``.
- Only when the state is ``disabled_inactivity``: enable the workflow, then dispatch exactly one
  run, then record the outcome.
- Every API call or dispatch failure is made visible (logged to stderr and pinged to a failure
  healthcheck URL) and exits non-zero.
- Repeated invocations are idempotent: an active workflow triggers no write call; a recovered
  workflow is observed active on the next cycle and treated as a no-op.
- The recovery credential is repository-scoped ``Actions: write`` only. ``contents: write`` is
  forbidden by the checked-in credential contract and must be verified in GitHub during
  provisioning. No synthetic commits are written and the workflow is never dispatched while
  active.

The script never provisions an external account, credential, secret, or scheduler. It reads its
configuration from the environment and leaves the scheduler, credential, and alerting provisioning
to the maintainer runbook (``docs/how-to/operate.md`` and ``docs/how-to/cron-activation-runbook.md``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Protocol

import httpx

# The workflow file this job recovers. Hardcoded because the approved plan names exactly this
# workflow; widening the surface would violate the scope boundary.
WORKFLOW_FILE = "ingestion.yml"

# The dispatch target ref. ``main`` is the only branch GitHub fires ``schedule:`` from, so a
# recovery must re-arm against the same branch the schedule lives on.
DEFAULT_DISPATCH_REF = "main"

# The least-privileged credential contract. A repository-scoped GitHub App installation token (or
# fine-grained PAT) with exactly ``actions: write``. ``contents: write`` is forbidden: this job
# never writes repository contents, and the declared contract is unit-tested. GitHub's token
# permissions are verified by the maintainer during provisioning because bearer tokens cannot
# self-report their effective scope.
ALLOWED_PERMISSIONS: dict[str, str] = {"actions": "write"}
FORBIDDEN_PERMISSIONS: dict[str, str] = {"contents": "write"}

# Workflow states GitHub reports. Only ``disabled_inactivity`` is the recovery trigger; any other
# non-active state is surfaced as an alert rather than recovered from blindly.
RECOVERY_STATE = "disabled_inactivity"
ACTIVE_STATE = "active"


class RecoveryError(RuntimeError):
    """Raised when a recovery API call fails or the configuration is unsafe."""


@dataclass(frozen=True)
class RecoveryConfig:
    """Environment-derived configuration for one recovery invocation."""

    repository: str
    workflow_file: str
    dispatch_ref: str
    token: str
    requested_permissions: dict[str, str]
    healthcheck_url: str | None = None
    github_api_base: str = "https://api.github.com"
    request_timeout_seconds: float = 30.0


@dataclass
class RecoveryOutcome:
    """The observable result of one recovery invocation."""

    state: str
    enabled: bool = False
    dispatched: bool = False
    dispatch_run_id: int | None = None
    no_op: bool = False
    alerts: list[str] = field(default_factory=list)

    @property
    def recovered(self) -> bool:
        return self.enabled and self.dispatched


class ActionsClient(Protocol):
    """The GitHub Actions REST surface this job depends on."""

    def get_workflow_state(self) -> str: ...

    def enable_workflow(self) -> None: ...

    def dispatch_workflow(self, ref: str) -> int | None: ...


class HttpxActionsClient:
    """Concrete ``ActionsClient`` backed by the GitHub REST API over httpx."""

    def __init__(self, config: RecoveryConfig) -> None:
        self._config = config
        self._headers = {
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "internhunter-recovery/1.0",
        }

    @property
    def _workflow_url(self) -> str:
        return (
            f"{self._config.github_api_base}/repos/{self._config.repository}"
            f"/actions/workflows/{self._config.workflow_file}"
        )

    def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                url,
                headers=self._headers,
                timeout=self._config.request_timeout_seconds,
                **kwargs,
            )
        except httpx.HTTPError as error:
            raise RecoveryError(f"{method} {url}: transport error: {error}") from error
        if response.status_code >= 400:
            raise RecoveryError(
                f"{method} {url}: HTTP {response.status_code}: {response.text[:500]}"
            )
        return response

    def get_workflow_state(self) -> str:
        response = self._request("GET", self._workflow_url)
        try:
            payload = response.json()
        except ValueError as error:
            raise RecoveryError("GET workflow: response was not valid JSON") from error
        if not isinstance(payload, dict):
            raise RecoveryError(f"GET workflow: expected an object, got {type(payload).__name__}")
        state = payload.get("state")
        if not isinstance(state, str) or not state:
            raise RecoveryError(f"workflow response missing state: {payload!r}")
        return state

    def enable_workflow(self) -> None:
        # PUT is idempotent at the API level: GitHub returns 204 whether the workflow was
        # disabled or already enabled, so a retried recovery does not double-apply.
        self._request("PUT", f"{self._workflow_url}/enable")
        # 204 No Content on success.

    def dispatch_workflow(self, ref: str) -> int | None:
        # The dispatch endpoint returns 204 with no body; the run id is not returned here. We
        # return None to signal "dispatch accepted" without claiming a run id we cannot prove.
        self._request(
            "POST",
            f"{self._workflow_url}/dispatches",
            json={"ref": ref},
        )
        return None


def assert_credential_contract(requested_permissions: dict[str, str]) -> None:
    """Reject any credential contract that grants ``contents: write`` or lacks ``actions: write``.

    This is the load-bearing least-privilege declaration. It is a pure function on the checked-in
    contract so it can be tested without a real credential. The runtime script calls it before any
    network request; the maintainer separately verifies the real GitHub token's scope during
    provisioning because a bearer token cannot self-report its effective permissions.
    """
    for scope, level in requested_permissions.items():
        if (
            scope in FORBIDDEN_PERMISSIONS
            and level.lower() == FORBIDDEN_PERMISSIONS[scope]
        ):
            raise RecoveryError(
                f"credential contract forbids {scope}: {level} "
                "(recovery must never write repository contents)"
            )
    for scope, required_level in ALLOWED_PERMISSIONS.items():
        actual = requested_permissions.get(scope)
        if actual is None or actual.lower() != required_level.lower():
            raise RecoveryError(
                f"credential contract requires {scope}: {required_level}; "
                f"got {actual!r}"
            )


def _healthcheck_failure_url(healthcheck_url: str) -> str:
    """Return the healthchecks.io failure endpoint for a configured base ping URL."""
    return f"{healthcheck_url.rstrip('/')}/fail"


def _ping_healthcheck(config: RecoveryConfig, *, failed: bool) -> None:
    """Best-effort record a recovery result without masking its GitHub API outcome."""
    if not config.healthcheck_url:
        return
    url = (
        _healthcheck_failure_url(config.healthcheck_url)
        if failed
        else config.healthcheck_url
    )
    try:
        httpx.get(url, timeout=config.request_timeout_seconds)
    except httpx.HTTPError as error:
        print(
            f"[recovery] WARNING: healthcheck ping to {url} failed: {error}",
            file=sys.stderr,
        )


def alert_failure(config: RecoveryConfig, message: str) -> None:
    """Make a failed recovery visible and best-effort ping the healthcheck failure endpoint.

    A ping failure is logged as a warning and never masks the original recovery failure. The base
    healthcheck URL is optional; when it is absent, stderr and the host's non-zero-exit alert are
    still visible signals.
    """
    print(f"[recovery] ALERT: {message}", file=sys.stderr)
    _ping_healthcheck(config, failed=True)


def record_success(config: RecoveryConfig) -> None:
    """Best-effort record a successful/no-op tick so the healthcheck can detect missed ticks."""
    _ping_healthcheck(config, failed=False)


def run_recovery(config: RecoveryConfig, client: ActionsClient) -> RecoveryOutcome:
    """Run one idempotent recovery cycle against ``client``.

    - ``active`` -> no write calls, ``no_op=True``.
    - ``disabled_inactivity`` -> enable then dispatch exactly once.
    - any other state -> alert and raise (do not guess).
    """
    outcome = RecoveryOutcome(state="")
    try:
        state = client.get_workflow_state()
    except RecoveryError as error:
        outcome.alerts.append(str(error))
        alert_failure(config, str(error))
        raise
    outcome.state = state

    if state == ACTIVE_STATE:
        outcome.no_op = True
        return outcome

    if state != RECOVERY_STATE:
        message = f"workflow state {state!r} is not the recovery trigger; not mutating"
        outcome.alerts.append(message)
        alert_failure(config, message)
        raise RecoveryError(message)

    try:
        client.enable_workflow()
    except RecoveryError as error:
        outcome.alerts.append(str(error))
        alert_failure(config, str(error))
        raise
    outcome.enabled = True

    try:
        run_id = client.dispatch_workflow(config.dispatch_ref)
    except RecoveryError as error:
        outcome.alerts.append(str(error))
        alert_failure(config, str(error))
        raise
    outcome.dispatched = True
    outcome.dispatch_run_id = run_id
    return outcome


def _config_from_env(env: dict[str, str]) -> RecoveryConfig:
    repository = env.get("GITHUB_REPOSITORY", "").strip()
    token = env.get("RECOVERY_GITHUB_TOKEN", "").strip()
    dispatch_ref = env.get("RECOVERY_DISPATCH_REF", DEFAULT_DISPATCH_REF).strip()
    healthcheck_url = env.get("RECOVERY_HEALTHCHECK_URL", "").strip() or None
    api_base = env.get("GITHUB_API_BASE", "https://api.github.com").strip()
    try:
        timeout = float(env.get("RECOVERY_REQUEST_TIMEOUT_SECONDS", "30"))
    except ValueError as error:
        raise RecoveryError(
            "RECOVERY_REQUEST_TIMEOUT_SECONDS must be a number"
        ) from error
    if timeout <= 0:
        raise RecoveryError(
            "RECOVERY_REQUEST_TIMEOUT_SECONDS must be greater than zero"
        )

    if not repository:
        raise RecoveryError("GITHUB_REPOSITORY (owner/repo) is required")
    if not token:
        raise RecoveryError(
            "RECOVERY_GITHUB_TOKEN is required (repository-scoped Actions: write)"
        )
    if "/" not in repository:
        raise RecoveryError(f"GITHUB_REPOSITORY must be owner/repo, got {repository!r}")

    # The declared credential contract. It is asserted before any request and tests protect it;
    # the maintainer verifies the actual token scope in GitHub during provisioning. See the runbook.
    requested_permissions = dict(ALLOWED_PERMISSIONS)
    assert_credential_contract(requested_permissions)

    return RecoveryConfig(
        repository=repository,
        workflow_file=WORKFLOW_FILE,
        dispatch_ref=dispatch_ref,
        token=token,
        requested_permissions=requested_permissions,
        healthcheck_url=healthcheck_url,
        github_api_base=api_base,
        request_timeout_seconds=timeout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and the credential contract without contacting GitHub.",
    )
    args = parser.parse_args(argv)

    try:
        config = _config_from_env(dict(os.environ))
    except RecoveryError as error:
        print(f"[recovery] CONFIG ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "repository": config.repository,
                    "workflow_file": config.workflow_file,
                    "dispatch_ref": config.dispatch_ref,
                    "requested_permissions": config.requested_permissions,
                    "healthcheck_configured": config.healthcheck_url is not None,
                },
                sort_keys=True,
            )
        )
        return 0

    client = HttpxActionsClient(config)
    try:
        outcome = run_recovery(config, client)
    except RecoveryError:
        # The alert was already emitted inside ``run_recovery``.
        return 1

    if outcome.no_op:
        print(
            json.dumps(
                {
                    "state": outcome.state,
                    "no_op": True,
                    "enabled": False,
                    "dispatched": False,
                }
            )
        )
        record_success(config)
        return 0

    print(
        json.dumps(
            {
                "state": outcome.state,
                "enabled": outcome.enabled,
                "dispatched": outcome.dispatched,
                "dispatch_ref": config.dispatch_ref,
                "recovered": outcome.recovered,
            }
        )
    )
    record_success(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
