import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.services.ingestion.models import RawPosting
from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vietnamworks_raw.json"
ROBOTS_ALLOWED = "User-agent: *\nAllow: /job-search/\n"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _allow_robots(client: MagicMock) -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = ROBOTS_ALLOWED
    client.get.return_value = response


def _mock_client(fixture: dict) -> MagicMock:
    """Return a mock httpx.Client whose .post() always returns the given fixture."""
    client = MagicMock()
    _allow_robots(client)
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = fixture
    client.post.return_value = resp
    return client


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    """Build a real httpx.HTTPStatusError with a working .response.status_code."""
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"{status_code} error", request=request, response=response)


def _ok_response(fixture: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = fixture
    return resp


def _mock_client_sequence(side_effects: list) -> MagicMock:
    """Return a mock httpx.Client whose .post() yields each side effect in order.

    Each item is either a MagicMock response (returned) or an exception
    instance (raised) — see unittest.mock's side_effect-list semantics.
    """
    client = MagicMock()
    _allow_robots(client)
    client.post.side_effect = side_effects
    return client


def _ai_job(job_id: int, query: str) -> dict:
    """A job that passes the jobFunction precision filter, tagged with its query."""
    return {
        "jobId": job_id,
        "jobTitle": f"{query} role {job_id}",
        "jobUrl": f"https://www.vietnamworks.com/job-{job_id}-jv",
        "jobFunction": {"parentId": 5, "children": [{"id": 27}]},
    }


def _per_query_client(
    jobs_by_query: dict[str, dict[int, list[dict]]],
    fail_pages: set[tuple[str, int]] | None = None,
) -> MagicMock:
    """Mock client whose response depends on the request payload's query and page.

    `_build_payload` puts them at json["query"] / json["page"], so dispatching on
    kwargs["json"] lets each query return distinct job IDs — the single-fixture
    client used elsewhere in this file cannot show per-query coverage at all.
    Any (query, page) in `fail_pages` raises a transient 500 on every attempt.
    """
    fail_pages = fail_pages or set()

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        query, page = payload["query"], payload["page"]
        if (query, page) in fail_pages:
            raise _http_error(500)
        return _ok_response({"data": jobs_by_query.get(query, {}).get(page, [])})

    client = MagicMock()
    _allow_robots(client)
    client.post.side_effect = side_effect
    return client


class VietnamWorksSourceTests(unittest.TestCase):
    """Tests for VietnamWorksSource — no live network calls.

    Fixture jobs:
      1001 — IT (parentId 5) + AI/Data child 27       → KEEP
      1002 — Non-IT (parentId 9)                       → FILTER OUT
      1003 — IT + child 27 + internship level          → KEEP (internships not filtered)
      1004 — IT (parentId 5) but no child 27           → FILTER OUT
    """

    def setUp(self) -> None:
        self.fixture = _load_fixture()
        self.client = _mock_client(self.fixture)
        # Suppress polite delay across all tests
        patcher = patch("time.sleep")
        self.mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def _source(self) -> VietnamWorksSource:
        return VietnamWorksSource(client=self.client)

    # ------------------------------------------------------------------
    # jobFunction precision filter
    # ------------------------------------------------------------------

    def test_ai_data_job_is_kept(self) -> None:
        results = list(self._source().fetch())
        self.assertIn("1001", {r.external_id for r in results})

    def test_non_it_job_is_filtered_out(self) -> None:
        # job 1002: parentId 9, not IT/Telecom
        results = list(self._source().fetch())
        self.assertNotIn("1002", {r.external_id for r in results})

    def test_it_job_without_ai_data_child_is_filtered_out(self) -> None:
        # job 1004: parentId 5 but children only [15] (Project Management), not 27
        results = list(self._source().fetch())
        self.assertNotIn("1004", {r.external_id for r in results})

    # ------------------------------------------------------------------
    # Internship retention
    # ------------------------------------------------------------------

    def test_internship_ai_data_job_is_retained(self) -> None:
        # job 1003: parentId 5 + child 27 + jobLevelVI "Thực tập" — must NOT be dropped
        results = list(self._source().fetch())
        self.assertIn("1003", {r.external_id for r in results})

    # ------------------------------------------------------------------
    # Dedup by jobId across queries and pages
    # ------------------------------------------------------------------

    def test_duplicate_job_ids_across_queries_appear_once(self) -> None:
        # The mock returns the same fixture for every query×page combination,
        # so jobId 1001 would be seen 16 times (8 queries × 2 pages).
        # Dedup must ensure it is emitted exactly once.
        results = list(self._source().fetch())
        external_ids = [r.external_id for r in results]
        self.assertEqual(len(external_ids), len(set(external_ids)))
        self.assertEqual(external_ids.count("1001"), 1)

    # ------------------------------------------------------------------
    # RawPosting field correctness
    # ------------------------------------------------------------------

    def test_source_is_vietnamworks(self) -> None:
        results = list(self._source().fetch())
        for r in results:
            self.assertEqual(r.source, "vietnamworks")

    def test_external_id_is_string(self) -> None:
        results = list(self._source().fetch())
        for r in results:
            self.assertIsInstance(r.external_id, str)

    def test_posting_fields_match_fixture(self) -> None:
        results = list(self._source().fetch())
        posting = next(r for r in results if r.external_id == "1001")
        self.assertIsInstance(posting, RawPosting)
        self.assertEqual(posting.source_url, "https://www.vietnamworks.com/data-scientist--i-1001-jv")
        self.assertIsInstance(posting.raw_payload, dict)
        self.assertEqual(posting.raw_payload["jobId"], 1001)
        self.assertEqual(posting.raw_payload["jobTitle"], "Data Scientist")

    def test_raw_payload_is_verbatim(self) -> None:
        # raw_payload must equal the original dict from the API response
        results = list(self._source().fetch())
        posting = next(r for r in results if r.external_id == "1001")
        expected = next(j for j in self.fixture["data"] if j["jobId"] == 1001)
        self.assertEqual(posting.raw_payload, expected)

    def test_content_hash_is_non_empty(self) -> None:
        results = list(self._source().fetch())
        for r in results:
            self.assertTrue(r.content_hash)

    # ------------------------------------------------------------------
    # content_hash stability
    # ------------------------------------------------------------------

    def test_content_hash_is_stable_across_identical_fetches(self) -> None:
        results1 = list(VietnamWorksSource(client=_mock_client(self.fixture)).fetch())
        results2 = list(VietnamWorksSource(client=_mock_client(self.fixture)).fetch())
        hash1 = next(r.content_hash for r in results1 if r.external_id == "1001")
        hash2 = next(r.content_hash for r in results2 if r.external_id == "1001")
        self.assertEqual(hash1, hash2)

    def test_content_hash_differs_for_changed_payload(self) -> None:
        modified = copy.deepcopy(self.fixture)
        for job in modified["data"]:
            if job["jobId"] == 1001:
                job["jobTitle"] = "Senior Data Scientist"

        results_orig = list(VietnamWorksSource(client=_mock_client(self.fixture)).fetch())
        results_mod = list(VietnamWorksSource(client=_mock_client(modified)).fetch())

        hash_orig = next(r.content_hash for r in results_orig if r.external_id == "1001")
        hash_mod = next(r.content_hash for r in results_mod if r.external_id == "1001")
        self.assertNotEqual(hash_orig, hash_mod)

    # ------------------------------------------------------------------
    # max_jobs cap
    # ------------------------------------------------------------------

    def test_max_jobs_cap_is_honoured(self) -> None:
        # Fixture yields 2 AI/Data jobs (1001 and 1003); cap to 1 → only 1 emitted.
        source = self._source()
        source._max_jobs = 1
        results = list(source.fetch())
        self.assertEqual(len(results), 1)

    # ------------------------------------------------------------------
    # No live network
    # ------------------------------------------------------------------

    def test_injected_client_is_used_not_real_httpx(self) -> None:
        source = self._source()
        list(source.fetch())
        self.client.post.assert_called()


class VietnamWorksResilienceTests(unittest.TestCase):
    """Per-page retry/backoff/skip behaviour — no live network calls."""

    def setUp(self) -> None:
        self.fixture = _load_fixture()
        patcher = patch("time.sleep")
        self.mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def _source(self, client: MagicMock, queries: list[str], pages_per_query: int) -> VietnamWorksSource:
        source = VietnamWorksSource(client=client)
        source._queries = queries
        source._pages_per_query = pages_per_query
        return source

    def test_mid_run_failure_skips_page_but_later_pages_still_yield(self) -> None:
        # page 0: exhausts all 3 attempts with 500s; page 1: succeeds.
        client = _mock_client_sequence(
            [_http_error(500), _http_error(500), _http_error(500), _ok_response(self.fixture)]
        )
        source = self._source(client, queries=["q"], pages_per_query=2)

        results = list(source.fetch())

        external_ids = {r.external_id for r in results}
        self.assertIn("1001", external_ids)
        self.assertIn("1003", external_ids)
        self.assertEqual(source.pages_failed, 1)

    def test_all_pages_failing_does_not_raise(self) -> None:
        client = _mock_client_sequence([_http_error(500)] * 3 + [_http_error(500)] * 3)
        source = self._source(client, queries=["q"], pages_per_query=2)

        results = list(source.fetch())

        self.assertEqual(results, [])
        self.assertEqual(source.pages_failed, 2)

    def test_transient_failure_is_retried_and_can_succeed(self) -> None:
        client = _mock_client_sequence([_http_error(500), _ok_response(self.fixture)])
        source = self._source(client, queries=["q"], pages_per_query=1)

        results = list(source.fetch())

        external_ids = {r.external_id for r in results}
        self.assertIn("1001", external_ids)
        self.assertIn("1003", external_ids)
        self.assertEqual(source.pages_failed, 0)

    def test_permanent_failure_is_not_retried(self) -> None:
        client = _mock_client_sequence([_http_error(403)])
        source = self._source(client, queries=["q"], pages_per_query=1)

        results = list(source.fetch())

        self.assertEqual(results, [])
        self.assertEqual(client.post.call_count, 1)
        self.assertEqual(source.pages_failed, 1)

    def test_backoff_doubles_between_retry_attempts(self) -> None:
        client = _mock_client_sequence([_http_error(500), _http_error(500), _http_error(500)])
        source = self._source(client, queries=["q"], pages_per_query=1)

        list(source.fetch())

        self.mock_sleep.assert_any_call(2.0)
        self.mock_sleep.assert_any_call(4.0)
        # Backoff sleeps must occur in order before the trailing politeness delay.
        backoff_calls = [c.args[0] for c in self.mock_sleep.call_args_list if c.args[0] in (2.0, 4.0)]
        self.assertEqual(backoff_calls, [2.0, 4.0])

    def test_politeness_delay_still_applies_to_skipped_page(self) -> None:
        client = _mock_client_sequence([_http_error(403)])
        source = self._source(client, queries=["q"], pages_per_query=1)

        list(source.fetch())

        self.mock_sleep.assert_any_call(source._delay)

    def test_pages_failed_resets_across_successive_fetch_calls(self) -> None:
        client = _mock_client_sequence([_http_error(500)] * 3)
        source = self._source(client, queries=["q"], pages_per_query=1)

        list(source.fetch())
        self.assertEqual(source.pages_failed, 1)

        source._client = _mock_client_sequence([_ok_response(self.fixture)])
        list(source.fetch())
        self.assertEqual(source.pages_failed, 0)


class VietnamWorksCoverageTests(unittest.TestCase):
    """Round-robin interleave: a cap must truncate evenly across queries (T0019.9).

    Shape used throughout: 8 queries x 2 pages x 2 AI/Data jobs per page = 32
    jobs available, `max_jobs = 20`. The 2-per-page figure is load-bearing — the
    interleave's granularity is a *page*, not a job, since `_collect` drains a
    whole page before moving to the next query. Jobs-per-query-per-page must
    therefore be <= max_jobs / len(queries) for a cap to reach every query at
    all; with 10 jobs per page the budget is spent on two queries regardless of
    loop order, and the anti-skew assertion below could not discriminate.
    """

    QUERIES = [f"q{i}" for i in range(1, 9)]
    PAGES = 2
    PER_PAGE = 2
    MAX_JOBS = 20

    def setUp(self) -> None:
        patcher = patch("time.sleep")
        self.mock_sleep = patcher.start()
        self.addCleanup(patcher.stop)
        # query -> page -> jobs. IDs encode the query index: qN owns N00..N99.
        self.jobs_by_query = {
            query: {
                page: [
                    _ai_job((qi + 1) * 100 + page * self.PER_PAGE + n, query)
                    for n in range(self.PER_PAGE)
                ]
                for page in range(self.PAGES)
            }
            for qi, query in enumerate(self.QUERIES)
        }

    def _source(self, client: MagicMock, max_jobs: int | None = None) -> VietnamWorksSource:
        source = VietnamWorksSource(client=client)
        source._queries = list(self.QUERIES)
        source._pages_per_query = self.PAGES
        source._max_jobs = self.MAX_JOBS if max_jobs is None else max_jobs
        return source

    @staticmethod
    def _query_of(external_id: str) -> str:
        return f"q{int(external_id) // 100}"

    # ------------------------------------------------------------------
    # The anti-skew assertion — this ticket's core test
    # ------------------------------------------------------------------

    def test_cap_truncates_evenly_across_queries_not_alphabetically(self) -> None:
        # Against the old query-outer loop the budget of 20 is consumed by the
        # first 5 queries (4 jobs each) and q6..q8 are never requested at all.
        source = self._source(_per_query_client(self.jobs_by_query))

        results = list(source.fetch())

        covered = {self._query_of(r.external_id) for r in results}
        self.assertEqual(covered, set(self.QUERIES), "some queries were starved by the cap")

    def test_cap_is_still_exact_and_global(self) -> None:
        source = self._source(_per_query_client(self.jobs_by_query))

        results = list(source.fetch())

        self.assertEqual(len(results), self.MAX_JOBS)

    def test_dedup_holds_across_the_interleave(self) -> None:
        # q1 and q5 both return job 999 on page 0; it must be emitted exactly once.
        shared = _ai_job(999, "shared")
        jobs = copy.deepcopy(self.jobs_by_query)
        jobs["q1"][0] = [*jobs["q1"][0], shared]
        jobs["q5"][0] = [*jobs["q5"][0], shared]
        source = self._source(_per_query_client(jobs), max_jobs=100)

        results = list(source.fetch())

        external_ids = [r.external_id for r in results]
        self.assertEqual(external_ids.count("999"), 1)
        self.assertEqual(len(external_ids), len(set(external_ids)))

    def test_request_order_is_page_major(self) -> None:
        source = self._source(_per_query_client(self.jobs_by_query), max_jobs=1000)

        list(source.fetch())

        pages = [c.kwargs["json"]["page"] for c in source._client.post.call_args_list]
        # Every page-0 request precedes every page-1 request.
        self.assertEqual(pages, sorted(pages))
        self.assertEqual(pages, [0] * len(self.QUERIES) + [1] * len(self.QUERIES))

    def test_politeness_delay_runs_once_per_page_attempt(self) -> None:
        source = self._source(_per_query_client(self.jobs_by_query), max_jobs=1000)

        list(source.fetch())

        # No failures, so no backoff sleeps — every sleep is the politeness delay.
        delay_sleeps = [c for c in self.mock_sleep.call_args_list if c.args[0] == source._delay]
        self.assertEqual(len(delay_sleeps), source._client.post.call_count)
        self.assertEqual(len(delay_sleeps), len(self.QUERIES) * self.PAGES)

    def test_retry_skip_still_works_under_the_interleave(self) -> None:
        client = _per_query_client(self.jobs_by_query, fail_pages={("q3", 0)})
        source = self._source(client, max_jobs=1000)

        results = list(source.fetch())

        self.assertEqual(source.pages_failed, 1)
        covered = {self._query_of(r.external_id) for r in results}
        # Other queries are unaffected; q3 still contributes via its page 1.
        self.assertEqual(covered, set(self.QUERIES))
        self.assertNotIn("300", {r.external_id for r in results})


class _FakeClock:
    """A monotonic clock the test advances by hand.

    Real elapsed time cannot be asserted on — the whole point of the budget is a
    duration no test may actually wait out. Every second the adapter would spend
    is instead charged to this clock: the mocked `time.sleep` advances it by the
    slept amount, and the mocked transport advances it by `timeout_seconds`
    before raising, which is what a hung request costs in wall time.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class VietnamWorksBudgetTests(unittest.TestCase):
    """The global wall-clock budget — the 2026-08-18 nightly outage, reproduced.

    Run 32093739835 hung on every request and needed ~26 minutes to give up,
    against a 15-minute `timeout-minutes` ceiling in the workflow. The runner
    cancelled the job mid-fetch, so `fetch()` never returned, `main()` never
    reached `except IngestionSafetyError`, and the only diagnostic left was the
    spacing between log lines. These tests pin the property that failure was
    missing: a dead source ends the run from inside, in bounded time.
    """

    # The workflow's timeout-minutes: 15, in seconds. The bound every test here
    # is ultimately about — a run that exceeds this is killed rather than ending.
    JOB_CEILING_SECONDS = 900

    def setUp(self) -> None:
        self.fixture = _load_fixture()
        self.clock = _FakeClock()

        sleep_patcher = patch("time.sleep", side_effect=self.clock.advance)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        monotonic_patcher = patch("time.monotonic", side_effect=self.clock.monotonic)
        monotonic_patcher.start()
        self.addCleanup(monotonic_patcher.stop)

    def _hanging_client(self) -> MagicMock:
        """A client where every request hangs for the full timeout, then fails.

        This is the observed failure mode, not a 4xx: the source stopped
        answering rather than refusing, so each attempt cost `timeout_seconds`
        in full before `_post_with_retry` saw an exception at all.
        """
        client = MagicMock()
        _allow_robots(client)

        def side_effect(url: str, **kwargs: object) -> MagicMock:
            self.clock.advance(30)  # timeout_seconds
            raise httpx.TimeoutException("hung")

        client.post.side_effect = side_effect
        return client

    def _source(
        self,
        client: MagicMock,
        queries: list[str],
        pages_per_query: int,
        max_elapsed: float,
    ) -> VietnamWorksSource:
        source = VietnamWorksSource(client=client)
        source._queries = queries
        source._pages_per_query = pages_per_query
        source._max_elapsed = max_elapsed
        return source

    def _production_shape_source(self, client: MagicMock) -> VietnamWorksSource:
        """8 queries x 2 pages x a 600s budget — the shipped config's shape."""
        return self._source(
            client,
            queries=[f"q{i}" for i in range(8)],
            pages_per_query=2,
            max_elapsed=600,
        )

    def test_total_outage_finishes_inside_the_job_ceiling(self) -> None:
        # The regression. Unbounded, 16 pages x 96.6s each is ~1546s, which
        # overruns the 900s ceiling and gets the job cancelled instead of failed.
        client = self._hanging_client()
        source = self._production_shape_source(client)
        started = self.clock.now

        results = list(source.fetch())

        elapsed = self.clock.now - started
        self.assertEqual(results, [])
        self.assertLess(elapsed, self.JOB_CEILING_SECONDS)
        # Bound is the budget plus at most one page's worst case, not the budget
        # exactly — the check runs between pages, never mid-retry-ladder.
        self.assertLessEqual(elapsed, 600 + 96.6)

    def test_total_outage_stops_early_instead_of_attempting_every_page(self) -> None:
        client = self._hanging_client()
        source = self._production_shape_source(client)

        list(source.fetch())

        # 16 pages would be 48 attempts; the budget cuts it to 7 pages (21).
        attempted_pages = client.post.call_count / 3
        self.assertLess(attempted_pages, 16)
        self.assertEqual(client.post.call_count, 21)

    def test_fetch_returns_so_the_caller_can_reach_its_abort_path(self) -> None:
        # main() only logs `ingestion.aborted` if fetch() hands control back.
        # Under the outage it never did, which is why the run had no diagnostic.
        client = self._hanging_client()
        source = self._production_shape_source(client)

        results = list(source.fetch())

        self.assertEqual(results, [])
        self.assertTrue(source.budget_exhausted)

    def test_budget_exhaustion_is_logged_once_not_per_check(self) -> None:
        client = self._hanging_client()
        source = self._production_shape_source(client)

        with patch("src.services.ingestion.sources.vietnamworks.logger") as mock_logger:
            list(source.fetch())

        budget_events = [
            c for c in mock_logger.warning.call_args_list
            if c.args and c.args[0] == "ingestion.budget_exhausted"
        ]
        self.assertEqual(len(budget_events), 1)

    def test_expired_budget_stops_the_run_before_any_request(self) -> None:
        client = self._hanging_client()
        source = self._source(client, queries=["q"], pages_per_query=2, max_elapsed=0)

        results = list(source.fetch())

        self.assertEqual(results, [])
        client.post.assert_not_called()

    def test_healthy_run_is_untouched_by_the_budget(self) -> None:
        # The budget must be inert in the normal case: a real run fetches in
        # ~40s against a 600s budget, so it must never truncate a good night.
        client = _mock_client(self.fixture)
        source = self._production_shape_source(client)

        results = list(source.fetch())

        self.assertEqual(client.post.call_count, 16)
        self.assertFalse(source.budget_exhausted)
        self.assertTrue(results)

    def test_budget_state_resets_across_successive_fetch_calls(self) -> None:
        source = self._production_shape_source(self._hanging_client())
        list(source.fetch())
        self.assertTrue(source.budget_exhausted)

        source._client = _mock_client(self.fixture)
        list(source.fetch())

        self.assertFalse(source.budget_exhausted)


if __name__ == "__main__":
    unittest.main()
