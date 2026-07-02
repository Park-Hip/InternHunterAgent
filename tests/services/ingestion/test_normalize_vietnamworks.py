"""Unit tests for src/services/ingestion/normalize/vietnamworks.py.

Uses fixture jobs 1001–1004 fed directly to to_normalized_job().
No DB, no network — the normalizer is a pure dict → NormalizedJob transform.
"""
import json
import unittest
from pathlib import Path

from src.services.ingestion.models import NormalizedJob
from src.services.ingestion.normalize.vietnamworks import to_normalized_job

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vietnamworks_raw.json"


def _jobs() -> dict[int, dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {j["jobId"]: j for j in data["data"]}


class ToNormalizedJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _jobs()

    # ------------------------------------------------------------------
    # Return type and required fields
    # ------------------------------------------------------------------

    def test_returns_normalized_job_instance(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertIsInstance(result, NormalizedJob)

    def test_source_is_vietnamworks(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.source, "vietnamworks")

    def test_external_id_is_string(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.external_id, "1001")

    def test_title_and_company_populated(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.title, "Data Scientist")
        self.assertEqual(result.company, "TechCorp Vietnam")

    def test_source_url_populated(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertIsNotNone(result.source_url)
        self.assertIn("vietnamworks.com", result.source_url)  # type: ignore[operator]

    # ------------------------------------------------------------------
    # posted_date is always None (deferred to T0009.8)
    # ------------------------------------------------------------------

    def test_posted_date_is_none(self) -> None:
        for job_id in (1001, 1002, 1003, 1004):
            with self.subTest(job_id=job_id):
                self.assertIsNone(to_normalized_job(self.jobs[job_id]).posted_date)

    # ------------------------------------------------------------------
    # Salary — visible vs hidden
    # ------------------------------------------------------------------

    def test_visible_salary_populates_fields(self) -> None:
        # job 1001: isSalaryVisible=true, salaryMin=1500, salaryMax=2500, salaryCurrency=USD
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.salary_min, 1500)
        self.assertEqual(result.salary_max, 2500)
        self.assertEqual(result.salary_currency, "USD")
        self.assertFalse(result.is_salary_negotiable)

    def test_hidden_salary_nulls_min_max_currency(self) -> None:
        # job 1002: isSalaryVisible=false → min/max/currency must all be None
        result = to_normalized_job(self.jobs[1002])
        self.assertIsNone(result.salary_min)
        self.assertIsNone(result.salary_max)
        self.assertIsNone(result.salary_currency)

    def test_hidden_salary_sets_negotiable_true(self) -> None:
        result = to_normalized_job(self.jobs[1002])
        self.assertTrue(result.is_salary_negotiable)

    def test_hidden_salary_job_1004(self) -> None:
        result = to_normalized_job(self.jobs[1004])
        self.assertIsNone(result.salary_min)
        self.assertIsNone(result.salary_max)
        self.assertTrue(result.is_salary_negotiable)

    # ------------------------------------------------------------------
    # Description — merged blob
    # ------------------------------------------------------------------

    def test_description_contains_job_description_text(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertIsNotNone(result.description)
        self.assertIn("Build and deploy ML models", result.description)  # type: ignore[operator]

    def test_description_contains_requirement_text(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertIn("3+ years experience in data science", result.description)  # type: ignore[operator]

    def test_description_contains_benefit_text(self) -> None:
        # job 1001 has benefits with benefitValue containing benefit text
        result = to_normalized_job(self.jobs[1001])
        self.assertIn("Full health and dental coverage", result.description)  # type: ignore[operator]

    def test_description_is_single_blob(self) -> None:
        # description is a string, not a list
        result = to_normalized_job(self.jobs[1001])
        self.assertIsInstance(result.description, str)

    def test_empty_requirement_still_has_description(self) -> None:
        # job 1002 has empty jobRequirement — description should still have jobDescription
        result = to_normalized_job(self.jobs[1002])
        self.assertIsNotNone(result.description)
        self.assertIn("Lead the marketing team", result.description)  # type: ignore[operator]

    # ------------------------------------------------------------------
    # Internship flag
    # ------------------------------------------------------------------

    def test_intern_job_flagged(self) -> None:
        # job 1003: jobLevelVI="Thực tập" → is_internship=True
        result = to_normalized_job(self.jobs[1003])
        self.assertTrue(result.is_internship)

    def test_senior_job_not_internship(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertFalse(result.is_internship)

    # ------------------------------------------------------------------
    # Role classification
    # ------------------------------------------------------------------

    def test_data_scientist_role(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.role, "Data Scientist")

    def test_data_engineer_intern_role(self) -> None:
        # job 1003: "Thực Tập Sinh Data Engineer" → Data Engineer
        result = to_normalized_job(self.jobs[1003])
        self.assertEqual(result.role, "Data Engineer")

    def test_it_pm_role_is_other(self) -> None:
        # job 1004: "IT Project Manager" — no taxonomy match → Other
        result = to_normalized_job(self.jobs[1004])
        self.assertEqual(result.role, "Other")

    # ------------------------------------------------------------------
    # Location normalisation
    # ------------------------------------------------------------------

    def test_hcm_location_canonical(self) -> None:
        # job 1001: address "Hồ Chí Minh" → "Ho Chi Minh City"
        # workingLocations (cityName) also includes "Ha Noi" → multi-city result
        result = to_normalized_job(self.jobs[1001])
        self.assertIn("Ho Chi Minh City", result.location)  # type: ignore[operator]

    def test_multi_city_from_working_locations(self) -> None:
        # job 1001 has workingLocations (cityName) with both HCM and Hanoi
        result = to_normalized_job(self.jobs[1001])
        self.assertIn("Hanoi", result.location)  # type: ignore[operator]

    def test_hanoi_location_canonical(self) -> None:
        # job 1002: address "Hà Nội" → "Hanoi"
        result = to_normalized_job(self.jobs[1002])
        self.assertEqual(result.location, "Hanoi")

    # ------------------------------------------------------------------
    # Tech stack
    # ------------------------------------------------------------------

    def test_tech_stack_from_skills(self) -> None:
        # job 1001 skills: Python, SQL
        result = to_normalized_job(self.jobs[1001])
        self.assertIsNotNone(result.tech_stack)
        techs = result.tech_stack.split(", ")  # type: ignore[union-attr]
        self.assertIn("Python", techs)
        self.assertIn("SQL", techs)

    def test_tech_stack_from_intern_skills(self) -> None:
        # job 1003 skills: Python, Airflow
        result = to_normalized_job(self.jobs[1003])
        self.assertIsNotNone(result.tech_stack)
        techs = result.tech_stack.split(", ")  # type: ignore[union-attr]
        self.assertIn("Python", techs)
        self.assertIn("Airflow", techs)

    def test_no_skills_no_matching_desc_gives_none(self) -> None:
        # job 1004 has no skills and a generic description with no tech keywords
        result = to_normalized_job(self.jobs[1004])
        self.assertIsNone(result.tech_stack)

    # ------------------------------------------------------------------
    # job_level passthrough
    # ------------------------------------------------------------------

    def test_job_level_populated(self) -> None:
        result = to_normalized_job(self.jobs[1001])
        self.assertEqual(result.job_level, "Senior")

    def test_intern_job_level(self) -> None:
        result = to_normalized_job(self.jobs[1003])
        self.assertEqual(result.job_level, "Intern")


if __name__ == "__main__":
    unittest.main()
