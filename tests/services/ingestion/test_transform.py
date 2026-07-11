"""Unit tests for src/services/ingestion/transform.py.

All functions are pure; no DB, no network. Config is loaded from ingestion.yaml
via settings — the same mechanism used in production.
"""
from datetime import date
import unittest

from src.services.ingestion.transform import (
    classify_role,
    derive_is_internship,
    find_tech_stack,
    html_to_text,
    normalize_location,
    to_date,
)


class HtmlToTextTests(unittest.TestCase):
    def test_strips_tags_and_unescapes_entities(self) -> None:
        result = html_to_text("<p>Hello &amp; <b>World</b>!</p>")
        self.assertEqual(result, "Hello & World !")

    def test_collapses_whitespace(self) -> None:
        result = html_to_text("<p>  lots   of   space  </p>")
        self.assertEqual(result, "lots of space")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(html_to_text(None), "")

    def test_empty_string_returns_empty_string(self) -> None:
        self.assertEqual(html_to_text(""), "")

    def test_nested_tags(self) -> None:
        result = html_to_text("<ul><li>Python</li><li>SQL</li></ul>")
        self.assertIn("Python", result)
        self.assertIn("SQL", result)


class DeriveIsInternshipTests(unittest.TestCase):
    def test_intern_in_job_level(self) -> None:
        self.assertTrue(derive_is_internship("Intern", None))

    def test_thuc_tap_in_job_level_vi(self) -> None:
        self.assertTrue(derive_is_internship(None, "Thực tập"))

    def test_thuc_tap_case_insensitive(self) -> None:
        self.assertTrue(derive_is_internship(None, "THỰC TẬP"))

    def test_intern_case_insensitive(self) -> None:
        self.assertTrue(derive_is_internship("INTERN", None))

    def test_senior_is_not_internship(self) -> None:
        self.assertFalse(derive_is_internship("Senior", "Chuyên viên"))

    def test_both_none_is_not_internship(self) -> None:
        self.assertFalse(derive_is_internship(None, None))

    def test_intern_in_vi_level(self) -> None:
        # Some postings use "Thực Tập Sinh" as the Vietnamese level
        self.assertTrue(derive_is_internship(None, "Thực Tập Sinh"))


class ToDateTests(unittest.TestCase):
    def test_parses_iso_datetime_with_timezone(self) -> None:
        self.assertEqual(to_date("2026-07-30T23:59:59+07:00"), date(2026, 7, 30))

    def test_none_returns_none(self) -> None:
        self.assertIsNone(to_date(None))

    def test_garbage_returns_none(self) -> None:
        self.assertIsNone(to_date("not-a-date"))


class FindTechStackTests(unittest.TestCase):
    def test_finds_tech_in_skill_names(self) -> None:
        result = find_tech_stack("Python", "SQL")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("Python", techs)
        self.assertIn("SQL", techs)

    def test_finds_tech_in_description_text(self) -> None:
        result = find_tech_stack("Experience with PyTorch and Docker")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("PyTorch", techs)
        self.assertIn("Docker", techs)

    def test_no_match_returns_none(self) -> None:
        result = find_tech_stack("No technology keywords here")
        self.assertIsNone(result)

    def test_case_insensitive_match(self) -> None:
        result = find_tech_stack("proficient in python and airflow")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("Python", techs)
        self.assertIn("Airflow", techs)

    def test_extracts_techniques_from_source_tags(self) -> None:
        result = find_tech_stack("Machine Learning", "ETL", "Data Analysis")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("Machine Learning", techs)
        self.assertIn("ETL", techs)
        self.assertIn("Data Analysis", techs)

    def test_normalizes_aliases_and_buried_phrase_terms(self) -> None:
        result = find_tech_stack(
            "Data Visualization & Analysis (Power BI; SQL - basic; Python - basic)",
            "PowerBI",
            "Sql",
        )
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("Data Visualization", techs)
        self.assertIn("Power BI", techs)
        self.assertIn("SQL", techs)
        self.assertIn("Python", techs)

    def test_excludes_roles_and_soft_skills_by_omission(self) -> None:
        self.assertIsNone(find_tech_stack("Data Engineer", "Communication"))

    def test_preserves_dictionary_casing(self) -> None:
        # Even if text is lowercase, the output uses dictionary casing
        result = find_tech_stack("using pytorch and tensorflow")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("PyTorch", techs)
        self.assertIn("TensorFlow", techs)

    def test_deduplicates_across_sources(self) -> None:
        # "Python" appears in both skills and description
        result = find_tech_stack("Python", "Experience with Python and SQL")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertEqual(techs.count("Python"), 1)

    # --- word-boundary safety ---

    def test_r_not_detected_inside_keras(self) -> None:
        # "Keras" contains the letter 'r' but should not trigger the R tech entry
        result = find_tech_stack("Experience with Keras neural networks")
        techs = result.split(", ") if result else []
        self.assertNotIn("R", techs)
        self.assertIn("Keras", techs)

    def test_r_detected_as_standalone_word(self) -> None:
        result = find_tech_stack("Statistical analysis using R and Python")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("R", techs)

    def test_go_not_detected_inside_mongodb(self) -> None:
        result = find_tech_stack("Database experience with MongoDB")
        techs = result.split(", ") if result else []
        self.assertNotIn("Go", techs)
        self.assertIn("MongoDB", techs)

    def test_go_detected_as_standalone_word(self) -> None:
        result = find_tech_stack("Backend development using Go and Docker")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("Go", techs)

    def test_csharp_detected(self) -> None:
        result = find_tech_stack("Build APIs with C# and .NET")
        self.assertIsNotNone(result)
        techs = result.split(", ")  # type: ignore[union-attr]
        self.assertIn("C#", techs)

    def test_empty_sources_returns_none(self) -> None:
        self.assertIsNone(find_tech_stack("", ""))


class ClassifyRoleTests(unittest.TestCase):
    def test_data_scientist(self) -> None:
        self.assertEqual(classify_role("Senior Data Scientist", None), "Data Scientist")

    def test_data_engineer(self) -> None:
        self.assertEqual(classify_role("Data Engineer", None), "Data Engineer")

    def test_data_analyst(self) -> None:
        self.assertEqual(classify_role("Business Analyst", None), "Data Analyst")

    def test_ml_engineer(self) -> None:
        self.assertEqual(classify_role("Machine Learning Engineer", None), "ML Engineer")

    def test_ai_engineer(self) -> None:
        self.assertEqual(classify_role("AI Engineer", None), "AI Engineer")

    def test_software_developer(self) -> None:
        self.assertEqual(classify_role("Backend Developer", None), "Software Developer")

    def test_unmatched_title_returns_other(self) -> None:
        self.assertEqual(classify_role("Product Manager", None), "Other")

    def test_unmatched_vague_title_returns_other(self) -> None:
        self.assertEqual(classify_role("Team Lead", None), "Other")

    def test_first_match_wins(self) -> None:
        # "data engineer" keyword appears before "software developer" in taxonomy
        # so a title containing both should resolve to Data Engineer
        result = classify_role("Data Engineer and Software Developer", None)
        self.assertEqual(result, "Data Engineer")

    def test_case_insensitive(self) -> None:
        self.assertEqual(classify_role("DATA SCIENTIST", None), "Data Scientist")

    def test_mlops_maps_to_ml_engineer(self) -> None:
        self.assertEqual(classify_role("MLOps Engineer", None), "ML Engineer")

    def test_intern_data_engineer_title(self) -> None:
        # Vietnamese intern title — "data engineer" keyword present
        self.assertEqual(classify_role("Thực Tập Sinh Data Engineer", None), "Data Engineer")

    def test_function_children_accepted(self) -> None:
        # Passing children should not change the result (no crash)
        children = [{"id": 27, "name": "Data Engineer/Data Analyst/AI"}]
        self.assertEqual(classify_role("Data Scientist", children), "Data Scientist")


class NormalizeLocationTests(unittest.TestCase):
    def test_hcm_vietnamese_alias(self) -> None:
        self.assertEqual(normalize_location("Hồ Chí Minh"), "Ho Chi Minh City")

    def test_tphcm_alias(self) -> None:
        self.assertEqual(normalize_location("TPHCM"), "Ho Chi Minh City")

    def test_ha_noi_alias(self) -> None:
        self.assertEqual(normalize_location("Hà Nội"), "Hanoi")

    def test_ha_noi_en_alias(self) -> None:
        self.assertEqual(normalize_location("Ha Noi"), "Hanoi")

    def test_da_nang_alias(self) -> None:
        self.assertEqual(normalize_location("Đà Nẵng"), "Da Nang")

    def test_multi_city_comma_separated(self) -> None:
        result = normalize_location("Hồ Chí Minh", "Hà Nội")
        self.assertEqual(result, "Ho Chi Minh City, Hanoi")

    def test_multi_city_deduplicates_canonical(self) -> None:
        # "hcm" and "tphcm" both map to the same canonical city
        result = normalize_location("TPHCM", "HCM")
        self.assertEqual(result, "Ho Chi Minh City")

    def test_unknown_city_returns_other(self) -> None:
        self.assertEqual(normalize_location("Binh Duong"), "Other")

    def test_empty_string_returns_other(self) -> None:
        self.assertEqual(normalize_location(""), "Other")

    def test_no_sources_returns_other(self) -> None:
        self.assertEqual(normalize_location(), "Other")

    def test_mixed_known_and_unknown(self) -> None:
        # Unknown city "Binh Duong" is skipped; known "Hà Nội" maps to Hanoi
        result = normalize_location("Binh Duong", "Hà Nội")
        self.assertEqual(result, "Hanoi")

    def test_case_insensitive(self) -> None:
        self.assertEqual(normalize_location("HÀ NỘI"), "Hanoi")

    # --- word-boundary substring matching (T0010.6) ---

    def test_city_inside_free_form_address(self) -> None:
        result = normalize_location("12 Nguyen Hue, District 1, Ho Chi Minh City")
        self.assertIn("Ho Chi Minh City", result)

    def test_short_alias_inside_free_form_address(self) -> None:
        result = normalize_location("Some Street, Ba Dinh, HN")
        self.assertEqual(result, "Hanoi")

    def test_short_alias_does_not_match_inside_word(self) -> None:
        # "hn" and "hcm" only appear as substrings of larger words here —
        # word-boundary matching must not treat this as a city hit.
        result = normalize_location("John from the technology team")
        self.assertEqual(result, "Other")

    def test_two_cities_in_one_free_form_string(self) -> None:
        result = normalize_location(
            "Office in Ho Chi Minh City, branch office also in Ha Noi"
        )
        self.assertIn("Ho Chi Minh City", result)
        self.assertIn("Hanoi", result)

    def test_multi_city_deterministic_order_free_form(self) -> None:
        result = normalize_location(
            "Office in Ho Chi Minh City, branch office also in Ha Noi"
        )
        self.assertEqual(result, "Ho Chi Minh City, Hanoi")

    def test_dedup_when_multiple_keys_map_to_same_canonical_free_form(self) -> None:
        result = normalize_location("Ho Chi Minh, also known as Ho Chi Minh City")
        self.assertEqual(result, "Ho Chi Minh City")


if __name__ == "__main__":
    unittest.main()
