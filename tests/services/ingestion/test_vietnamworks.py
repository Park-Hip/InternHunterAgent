import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.services.ingestion.models import RawPosting
from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vietnamworks_raw.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _mock_client(fixture: dict) -> MagicMock:
    """Return a mock httpx.Client whose .post() always returns the given fixture."""
    client = MagicMock()
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
    client.post.side_effect = side_effects
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


if __name__ == "__main__":
    unittest.main()
