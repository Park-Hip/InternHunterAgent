import hashlib
import json
import time
from collections.abc import Iterator

import httpx

from src.core.config import settings
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
        self._queries: list[str] = cfg["queries"]
        self._parent_id: int = cfg["job_function"]["parent_id"]
        self._child_ids: set[int] = set(cfg["job_function"]["child_ids"])
        self._max_jobs: int = cfg["max_jobs"]
        self._client = client

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
        """Inner generator: iterate queries × pages, filter, dedup, cap."""
        seen_ids: set[int] = set()
        kept = 0
        for query in self._queries:
            if kept >= self._max_jobs:
                break
            for page in range(self._pages_per_query):
                if kept >= self._max_jobs:
                    break
                jobs = self._post(client, query, page)
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
                time.sleep(self._delay)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(self) -> Iterator[RawPosting]:
        if self._client is not None:
            yield from self._collect(self._client)
        else:
            with httpx.Client(follow_redirects=True) as client:
                yield from self._collect(client)
