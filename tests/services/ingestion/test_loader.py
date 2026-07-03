import unittest
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from src.services.ingestion.models import NormalizedJob, RawPosting
from src.services.ingestion.sources.base import JobSource


def _make_posting(external_id: str = "job-001", payload: dict | None = None) -> RawPosting:
    return RawPosting(
        source="vietnamworks",
        external_id=external_id,
        source_url=f"https://example.com/job/{external_id}",
        raw_payload=payload or {"jobId": external_id, "jobTitle": "Intern", "companyName": "Acme"},
        content_hash="abc123",
    )


class StubSource(JobSource):
    source = "vietnamworks"

    def __init__(self, postings: list[RawPosting]) -> None:
        self._postings = postings

    def fetch(self) -> Iterator[RawPosting]:
        yield from self._postings


class RunIngestionTests(unittest.TestCase):
    @patch("src.services.ingestion.loader.replace_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_summary_counts_match_fetched_postings(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_replace_clean: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        postings = [_make_posting(f"job-{i}") for i in range(5)]
        stub = StubSource(postings)
        mock_upsert_raw.return_value = 5
        mock_replace_clean.return_value = 5
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        result = run_ingestion(source=stub)

        self.assertEqual(result["fetched"], 5)
        self.assertEqual(result["raw_upserted"], 5)
        self.assertEqual(result["clean_loaded"], 5)

    @patch("src.services.ingestion.loader.replace_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_raw_upsert_called_before_clean_replace(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_replace_clean: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        call_order: list[str] = []
        mock_upsert_raw.side_effect = lambda _: call_order.append("raw") or 1
        mock_replace_clean.side_effect = lambda _: call_order.append("clean") or 1
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        run_ingestion(source=StubSource([_make_posting()]))

        self.assertEqual(call_order, ["raw", "clean"])

    @patch("src.services.ingestion.loader.replace_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_normalized_jobs_derive_from_fetched_payloads(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_replace_clean: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        payload = {"jobId": "42", "jobTitle": "Intern", "companyName": "Corp"}
        posting = _make_posting("42", payload)
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)
        mock_upsert_raw.return_value = 1
        mock_replace_clean.return_value = 1

        run_ingestion(source=StubSource([posting]))

        mock_normalize.assert_called_once_with(payload)

    @patch("src.services.ingestion.loader.replace_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_empty_fetch_passes_empty_lists_through(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_replace_clean: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_upsert_raw.return_value = 0
        mock_replace_clean.return_value = 0

        result = run_ingestion(source=StubSource([]))

        self.assertEqual(result["fetched"], 0)
        mock_upsert_raw.assert_called_once_with([])
        mock_replace_clean.assert_called_once_with([])
        mock_normalize.assert_not_called()

    @patch("src.services.ingestion.loader.replace_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    def test_malformed_payload_is_skipped_not_fatal(
        self,
        mock_upsert_raw: MagicMock,
        mock_replace_clean: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        good_a = _make_posting("job-001")
        bad = _make_posting("job-002", payload={"jobTitle": "Missing jobId"})
        good_b = _make_posting("job-003")
        mock_upsert_raw.return_value = 3
        mock_replace_clean.return_value = 2

        result = run_ingestion(source=StubSource([good_a, bad, good_b]))

        self.assertEqual(result["fetched"], 3)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["clean_loaded"], 2)
        loaded = mock_replace_clean.call_args[0][0]
        self.assertEqual(len(loaded), 2)
        self.assertTrue(all(isinstance(job, NormalizedJob) for job in loaded))
        loaded_external_ids = {job.external_id for job in loaded}
        self.assertEqual(loaded_external_ids, {"job-001", "job-003"})

    def test_import_has_no_side_effects(self) -> None:
        # Simply importing the module must not raise or trigger DB/network
        import importlib
        import src.services.ingestion.loader as _loader  # noqa: F401

        importlib.reload(_loader)


if __name__ == "__main__":
    unittest.main()
