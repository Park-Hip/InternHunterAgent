"""Load and validate every baseline case before a runner or scorer reads one.

The baseline is four files, each with one role (#761):

``baseline.yaml``
    The 36-question #708 corpus. All of it is dev: the 12 cases that were once
    held-out were used while tuning ``sql_generation``, so they are regression
    cases now, not a generalization measurement.
``paraphrases.yaml``
    Dev questions reworded, with the reference SQL of the case they paraphrase.
    They measure wording sensitivity rather than recall.
``held_out.yaml``
    The fresh held-out set. It is scored at a milestone and is not read while a
    prompt, tool, or query-path change is being tuned. It also carries the
    split-breakdown, paging, and refused-statement cases from #745.
``safety.yaml``
    The safety smoke set: destructive, injection, and secret-exfiltration arms
    plus an injection carried by posting text. These have an ``expect`` block
    instead of reference SQL and are scored for refusal and no leaked value.

Every file is validated on load. In particular ``answerable`` and
``expect.refusal`` must be *quoted* enum strings: PyYAML resolves a bare
``yes``/``no`` to a boolean, so an unquoted value would silently become
``True``/``False`` and change what a case expects. The node check runs before
the value check, because by the time ``safe_load`` returns there is no
difference left to see.

The loader is deliberately database-free. It checks the grammar and the SQL
shape; executing a reference statement against the frozen snapshot is the
scorer's job. A reference statement still has to pass ``validate_sql`` here, so
a case cannot ship a statement the product itself would refuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Any, Sequence

import yaml

from src.services.query.sql_validator import validate_sql

EVALS_ROOT = Path(__file__).resolve().parent
DATASETS_ROOT = EVALS_ROOT / "datasets"


@dataclass(frozen=True)
class DatasetFile:
    """One case file and the split every case in it must declare."""

    name: str
    path: Path
    split: str


BASELINE = DatasetFile("baseline", DATASETS_ROOT / "baseline.yaml", "dev")
PARAPHRASES = DatasetFile("paraphrases", DATASETS_ROOT / "paraphrases.yaml", "dev")
HELD_OUT = DatasetFile("held_out", DATASETS_ROOT / "held_out.yaml", "held-out")
SAFETY = DatasetFile("safety", DATASETS_ROOT / "safety.yaml", "safety")

DATASET_FILES: tuple[DatasetFile, ...] = (BASELINE, PARAPHRASES, HELD_OUT, SAFETY)

COMPARE_MODES = {"ids": "ids_only", "count": "aggregate_count", "rows": "rows_equal"}
SPLITS = {"dev", "held-out", "safety"}
NEEDS = {
    "find",
    "count",
    "inspect",
    "narrow",
    "breakdown",
    "paging",
    "refusal",
    "safety",
    "out_of_scope",
}
STYLES = {"mixed", "diacritics", "no_diacritics"}
ANSWERABLE = {"yes", "no", "partial"}
EXPECTED_REFUSAL = {"yes", "no"}

BASE_KEYS = {
    "id",
    "split",
    "need",
    "turns",
    "style",
    "answerable",
    "expected",
    "reference_sql",
    "compare",
    "as_of",
    "detail_check",
    "note",
    "review",
    "expect",
    "paraphrase_of",
}
REQUIRED_KEYS = {"id", "split", "need", "turns", "style", "answerable", "expected", "reference_sql"}

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SELECT = re.compile(r"\s*SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM\s", re.I | re.S)
_COUNT = re.compile(r"\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+count\s*", re.I)
_TABLE = re.compile(r"^\s*(?:SELECT|WITH|\()", re.I)


class DatasetError(ValueError):
    """A baseline case file does not follow the committed grammar."""


def _fail(path: Path, case_id: str | None, message: str) -> None:
    where = f"{path.name}: case {case_id}" if case_id else path.name
    raise DatasetError(f"{where}: {message}")


def _scalar(node: yaml.Node, path: Path, case_id: str | None, field: str) -> yaml.ScalarNode:
    if not isinstance(node, yaml.ScalarNode):
        _fail(path, case_id, f"{field} must be a scalar")
    return node


def _mapping_fields(node: yaml.Node, path: Path, case_id: str | None) -> dict[str, yaml.Node]:
    if not isinstance(node, yaml.MappingNode):
        _fail(path, case_id, "must be a mapping")
    fields: dict[str, yaml.Node] = {}
    for key, value in node.value:
        if not isinstance(key, yaml.ScalarNode):
            _fail(path, case_id, "has a non-scalar key")
        fields[key.value] = value
    return fields


def _require_quoted(
    node: yaml.Node, *, path: Path, case_id: str | None, field: str
) -> None:
    scalar = _scalar(node, path, case_id, field)
    if scalar.tag != "tag:yaml.org,2002:str":
        _fail(
            path,
            case_id,
            f"{field} must be a quoted string; an unquoted yes/no is a YAML boolean",
        )
    if scalar.style not in ("'", '"'):
        _fail(path, case_id, f"{field} must be quoted")
    assert isinstance(scalar.value, str)


def _check_quoted_enums(path: Path, text: str) -> None:
    """Refuse a bare ``yes``/``no`` before PyYAML turns it into a boolean."""
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise DatasetError(f"{path.name}: not valid YAML: {exc}") from exc
    if not isinstance(root, yaml.SequenceNode):
        raise DatasetError(f"{path.name}: the top level must be a list of cases")
    for node in root.value:
        if not isinstance(node, yaml.MappingNode):
            continue
        fields = {
            key.value: value
            for key, value in node.value
            if isinstance(key, yaml.ScalarNode)
        }
        case_id_node = fields.get("id")
        case_id = case_id_node.value if isinstance(case_id_node, yaml.ScalarNode) else None
        if "answerable" in fields:
            _require_quoted(
                fields["answerable"],
                path=path,
                case_id=case_id,
                field="answerable",
            )
        expect = fields.get("expect")
        if isinstance(expect, yaml.MappingNode):
            expect_fields = {
                key.value: value
                for key, value in expect.value
                if isinstance(key, yaml.ScalarNode)
            }
            if "refusal" in expect_fields:
                _require_quoted(
                    expect_fields["refusal"],
                    path=path,
                    case_id=case_id,
                    field="expect.refusal",
                )


def _projected_columns(sql: str) -> list[str] | None:
    match = _SELECT.match(sql)
    if match is None:
        return None
    columns: list[str] = []
    for part in match.group(1).split(","):
        part = part.strip()
        alias = re.search(r"\s+AS\s+(\w+)\s*$", part, re.I)
        columns.append(
            (alias.group(1) if alias else part.rsplit(".", 1)[-1]).strip('"').lower()
        )
    return columns


def _validate_reference_sql(
    case: dict[str, Any], *, path: Path, case_id: str
) -> None:
    references = case["reference_sql"]
    if not isinstance(references, list):
        _fail(path, case_id, "reference_sql must be a list")
    if references and len(references) != len(case["turns"]):
        _fail(
            path,
            case_id,
            "reference_sql must have one entry per turn (null for a detail turn)",
        )
    if not references:
        if "compare" in case:
            _fail(path, case_id, "compare is meaningless without reference_sql")
        if case["need"] not in {"out_of_scope", "refusal", "safety"}:
            _fail(path, case_id, f"need {case['need']!r} needs reference SQL")
        return
    if case["need"] in {"out_of_scope", "refusal", "safety"}:
        _fail(path, case_id, f"need {case['need']!r} must not carry reference SQL")
    if not any(references):
        _fail(path, case_id, "reference_sql is entirely null")

    compare = case.get("compare")
    if compare not in COMPARE_MODES:
        _fail(path, case_id, f"compare must be one of {sorted(COMPARE_MODES)}")
    for index, sql in enumerate(references):
        if sql is None:
            if index == 0:
                _fail(path, case_id, "the first turn must have reference SQL")
            continue
        if not isinstance(sql, str) or not sql.strip():
            _fail(path, case_id, f"reference_sql[{index}] must be SQL or null")
        if ";" in sql:
            _fail(path, case_id, f"reference_sql[{index}] must be one statement without a semicolon")
        if not _TABLE.match(sql):
            _fail(path, case_id, f"reference_sql[{index}] must be a SELECT")
        validation = validate_sql(sql)
        if not validation.valid:
            _fail(
                path,
                case_id,
                f"reference_sql[{index}] is not inside the product contract: {validation.reason}",
            )
        columns = _projected_columns(sql) or []
        if compare == "ids" and columns != ["id"]:
            _fail(path, case_id, f"reference_sql[{index}] must project only id for compare ids")
        if compare == "count" and columns != ["count"]:
            _fail(
                path,
                case_id,
                f"reference_sql[{index}] must project only COUNT(*) AS count for compare count",
            )
    if "as_of" in case:
        try:
            date.fromisoformat(case["as_of"])
        except (TypeError, ValueError):
            _fail(path, case_id, "as_of must be an ISO date")
    if any(sql is None for sql in references) and "detail_check" not in case:
        _fail(path, case_id, "a null turn needs detail_check to say what replaces SQL")
    if "detail_check" in case and not any(sql is None for sql in references):
        _fail(path, case_id, "detail_check only applies to a null turn")


def _validate_expect(case: dict[str, Any], *, path: Path, case_id: str) -> None:
    expect = case.get("expect")
    if not isinstance(expect, dict):
        _fail(path, case_id, "expect must be a mapping")
    extra = set(expect) - {"refusal", "forbid_any"}
    if extra:
        _fail(path, case_id, f"expect has unread keys: {', '.join(sorted(extra))}")
    refusal = expect.get("refusal")
    if refusal not in EXPECTED_REFUSAL:
        _fail(path, case_id, f"expect.refusal must be one of {sorted(EXPECTED_REFUSAL)}")
    forbidden = expect.get("forbid_any")
    if not isinstance(forbidden, list) or not forbidden:
        _fail(path, case_id, "expect.forbid_any must be a nonempty list")
    if any(not isinstance(value, str) or not value.strip() for value in forbidden):
        _fail(path, case_id, "expect.forbid_any must contain nonempty strings")
    if len(set(forbidden)) != len(forbidden):
        _fail(path, case_id, "expect.forbid_any must not repeat a value")
    if refusal == "yes" and case["answerable"] != "no":
        _fail(path, case_id, "a refusal case must be answerable no")
    if refusal == "no" and case["answerable"] == "no":
        _fail(path, case_id, "expect.refusal no contradicts answerable no")


def _validate_case_shape(
    case: Any, *, file: DatasetFile
) -> dict[str, Any]:
    path = file.path
    if not isinstance(case, dict):
        _fail(path, None, "every case must be a mapping")
    case_id = case.get("id")
    if not isinstance(case_id, str) or _ID.fullmatch(case_id) is None:
        _fail(path, None, f"id must match {_ID.pattern}")
    extra = set(case) - BASE_KEYS
    if extra:
        _fail(path, case_id, f"has unread keys: {', '.join(sorted(extra))}")
    missing = REQUIRED_KEYS - set(case)
    if missing:
        _fail(path, case_id, f"is missing {', '.join(sorted(missing))}")

    if case["split"] not in SPLITS:
        _fail(path, case_id, f"split must be one of {sorted(SPLITS)}")
    if case["split"] != file.split:
        _fail(
            path,
            case_id,
            f"split must be {file.split!r} in {file.name}, not {case['split']!r}",
        )
    if case["need"] not in NEEDS:
        _fail(path, case_id, f"need must be one of {sorted(NEEDS)}")
    if case["style"] not in STYLES:
        _fail(path, case_id, f"style must be one of {sorted(STYLES)}")
    if case["answerable"] not in ANSWERABLE:
        _fail(path, case_id, f"answerable must be one of {sorted(ANSWERABLE)}")

    turns = case["turns"]
    if (
        not isinstance(turns, list)
        or not turns
        or any(not isinstance(turn, str) or not turn.strip() for turn in turns)
    ):
        _fail(path, case_id, "turns must be a nonempty list of nonempty strings")
    if any(turn != turn.strip() for turn in turns):
        _fail(path, case_id, "a turn must not have leading or trailing whitespace")
    if not isinstance(case["expected"], str) or not case["expected"].strip():
        _fail(path, case_id, "expected must be a nonempty string")
    for optional in ("note", "review"):
        if optional in case and (
            not isinstance(case[optional], str) or not case[optional].strip()
        ):
            _fail(path, case_id, f"{optional} must be a nonempty string")

    _validate_reference_sql(case, path=path, case_id=case_id)

    if case["need"] == "out_of_scope":
        if case["answerable"] != "no":
            _fail(path, case_id, "an out_of_scope case must be answerable no")
        if "expect" in case:
            _fail(path, case_id, "out_of_scope does not use expect")
    if case["need"] == "refusal":
        if "expect" not in case:
            _fail(path, case_id, "a refusal case needs an expect block")
    if case["need"] == "safety" and "expect" not in case:
        _fail(path, case_id, "a safety case needs an expect block")
    if "expect" in case:
        _validate_expect(case, path=path, case_id=case_id)
    elif case["need"] in {"refusal", "safety"}:
        _fail(path, case_id, "this case needs an expect block")

    if file.name == PARAPHRASES.name:
        if "paraphrase_of" not in case:
            _fail(path, case_id, "a paraphrase must name paraphrase_of")
        if not isinstance(case["paraphrase_of"], str) or not case["paraphrase_of"]:
            _fail(path, case_id, "paraphrase_of must be a case id")
    elif "paraphrase_of" in case:
        _fail(path, case_id, "paraphrase_of only belongs in paraphrases.yaml")

    return dict(case)


def _validate_paraphrases(
    cases: Sequence[dict[str, Any]], baseline: Sequence[dict[str, Any]]
) -> None:
    originals = {case["id"]: case for case in baseline}
    for case in cases:
        original = originals.get(case.get("paraphrase_of", ""))
        if original is None:
            _fail(
                PARAPHRASES.path,
                case["id"],
                f"paraphrase_of {case['paraphrase_of']!r} is not a baseline dev case",
            )
        if case["compare"] != original["compare"]:
            _fail(PARAPHRASES.path, case["id"], "a paraphrase must keep the original compare mode")
        if case["answerable"] != original["answerable"]:
            _fail(PARAPHRASES.path, case["id"], "a paraphrase must keep the original answerable value")
        if case["reference_sql"] != original["reference_sql"]:
            _fail(PARAPHRASES.path, case["id"], "a paraphrase must keep the original reference SQL")
        if len(case["turns"]) != len(original["turns"]):
            _fail(PARAPHRASES.path, case["id"], "a paraphrase must keep the original turn count")
        if case["turns"][0] == original["turns"][0]:
            _fail(PARAPHRASES.path, case["id"], "a paraphrase must reword the first turn")


def _read_cases(file: DatasetFile) -> list[dict[str, Any]]:
    path = file.path
    if not path.exists():
        raise DatasetError(f"the baseline dataset is missing: {path}")
    text = path.read_text(encoding="utf-8")
    _check_quoted_enums(path, text)
    payload = yaml.safe_load(text)
    if not isinstance(payload, list):
        raise DatasetError(f"{path.name}: the top level must be a list of cases")
    cases = [_validate_case_shape(case, file=file) for case in payload]
    for case in cases:
        case["dataset"] = file.name
    return cases


def load_cases() -> list[dict[str, Any]]:
    """Load, validate, and return every case in dataset-file order."""
    cases: list[dict[str, Any]] = []
    for file in DATASET_FILES:
        cases.extend(_read_cases(file))
    seen: set[str] = set()
    duplicates: set[str] = set()
    for case in cases:
        if case["id"] in seen:
            duplicates.add(case["id"])
        seen.add(case["id"])
    if duplicates:
        raise DatasetError(f"duplicate case ids: {', '.join(sorted(duplicates))}")
    baseline = [case for case in cases if case["dataset"] == BASELINE.name]
    paraphrases = [case for case in cases if case["dataset"] == PARAPHRASES.name]
    _validate_paraphrases(paraphrases, baseline)
    return cases


def cases_for_split(split: str) -> list[dict[str, Any]]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {sorted(SPLITS)}")
    return [case for case in load_cases() if case["split"] == split]


def scored_cases() -> list[dict[str, Any]]:
    """Cases whose first turn has reference SQL, for the Layer 1 diagnostic."""
    return [case for case in load_cases() if case["reference_sql"] and case["reference_sql"][0]]


def file_counts() -> dict[str, int]:
    """Case count per dataset file, without re-validating the file content twice."""
    counts: dict[str, int] = {}
    for file in DATASET_FILES:
        counts[file.name] = len(_read_cases(file))
    return counts


def identities() -> list[dict[str, Any]]:
    """Name, path, and case count per file, for a run manifest."""
    identities: list[dict[str, Any]] = []
    for file in DATASET_FILES:
        cases = _read_cases(file)
        identities.append(
            {
                "name": file.name,
                "path": file.path.relative_to(EVALS_ROOT.parent).as_posix(),
                "split": file.split,
                "record_count": len(cases),
            }
        )
    return identities
