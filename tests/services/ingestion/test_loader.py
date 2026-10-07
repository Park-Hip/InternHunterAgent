import unittest
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from src.services.ingestion.models import NormalizedJob, RawPosting
from src.services.ingestion.raw_store import RawUpsertCounts


def _use_normalizer(mock_normalize: MagicMock, normalize: MagicMock) -> None:
    """Route the loader's normalizer call to `normalize` for the duration of a test."""
    mock_normalize.side_effect = normalize


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


def _make_normalized_job(external_id: str = "job-001", **overrides) -> NormalizedJob:
    defaults = {
        "source": "vietnamworks",
        "external_id": external_id,
        "source_url": f"https://example.com/job/{external_id}",
        "title": "Data Intern",
        "company": "Acme Corp",
        "role": "Data Science",
        "is_internship": True,
        "salary_min": 2000.0,
        "salary_max": 3000.0,
        "salary_currency": "USD",
        "is_salary_negotiable": False,
    }
    return NormalizedJob(**{**defaults, **overrides})


class StubSource:
    source = "vietnamworks"
    pages_failed = 0

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
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(5)]
        stub = StubSource(postings)
        mock_upsert_raw.return_value = RawUpsertCounts(new=2, changed=1, unchanged=2)
        mock_upsert_clean.return_value = 5
        mock_expire.return_value = 0
        _use_normalizer(mock_binding, MagicMock(return_value=_make_normalized_job()))

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
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        call_order: list[str] = []
        mock_upsert_raw.side_effect = lambda _: (
            call_order.append("raw") or RawUpsertCounts(1, 0, 0)
        )
        mock_upsert_clean.side_effect = lambda _: call_order.append("clean") or 1
        mock_expire.side_effect = lambda _: call_order.append("expire") or 0
        _use_normalizer(mock_binding, MagicMock(return_value=_make_normalized_job()))

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
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        payload = {"jobId": "42", "jobTitle": "Intern", "companyName": "Corp"}
        posting = _make_posting("42", payload)
        _use_normalizer(mock_binding, MagicMock(return_value=_make_normalized_job()))
        mock_upsert_raw.return_value = RawUpsertCounts(1, 0, 0)
        mock_upsert_clean.return_value = 1
        mock_expire.return_value = 0

        run_ingestion(source=StubSource([posting]))

        mock_binding.assert_called_once_with(payload)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_empty_fetch_passes_empty_lists_through(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(0, 0, 0)
        mock_upsert_clean.return_value = 0
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource([]))

        self.assertEqual(result["fetched"], 0)
        mock_upsert_raw.assert_called_once_with([])
        mock_upsert_clean.assert_called_once_with([])
        mock_binding.assert_not_called()

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_parse_failures_count_toward_rejection_ratio(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import IngestionSafetyError, run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(20)]

        def normalize(payload):
            job_id = payload["jobId"]
            if job_id in {"job-0", "job-1"}:
                raise ValueError("missing jobId")
            if job_id == "job-2":
                return _make_normalized_job(job_id, title="")
            return _make_normalized_job(job_id)

        _use_normalizer(mock_binding, normalize)
        mock_upsert_raw.return_value = RawUpsertCounts(20, 0, 0)
        mock_upsert_clean.return_value = 17
        mock_expire.return_value = 0

        with self.assertRaises(IngestionSafetyError):
            run_ingestion(source=StubSource(postings))

        mock_upsert_raw.assert_called_once()
        mock_upsert_clean.assert_not_called()
        mock_expire.assert_not_called()
        persisted = self.mock_persist.call_args.args[0]
        self.assertEqual(persisted.outcome, "safety_aborted")
        self.assertEqual(persisted.failure_phase, "row_quality_check")
        self.assertEqual(persisted.skipped, 3)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_expiry_runs_after_upsert_with_configured_window(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 14},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        mock_upsert_raw.return_value = RawUpsertCounts(1, 0, 0)
        mock_upsert_clean.return_value = 1
        mock_expire.return_value = 3
        _use_normalizer(mock_binding, MagicMock(return_value=_make_normalized_job()))

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
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
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
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
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
            "safety": {"min_yield": 20, "max_rejected_ratio": 0.10},
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
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 1, "max_rejected_ratio": 0.10},
        }
        call_order: list[str] = []
        mock_schema_assert.side_effect = lambda: call_order.append("schema")
        mock_upsert_raw.side_effect = lambda _: (
            call_order.append("raw") or RawUpsertCounts(1, 0, 0)
        )
        mock_upsert_clean.side_effect = lambda _: call_order.append("clean") or 1
        mock_expire.side_effect = lambda _: call_order.append("expire") or 0
        _use_normalizer(mock_binding, MagicMock(return_value=_make_normalized_job()))

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
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_single_blank_title_row_dropped_and_run_completes(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(20)]

        def normalize(payload):
            job_id = payload["jobId"]
            if job_id == "job-0":
                return _make_normalized_job(job_id, title="")
            return _make_normalized_job(job_id)

        _use_normalizer(mock_binding, normalize)
        mock_upsert_raw.return_value = RawUpsertCounts(20, 0, 0)
        mock_upsert_clean.return_value = 19
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource(postings))

        self.assertEqual(result["skipped"], 1)
        loaded = mock_upsert_clean.call_args[0][0]
        self.assertEqual(len(loaded), 19)
        mock_expire.assert_called_once()

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_two_blank_title_rows_at_ratio_complete(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(20)]

        def normalize(payload):
            job_id = payload["jobId"]
            if job_id in {"job-0", "job-1"}:
                return _make_normalized_job(job_id, title="")
            return _make_normalized_job(job_id)

        _use_normalizer(mock_binding, normalize)
        mock_upsert_raw.return_value = RawUpsertCounts(20, 0, 0)
        mock_upsert_clean.return_value = 18
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource(postings))

        self.assertEqual(result["skipped"], 2)
        loaded = mock_upsert_clean.call_args[0][0]
        self.assertEqual(len(loaded), 18)
        mock_expire.assert_called_once()

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_three_blank_title_rows_above_ratio_abort(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import IngestionSafetyError, run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(20)]

        def normalize(payload):
            job_id = payload["jobId"]
            if job_id in {"job-0", "job-1", "job-2"}:
                return _make_normalized_job(job_id, title="")
            return _make_normalized_job(job_id)

        _use_normalizer(mock_binding, normalize)
        mock_upsert_raw.return_value = RawUpsertCounts(20, 0, 0)
        mock_upsert_clean.return_value = 17
        mock_expire.return_value = 0

        with self.assertRaises(IngestionSafetyError):
            run_ingestion(source=StubSource(postings))

        mock_upsert_raw.assert_called_once()
        mock_upsert_clean.assert_not_called()
        mock_expire.assert_not_called()
        persisted = self.mock_persist.call_args.args[0]
        self.assertEqual(persisted.outcome, "safety_aborted")
        self.assertEqual(persisted.failure_phase, "row_quality_check")
        self.assertEqual(persisted.skipped, 3)

    @patch("src.services.ingestion.loader.assert_clean_jobs_schema")
    @patch("src.services.ingestion.loader.settings")
    @patch("src.services.ingestion.loader.expire_stale_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_clean_jobs")
    @patch("src.services.ingestion.loader.upsert_raw_postings")
    @patch("src.services.ingestion.loader.to_normalized_job")
    def test_nan_salary_row_dropped_and_run_completes(
        self,
        mock_binding: MagicMock,
        mock_upsert_raw: MagicMock,
        mock_upsert_clean: MagicMock,
        mock_expire: MagicMock,
        mock_settings: MagicMock,
        mock_schema_assert: MagicMock,
    ) -> None:
        from src.services.ingestion.loader import run_ingestion

        mock_settings.ingestion_yaml = {
            "lifecycle": {"expire_after_days": 7},
            "safety": {"min_yield": 0, "max_rejected_ratio": 0.10},
        }
        postings = [_make_posting(f"job-{i}") for i in range(20)]

        def normalize(payload):
            job_id = payload["jobId"]
            if job_id == "job-0":
                return _make_normalized_job(job_id, salary_min=float("nan"))
            return _make_normalized_job(job_id)

        _use_normalizer(mock_binding, normalize)
        mock_upsert_raw.return_value = RawUpsertCounts(20, 0, 0)
        mock_upsert_clean.return_value = 19
        mock_expire.return_value = 0

        result = run_ingestion(source=StubSource(postings))

        self.assertEqual(result["skipped"], 1)
        mock_expire.assert_called_once()

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


class DefaultSourceTests(unittest.TestCase):
    def test_no_source_builds_vietnamworks(self) -> None:
        from src.services.ingestion.loader import run_ingestion

        with patch("src.services.ingestion.loader.persist_ingestion_run"), \
             patch("src.services.ingestion.loader.assert_clean_jobs_schema"), \
             patch("src.services.ingestion.loader.VietnamWorksSource") as mock_source:
            mock_source.return_value.fetch.side_effect = RuntimeError("stop after init")
            with self.assertRaisesRegex(RuntimeError, "stop after init"):
                run_ingestion()
        mock_source.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
