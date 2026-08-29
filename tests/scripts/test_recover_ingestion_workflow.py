from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "recover_ingestion_workflow.py"
)
SPEC = importlib.util.spec_from_file_location("recover_ingestion_workflow", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
recovery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recovery
SPEC.loader.exec_module(recovery)


def _config(
    healthcheck_url: str | None = "https://hc.example/325",
) -> recovery.RecoveryConfig:
    return recovery.RecoveryConfig(
        repository="Park-Hip/InternHunterAgent",
        workflow_file="ingestion.yml",
        dispatch_ref="main",
        token="test-token-not-real",
        requested_permissions={"actions": "write"},
        healthcheck_url=healthcheck_url,
    )


class FakeClient:
    """In-memory ``ActionsClient`` recording every call for assertions."""

    def __init__(self, state: str = "active") -> None:
        self._state = state
        self.get_calls = 0
        self.enable_calls = 0
        self.dispatch_calls: list[str] = []
        self.get_state_error: recovery.RecoveryError | None = None
        self.enable_error: recovery.RecoveryError | None = None
        self.dispatch_error: recovery.RecoveryError | None = None

    def get_workflow_state(self) -> str:
        self.get_calls += 1
        if self.get_state_error is not None:
            raise self.get_state_error
        return self._state

    def enable_workflow(self) -> None:
        self.enable_calls += 1
        if self.enable_error is not None:
            raise self.enable_error
        self._state = "active"

    def dispatch_workflow(self, ref: str) -> int | None:
        self.dispatch_calls.append(ref)
        if self.dispatch_error is not None:
            raise self.dispatch_error
        return None


class FailingPing:
    """Captures ``alert_failure`` pings without touching the network."""

    def __init__(self) -> None:
        self.alerts: list[str] = []

    def __call__(self, config: recovery.RecoveryConfig, message: str) -> None:
        self.alerts.append(message)


def _patch_alert(monkeypatch) -> FailingPing:
    pinger = FailingPing()
    monkeypatch.setattr(recovery, "alert_failure", pinger)
    return pinger


def test_active_state_makes_no_write_calls(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="active")

    outcome = recovery.run_recovery(_config(), client)

    assert outcome.no_op is True
    assert outcome.enabled is False
    assert outcome.dispatched is False
    assert client.get_calls == 1
    assert client.enable_calls == 0
    assert client.dispatch_calls == []
    assert ping.alerts == []


def test_disabled_inactivity_enables_then_dispatches_exactly_once(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_inactivity")

    outcome = recovery.run_recovery(_config(), client)

    assert outcome.no_op is False
    assert outcome.enabled is True
    assert outcome.dispatched is True
    assert outcome.recovered is True
    assert client.get_calls == 1
    assert client.enable_calls == 1
    assert client.dispatch_calls == ["main"]
    assert ping.alerts == []


def test_enable_failure_alerts_and_exits_nonzero(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_inactivity")
    client.enable_error = recovery.RecoveryError("enable HTTP 403")

    with pytest.raises(recovery.RecoveryError, match="enable HTTP 403"):
        recovery.run_recovery(_config(), client)

    assert client.enable_calls == 1
    # The dispatch must never run when the enable step failed.
    assert client.dispatch_calls == []
    assert "enable HTTP 403" in ping.alerts[-1]


def test_dispatch_failure_alerts_and_exits_nonzero(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_inactivity")
    client.dispatch_error = recovery.RecoveryError("dispatch HTTP 422")

    with pytest.raises(recovery.RecoveryError, match="dispatch HTTP 422"):
        recovery.run_recovery(_config(), client)

    # Enable ran, dispatch was attempted once and failed.
    assert client.enable_calls == 1
    assert client.dispatch_calls == ["main"]
    assert "dispatch HTTP 422" in ping.alerts[-1]


def test_get_state_failure_alerts_and_exits_nonzero(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_inactivity")
    client.get_state_error = recovery.RecoveryError("GET transport error")

    with pytest.raises(recovery.RecoveryError, match="GET transport error"):
        recovery.run_recovery(_config(), client)

    assert client.get_calls == 1
    assert client.enable_calls == 0
    assert client.dispatch_calls == []
    assert "GET transport error" in ping.alerts[-1]


def test_non_recovery_state_is_alerted_not_mutated(monkeypatch) -> None:
    ping = _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_manually")

    with pytest.raises(recovery.RecoveryError, match="not the recovery trigger"):
        recovery.run_recovery(_config(), client)

    assert client.enable_calls == 0
    assert client.dispatch_calls == []
    assert ping.alerts  # made visible


def test_repeated_invocations_are_idempotent(monkeypatch) -> None:
    _patch_alert(monkeypatch)
    client = FakeClient(state="disabled_inactivity")

    first = recovery.run_recovery(_config(), client)
    second = recovery.run_recovery(_config(), client)

    # First cycle recovered: one enable, one dispatch.
    assert first.recovered is True
    assert client.enable_calls == 1
    assert client.dispatch_calls == ["main"]

    # Second cycle sees the now-active workflow and mutates nothing.
    assert second.no_op is True
    assert second.enabled is False
    assert second.dispatched is False
    assert client.enable_calls == 1
    assert client.dispatch_calls == ["main"]


def test_healthcheck_pings_are_best_effort_and_never_raise(monkeypatch, capsys) -> None:
    import httpx

    requested_urls: list[str] = []

    def boom(url: str, **_kwargs: object) -> None:
        requested_urls.append(url)
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", boom)
    config = _config(healthcheck_url="https://hc.example/325")

    # Neither success nor failure healthcheck failures may mask the primary outcome.
    recovery.alert_failure(config, "boom")
    recovery.record_success(config)

    err = capsys.readouterr().err
    assert "[recovery] ALERT: boom" in err
    assert "WARNING" in err
    assert requested_urls == ["https://hc.example/325/fail", "https://hc.example/325"]


def test_credential_contract_rejects_contents_write() -> None:
    with pytest.raises(recovery.RecoveryError, match="forbids contents"):
        recovery.assert_credential_contract({"actions": "write", "contents": "write"})


def test_credential_contract_requires_actions_write() -> None:
    with pytest.raises(recovery.RecoveryError, match="requires actions"):
        recovery.assert_credential_contract({"actions": "read"})


def test_credential_contract_accepts_minimal_actions_write() -> None:
    # The exact contract the runtime uses: actions: write only, no contents.
    recovery.assert_credential_contract({"actions": "write"})


def test_config_from_env_enforces_credential_contract_before_any_request() -> None:
    # The runtime only ever declares the minimal contract; assert it boots clean.
    env = {
        "GITHUB_REPOSITORY": "Park-Hip/InternHunterAgent",
        "RECOVERY_GITHUB_TOKEN": "token-not-real",
    }

    config = recovery._config_from_env(env)

    assert config.repository == "Park-Hip/InternHunterAgent"
    assert config.workflow_file == "ingestion.yml"
    assert config.dispatch_ref == "main"
    assert config.requested_permissions == {"actions": "write"}
    assert "contents" not in config.requested_permissions


def test_dry_run_validates_without_contacting_github(monkeypatch, capsys) -> None:
    # ``HttpxActionsClient`` must never be constructed during a dry run.
    constructed: list[object] = []
    monkeypatch.setattr(
        recovery,
        "HttpxActionsClient",
        lambda config: (
            constructed.append(config)
            or (_ for _ in ()).throw(AssertionError("dry run must not build a client"))
        ),
    )
    monkeypatch.setattr(
        recovery.os,
        "environ",
        {
            "GITHUB_REPOSITORY": "Park-Hip/InternHunterAgent",
            "RECOVERY_GITHUB_TOKEN": "token-not-real",
        },
    )

    assert recovery.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "ingestion.yml" in out
    assert "actions" in out
    assert "contents" not in out
    assert constructed == []


def test_main_records_a_successful_no_op_tick(monkeypatch) -> None:
    config = _config()
    recorded: list[recovery.RecoveryConfig] = []
    monkeypatch.setattr(recovery, "_config_from_env", lambda _env: config)
    monkeypatch.setattr(
        recovery, "HttpxActionsClient", lambda _config: FakeClient("active")
    )
    monkeypatch.setattr(recovery, "record_success", recorded.append)

    assert recovery.main([]) == 0
    assert recorded == [config]


def test_main_alerts_and_returns_nonzero_after_dispatch_failure(monkeypatch) -> None:
    config = _config()
    client = FakeClient("disabled_inactivity")
    client.dispatch_error = recovery.RecoveryError("dispatch HTTP 422")
    ping = FailingPing()
    monkeypatch.setattr(recovery, "_config_from_env", lambda _env: config)
    monkeypatch.setattr(recovery, "HttpxActionsClient", lambda _config: client)
    monkeypatch.setattr(recovery, "alert_failure", ping)

    assert recovery.main([]) == 1
    assert client.enable_calls == 1
    assert client.dispatch_calls == ["main"]
    assert ping.alerts == ["dispatch HTTP 422"]


def test_main_returns_nonzero_on_config_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(recovery.os, "environ", {})
    assert recovery.main([]) == 2
    assert "CONFIG ERROR" in capsys.readouterr().err
