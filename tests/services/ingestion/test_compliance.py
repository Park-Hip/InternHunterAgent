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


def _robots_response(body: str, *, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.text = body
    return response


def _client(body: str) -> MagicMock:
    client = MagicMock()
    client.get.return_value = _robots_response(body)
    return client


def _gate(
    *,
    allow_404: bool = False,
    cache_ttl_seconds: float = 300,
    clock=lambda: 100.0,
) -> RobotsPolicyGate:
    return RobotsPolicyGate(
        source="vietnamworks",
        robots_url=ROBOTS_URL,
        target_url=TARGET_URL,
        user_agent=USER_AGENT,
        timeout_seconds=30,
        cache_ttl_seconds=cache_ttl_seconds,
        allow_404=allow_404,
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


def test_configured_404_permits_job_api_requests_without_caching_absence() -> None:
    client = _client("")
    robots_response = _robots_response("", status_code=404)
    client.get.return_value = robots_response
    api_response = MagicMock()
    api_response.raise_for_status.return_value = None
    api_response.json.return_value = {"data": []}
    client.post.return_value = api_response
    source = VietnamWorksSource(client=client)

    with patch("src.services.ingestion.compliance.logger") as mock_logger:
        with patch("src.services.ingestion.sources.vietnamworks.time.sleep"):
            list(source.fetch())

    client.post.assert_called()
    robots_response.raise_for_status.assert_not_called()
    mock_logger.info.assert_called_once_with(
        "ingestion.robots_policy_absent_permitted",
        source="vietnamworks",
        robots_url=ROBOTS_URL,
        target_path="/job-search/v1.0/search",
        status_code=404,
    )

    gate = _gate(allow_404=True)
    gate.assert_allowed(client)
    gate.assert_allowed(client)

    assert client.get.call_count == 3


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
def test_rfc9309_wildcard_and_anchor_disallow_rules_fail_closed(
    fixture_name: str,
) -> None:
    client = _client(_fixture(fixture_name))

    with pytest.raises(RobotsPolicyError, match="robots_disallowed"):
        _gate().assert_allowed(client)


@pytest.mark.parametrize("status_code", [400, 403, 429, 500])
def test_non_404_unsuccessful_policy_fails_closed(status_code: int) -> None:
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))
    request = httpx.Request("GET", ROBOTS_URL)
    response = httpx.Response(status_code, request=request)
    client.get.return_value.status_code = status_code
    client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"{status_code} error", request=request, response=response
    )

    with pytest.raises(RobotsPolicyError, match="robots_unavailable"):
        _gate(allow_404=True).assert_allowed(client)


def test_unconfigured_404_fails_closed() -> None:
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))
    request = httpx.Request("GET", ROBOTS_URL)
    response = httpx.Response(404, request=request)
    client.get.return_value.status_code = 404
    client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 error", request=request, response=response
    )

    with pytest.raises(RobotsPolicyError, match="robots_unavailable"):
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


def test_network_failure_fails_closed() -> None:
    client = _client(_fixture("vietnamworks_robots_allowed.txt"))
    client.get.side_effect = httpx.ConnectError("connection failed")

    with pytest.raises(RobotsPolicyError, match="robots_unavailable"):
        _gate(allow_404=True).assert_allowed(client)


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
