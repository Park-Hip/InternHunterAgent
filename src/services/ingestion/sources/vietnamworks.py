import hashlib
import json
import time
from collections.abc import Iterator

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.services.ingestion.models import RawPosting
from src.services.ingestion.sources.base import JobSource


class VietnamWorksSource(JobSource):
    """Fetches IT/AI-Data postings from the VietnamWorks public JSON search API.

    Keyword recall (8 AI/Data queries) + jobFunction precision filter (parentId
    matches parent_id and at least one child id is in child_ids). Deduped by
    jobId across all queries and pages. Emits verbatim RawPosting records;
    no transform or persistence.

    Pass an httpx.Client to the constructor to inject canned responses in tests
    and avoid live network calls.

    Pre-production: verify ms.vietnamworks.com/robots.txt allows the /job-search
    API path before scheduling production runs (T0009.8 checklist item).
    """

    source = "vietnamworks"

    def __init__(self, client: httpx.Client | None = None) -> None:
        cfg = settings.ingestion_yaml
        self._url: str = cfg["api"]["url"]
        self._hits_per_page: int = cfg["api"]["hits_per_page"]
        self._pages_per_query: int = cfg["api"]["pages_per_query"]
        self._timeout: int = cfg["api"]["timeout_seconds"]
        self._delay: float = cfg["api"]["delay_seconds"]
        self._user_agent: str = cfg["api"]["user_agent"]
        self._retry_attempts: int = cfg["api"]["retry_attempts"]
        self._retry_backoff: float = cfg["api"]["retry_backoff_seconds"]
        self._max_elapsed: float = cfg["api"]["max_elapsed_seconds"]
        self._queries: list[str] = cfg["queries"]
        self._parent_id: int = cfg["job_function"]["parent_id"]
        self._child_ids: set[int] = set(cfg["job_function"]["child_ids"])
        self._max_jobs: int = cfg["max_jobs"]
        self._client = client
        self._deadline: float | None = None
        self.budget_exhausted = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "User-Agent": self._user_agent,
            "Content-Type": "application/json",
            "Origin": "https://www.vietnamworks.com",
            "Referer": "https://www.vietnamworks.com/",
        }

    def _build_payload(self, query: str, page: int) -> dict:
        return {
            "userId": 0,
            "query": query,
            "filter": [],
            "ranges": [],
            "order": [],
            "hitsPerPage": self._hits_per_page,
            "page": page,
        }

    def _post(self, client: httpx.Client, query: str, page: int) -> list[dict]:
        resp = client.post(
            self._url,
            json=self._build_payload(query, page),
            headers=self._headers(),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or []

    def _post_with_retry(
        self, client: httpx.Client, query: str, page: int
    ) -> list[dict] | None:
        """Return the page's jobs, or None if the page was given up on.

        Retries transient failures (429, 5xx, timeouts, transport errors) with
        exponential backoff. Permanent failures (other 4xx) are not retried — a
        retry cannot fix them, and burning delays on a 403 would mask a block.
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._post(client, query, page)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                transient = status == 429 or status >= 500
                reason = f"http_{status}"
            except httpx.TimeoutException:
                transient = True
                reason = "timeout"
            except httpx.TransportError:
                transient = True
                reason = "transport_error"

            if transient and attempts <= self._retry_attempts:
                backoff = self._retry_backoff * (2 ** (attempts - 1))
                time.sleep(backoff)
                continue

            self.pages_failed += 1
            logger.warning(
                "ingestion.page_failed",
                source=self.source,
                query=query,
                page=page,
                attempts=attempts,
                reason=reason,
            )
            return None

    def _out_of_budget(self) -> bool:
        """True once the run has spent its whole wall-clock budget.

        Checked before each request rather than mid-page, so a page already in
        flight always finishes its retry ladder — tearing one down partway would
        buy at most ~96s and cost the clean per-page accounting that
        `pages_failed` depends on. The bound is therefore the budget plus one
        page's worst case, which is what config/ingestion.yaml sizes against the
        workflow's timeout-minutes.

        Logged once per fetch, not once per check, so a bounded run leaves
        exactly one line saying why it stopped early.
        """
        if self._deadline is None or time.monotonic() < self._deadline:
            return False
        if not self.budget_exhausted:
            self.budget_exhausted = True
            logger.warning(
                "ingestion.budget_exhausted",
                source=self.source,
                max_elapsed_seconds=self._max_elapsed,
                pages_failed=self.pages_failed,
            )
        return True

    def _is_ai_data(self, job: dict) -> bool:
        fn = job.get("jobFunction") or {}
        child_ids = {
            c.get("id") for c in (fn.get("children") or []) if c.get("id") is not None
        }
        return fn.get("parentId") == self._parent_id and bool(self._child_ids & child_ids)

    @staticmethod
    def _content_hash(job: dict) -> str:
        canonical = json.dumps(job, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _collect(self, client: httpx.Client) -> Iterator[RawPosting]:
        """Inner generator: iterate pages × queries round-robin, filter, dedup, cap.

        Page-major on purpose: page 0 of every query, then page 1 of every query.
        The cap is global, so a query-major order would spend the whole budget on
        the first queries in the config list and never reach the last ones —
        interleaving makes a truncated run truncate evenly across queries instead
        of starving whichever roles happen to be listed later.
        """
        seen_ids: set[int] = set()
        kept = 0
        for page in range(self._pages_per_query):
            if kept >= self._max_jobs or self._out_of_budget():
                break
            for query in self._queries:
                if kept >= self._max_jobs or self._out_of_budget():
                    break
                try:
                    jobs = self._post_with_retry(client, query, page)
                    if jobs is None:
                        continue  # skipped page; politeness delay below still applies
                    for job in jobs:
                        job_id = job.get("jobId")
                        if job_id is None or job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        if not self._is_ai_data(job):
                            continue
                        if kept >= self._max_jobs:
                            break
                        yield RawPosting(
                            source=self.source,
                            external_id=str(job_id),
                            source_url=job.get("jobUrl"),
                            raw_payload=job,
                            content_hash=self._content_hash(job),
                        )
                        kept += 1
                finally:
                    # Runs even on a skipped page — the politeness delay must not be
                    # bypassed exactly when the server is signalling distress.
                    time.sleep(self._delay)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(self) -> Iterator[RawPosting]:
        self.pages_failed = 0
        self.budget_exhausted = False
        self._deadline = time.monotonic() + self._max_elapsed
        if self._client is not None:
            yield from self._collect(self._client)
        else:
            with httpx.Client(follow_redirects=True) as client:
                yield from self._collect(client)
