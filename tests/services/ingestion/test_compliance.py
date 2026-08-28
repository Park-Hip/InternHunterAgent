from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.ingestion.compliance import RobotsPolicyError, RobotsPolicyGate
from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

FIXTURES = Path(__file__).parent / "fixtures"
ROBOTS_URL = "https://ms.vietnamworks.com/robots.txt"
TARGET_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"
USER_AGENT = "InternHunterAgent/1.0 (+https://github.com/Park-Hip/InternHunterAgent)"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _robots_response(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = body
    return response


def _client(body: str) -> MagicMock:
    client = MagicMock()
    client.get.return_value = _robots_response(body)
    return client


def _gate(*, cache_ttl_seconds: float = 300, clock=lambda: 100.0) -> RobotsPolicyGate:
    return RobotsPolicyGate(
        source="vietnamworks",
        robots_url=ROBOTS_URL,
        target_url=TARGET_URL,
        user_agent=USER_AGENT,
        timeout_seconds=30,
        cache_ttl_seconds=cache_ttl_seconds,
        clock=clock,
    )


def test_allowed_policy_permits_target_and_sends_honest_user_agent() -> None:
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))

    _gate().assert_allowed(client)

    client.get.assert_called_once_with(
        ROBOTS_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )


def test_disallowed_policy_blocks_before_any_job_api_request() -> None:
    client = _client(_fixture("vietnamworks_robots_disallowed.txt"))
    source = VietnamWorksSource(client=client)

    with pytest.raises(RobotsPolicyError, match="robots_disallowed"):
        list(source.fetch())

    client.post.assert_not_called()


@pytest.mark.parametrize(
    "fixture_name",
    [
        "vietnamworks_robots_wildcard_disallowed.txt",
        "vietnamworks_robots_anchor_disallowed.txt",
    ],
)
def test_rfc9309_wildcard_and_anchor_disallow_rules_fail_closed(fixture_name: str) -> None:
    client = _client(_fixture(fixture_name))

    with pytest.raises(RobotsPolicyError, match="robots_disallowed"):
        _gate().assert_allowed(client)


def test_unavailable_policy_fails_closed_and_records_safe_reason() -> None:
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))
    request = httpx.Request("GET", ROBOTS_URL)
    response = httpx.Response(503, request=request)
    client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 error", request=request, response=response
    )

    with patch("src.services.ingestion.compliance.logger") as mock_logger:
        with pytest.raises(RobotsPolicyError, match="robots_unavailable"):
            _gate().assert_allowed(client)

    mock_logger.warning.assert_called_once_with(
        "ingestion.compliance_gate_blocked",
        source="vietnamworks",
        reason="robots_unavailable",
        robots_url=ROBOTS_URL,
        target_path="/job-search/v1.0/search",
    )


def test_malformed_policy_fails_closed() -> None:
    client = _client(_fixture("vietnamworks_robots_malformed.txt"))

    with pytest.raises(RobotsPolicyError, match="robots_malformed"):
        _gate().assert_allowed(client)


def test_successful_policy_is_cached_until_its_ttl_expires() -> None:
    now = [100.0]
    gate = _gate(cache_ttl_seconds=10, clock=lambda: now[0])
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))

    gate.assert_allowed(client)
    now[0] = 109.0
    gate.assert_allowed(client)
    now[0] = 110.0
    gate.assert_allowed(client)

    assert client.get.call_count == 2
