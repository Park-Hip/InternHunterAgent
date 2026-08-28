import unittest
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from src.services.ingestion.models import NormalizedJob, RawPosting
from src.services.ingestion.raw_store import RawUpsertCounts
from src.services.ingestion.sources.base import JobSource


def _make_posting(
    external_id: str = "job-001", payload: dict | None = None
) -> RawPosting:
    return RawPosting(
        source="vietnamworks",
        external_id=external_id,
        source_url=f"https://example.com/job/{external_id}",
        raw_payload=payload
        or {"jobId": external_id, "jobTitle": "Intern", "companyName": "Acme"},
        content_hash="abc123",
    )


class StubSource(JobSource):
    source = "vietnamworks"

    def __init__(self, postings: list[RawPosting]) -> None:
        self._postings = postings

    def fetch(self) -> Iterator[RawPosting]:
        yield from self._postings


class RunIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_persist = patch(
            "src.services.ingestion.loader.persist_ingestion_run"
        ).start()
        self.addCleanup(patch.stopall)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_summary_counts_match_fetched_postings(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        postings = [_make_posting(f"job-{i}") for i in range(5)]
        stub = StubSource(postings)
        mock_upsert_raw.return_value = RawUpsertCounts(new=2, changed=1, unchanged=2)
        mock_upsert_clean.return_value = 5
        mock_expire.return_value = 0
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        result = run_ingestion(source=stub)

        self.assertEqual(result["fetched"], 5)
        self.assertEqual(result["raw_upserted"], 5)
        self.assertEqual(result["raw_new"], 2)
        self.assertEqual(result["raw_changed"], 1)
        self.assertEqual(result["raw_unchanged"], 2)
        self.assertEqual(result["clean_loaded"], 5)
        self.assertEqual(result["expired_count"], 0)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_raw_upsert_called_before_clean_upsert_before_expiry(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        call_order: list[str] = []
        mock_upsert_raw.side_effect = lambda _: (
            call_order.append("raw") or RawUpsertCounts(1, 0, 0)
        )
        mock_upsert_clean.side_effect = lambda _: call_order.append("clean") or 1
        mock_expire.side_effect = lambda _: call_order.append("expire") or 0
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        run_ingestion(source=StubSource([_make_posting()]))

        self.assertEqual(call_order, ["raw", "clean", "expire"])

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_normalized_jobs_derive_from_fetched_payloads(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        payload = {"jobId": "42", "jobTitle": "Intern", "companyName": "Corp"}
        posting = _make_posting("42", payload)
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)
        mock_upsert_raw.return_value = RawUpsertCounts(1, 0, 0)
        mock_upsert_clean.return_value = 1
        mock_expire.return_value = 0

        run_ingestion(source=StubSource([posting]))

        mock_normalize.assert_called_once_with(payload)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_empty_fetch_passes_empty_lists_through(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(0, 0, 0)
        mock_upsert_clean.return_value = 0
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource([]))

        self.assertEqual(result["fetched"], 0)
        mock_upsert_raw.assert_called_once_with([])
        mock_upsert_clean.assert_called_once_with([])
        mock_normalize.assert_not_called()

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    def test_malformed_payload_is_skipped_not_fatal(
        self,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        good_a = _make_posting("job-001")
        bad = _make_posting("job-002", payload={"jobTitle": "Missing jobId"})
        good_b = _make_posting("job-003")
        mock_upsert_raw.return_value = RawUpsertCounts(3, 0, 0)
        mock_upsert_clean.return_value = 2
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource([good_a, bad, good_b]))

        self.assertEqual(result["fetched"], 3)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["clean_loaded"], 2)
        loaded = mock_upsert_clean.call_args[0][0]
        self.assertEqual(len(loaded), 2)
        self.assertTrue(all(isinstance(job, NormalizedJob) for job in loaded))
        loaded_external_ids = {job.external_id for job in loaded}
        self.assertEqual(loaded_external_ids, {"job-001", "job-003"})

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_expiry_runs_after_upsert_with_configured_window(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 14},
            "safety": {"min_yield": 0},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(1, 0, 0)
        mock_upsert_clean.return_value = 1
        mock_expire.return_value = 3
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        result = run_ingestion(source=StubSource([_make_posting()]))

        mock_expire.assert_called_once_with(14)
        self.assertEqual(result["expired_count"], 3)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    def test_pages_failed_surfaced_in_summary(
        self,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(0, 0, 0)
        mock_upsert_clean.return_value = 0
        mock_expire.return_value = 0

        stub = StubSource([])
        stub.pages_failed = 3

        result = run_ingestion(source=stub)

        self.assertEqual(result["pages_failed"], 3)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    def test_schema_assertion_failure_aborts_before_any_upsert(
        self,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import IngestionSafetyError, run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0},
        }
        mock_schema_assert.side_effect = IngestionSafetyError(
            "clean_jobs schema drift detected"
        )

        with self.assertRaises(IngestionSafetyError):
            run_ingestion(source=StubSource([_make_posting()]))

        mock_upsert_raw.assert_not_called()
        mock_upsert_clean.assert_not_called()
        mock_expire.assert_not_called()

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    def test_under_floor_yield_aborts_before_clean_write_and_expiry(
        self,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import IngestionSafetyError, run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 20},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(1, 0, 0)

        with self.assertRaises(IngestionSafetyError):
            run_ingestion(source=StubSource([_make_posting()]))

        mock_upsert_raw.assert_called_once()
        mock_upsert_clean.assert_not_called()
        mock_expire.assert_not_called()
        persisted = self.mock_persist.call_args.args[0]
        self.assertEqual(persisted.outcome, "safety_aborted")
        self.assertEqual(persisted.failure_phase, "yield_check")
        self.assertEqual(persisted.fetched, 1)
        self.assertEqual(persisted.raw_upserted, 1)
        self.assertIsNone(persisted.clean_loaded)
        self.assertIsNone(persisted.expired_count)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_happy_path_calls_all_checks_in_order_with_unchanged_summary_keys(
        self,
        mock_normalize: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 1},
        }
        call_order: list[str] = []
        mock_schema_assert.side_effect = lambda: call_order.append("schema")
        mock_upsert_raw.side_effect = lambda _: (
            call_order.append("raw") or RawUpsertCounts(1, 0, 0)
        )
        mock_upsert_clean.side_effect = lambda _: call_order.append("clean") or 1
        mock_expire.side_effect = lambda _: call_order.append("expire") or 0
        mock_normalize.return_value = MagicMock(spec=NormalizedJob)

        result = run_ingestion(source=StubSource([_make_posting()]))

        self.assertEqual(call_order, ["schema", "raw", "clean", "expire"])
        self.assertEqual(
            set(result.keys()),
            {
                "fetched",
                "raw_upserted",
                "raw_new",
                "raw_changed",
                "raw_unchanged",
                "clean_loaded",
                "skipped",
                "expired_count",
                "pages_failed",
            },
        )
        persisted = self.mock_persist.call_args.args[0]
        self.assertEqual(persisted.outcome, "completed")
        self.assertIsNone(persisted.failure_phase)
        self.assertEqual(persisted.fetched, 1)
        self.assertEqual(persisted.clean_loaded, 1)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    def test_runtime_failure_persists_known_partial_metrics(
        self, mock_schema_assert: MagicMock
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_schema_assert.side_effect = RuntimeError("database unavailable")

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            run_ingestion(source=StubSource([_make_posting()]))

        persisted = self.mock_persist.call_args.args[0]
        self.assertEqual(persisted.outcome, "failed")
        self.assertEqual(persisted.failure_phase, "schema_check")
        self.assertEqual(persisted.failure_code, "unexpected_error")
        self.assertIsNone(persisted.fetched)
        self.assertIsNone(persisted.raw_upserted)

    def test_import_has_no_side_effects(self) -> None:
        # Simply importing the module must not raise or trigger DB/network
        import importlib
        import src.services.ingestion.loader as _loader  # noqa: F401

        importlib.reload(_loader)


if __name__ == "__main__":
    unittest.main()
