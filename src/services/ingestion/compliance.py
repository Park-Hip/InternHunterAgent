"""Fail-closed, source-local robots.txt compliance checks for ingestion."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.core.logger import logger
from src.services.ingestion.safety import IngestionSafetyError


class RobotsPolicyError(IngestionSafetyError):
    """Raised when the current robots policy cannot authorize ingestion."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Robots compliance gate blocked ingestion: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class _RobotsRule:
    path: str
    allowed: bool

    def matches(self, target_path: str) -> bool:
        """Apply RFC 9309's wildcard and terminal-anchor matching semantics."""
        anchored = self.path.endswith("$")
        pattern = self.path[:-1] if anchored else self.path
        expression = "^" + re.escape(pattern).replace(r"\*", ".*")
        if anchored:
            expression += "$"
        return re.match(expression, target_path) is not None

    @property
    def match_length(self) -> int:
        # ``*`` and the terminal ``$`` are control characters, not matched octets.
        return len(self.path.rstrip("$").replace("*", "").encode("utf-8"))


@dataclass(frozen=True)
class _RobotsGroup:
    user_agents: tuple[str, ...]
    rules: tuple[_RobotsRule, ...]


@dataclass(frozen=True)
class _RobotsPolicy:
    groups: tuple[_RobotsGroup, ...]

    def allows(self, user_agent: str, target_url: str) -> bool:
        product_token = user_agent.split("/", maxsplit=1)[0].split(maxsplit=1)[0].lower()
        candidates = [
            (len(agent), group)
            for group in self.groups
            for agent in group.user_agents
            if agent == "*" or agent in product_token
        ]
        if not candidates:
            return True

        longest_match = max(length for length, _ in candidates)
        rules = [
            rule
            for length, group in candidates
            if length == longest_match
            for rule in group.rules
        ]
        matches = [rule for rule in rules if rule.matches(urlsplit(target_url).path)]
        if not matches:
            return True

        longest_rule = max(rule.match_length for rule in matches)
        # RFC 9309 resolves equal-length rules in favor of Allow.
        return any(rule.allowed for rule in matches if rule.match_length == longest_rule)


@dataclass(frozen=True)
class _CachedRobotsPolicy:
    policy: _RobotsPolicy
    expires_at: float


class RobotsPolicyGate:
    """Fetch, validate, cache, and evaluate one source's robots policy.

    A successful parse is held only in this gate instance for ``cache_ttl_seconds``.
    Fetch and parse failures are never cached, so a later source run can retry the
    policy endpoint. Every failure is denied rather than treated as permission.
    """

    def __init__(
        self,
        *,
        source: str,
        robots_url: str,
        target_url: str,
        user_agent: str,
        timeout_seconds: float,
        cache_ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._robots_url = robots_url
        self._target_url = target_url
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._clock = clock
        self._cached_policy: _CachedRobotsPolicy | None = None

    def assert_allowed(self, client: httpx.Client) -> None:
        """Raise ``RobotsPolicyError`` unless the current policy permits the target."""
        policy = self._cached_or_fetch(client)
        if not policy.allows(self._user_agent, self._target_url):
            self._block("robots_disallowed")

    def _cached_or_fetch(self, client: httpx.Client) -> _RobotsPolicy:
        if self._cached_policy is not None and self._clock() < self._cached_policy.expires_at:
            return self._cached_policy.policy

        try:
            response = client.get(
                self._robots_url,
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            self._block("robots_unavailable")

        policy = self._parse(response.text)
        self._cached_policy = _CachedRobotsPolicy(
            policy=policy,
            expires_at=self._clock() + self._cache_ttl_seconds,
        )
        return policy

    def _parse(self, body: str) -> _RobotsPolicy:
        """Parse enough of RFC 9309 to safely decide this source's target path."""
        normalized = body.lstrip("\ufeff")
        groups: list[_RobotsGroup] = []
        user_agents: list[str] = []
        rules: list[_RobotsRule] = []
        has_rule = False

        def finish_group() -> None:
            if user_agents:
                groups.append(_RobotsGroup(tuple(user_agents), tuple(rules)))

        for raw_line in normalized.splitlines():
            line = raw_line.split("#", maxsplit=1)[0].strip()
            if not line:
                continue
            name, separator, value = line.partition(":")
            if not separator:
                self._block("robots_malformed")
            directive = name.strip().lower()
            value = value.strip()
            if directive == "user-agent":
                if not value:
                    self._block("robots_malformed")
                if rules:
                    finish_group()
                    user_agents = []
                    rules = []
                user_agents.append(value.lower())
            elif directive in {"allow", "disallow"}:
                if not user_agents:
                    self._block("robots_malformed")
                if value:
                    rules.append(_RobotsRule(path=value, allowed=directive == "allow"))
                    has_rule = True

        finish_group()
        if not groups or not has_rule:
            self._block("robots_malformed")
        return _RobotsPolicy(tuple(groups))

    def _block(self, reason: str) -> NoReturn:
        target_path = urlsplit(self._target_url).path
        logger.warning(
            "ingestion.compliance_gate_blocked",
            source=self._source,
            reason=reason,
            robots_url=self._robots_url,
            target_path=target_path,
        )
        raise RobotsPolicyError(reason)


def target_url_for_robots(robots_url: str, target_path: str) -> str:
    """Build the robots-policy target URL while retaining the policy origin."""
    parts = urlsplit(robots_url)
    return urlunsplit((parts.scheme, parts.netloc, target_path, "", ""))
