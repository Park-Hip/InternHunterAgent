"""Deterministic three-tier grading for persisted evaluation runs.

The grader consumes recorded evidence only. It never creates an agent, calls a model, or
changes the fixture database. Structural checks win over textual checks, and textual checks
win over the optional judge tier.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from evals.scenarios import load_scenarios, repeat_count, scenario_category
from src.agents.runtime.prompts import (
    load_behavior_glossary,
    load_prompt_version,
    load_schema_context,
)
from src.core.config import settings

PASS = "PASS"
FAIL = "FAIL"
INFRA = "INFRA"
UNRUN = "UNRUN"
NOT_EVALUATED = "NOT_EVALUATED"
EXCLUDED_FROM_DENOMINATOR = frozenset({INFRA, UNRUN})
BEHAVIOR_GLOSSARY = load_behavior_glossary()
BEHAVIOR_GLOSSARY_ANCHORS = settings.prompts_yaml.get("behavior_glossary_anchors", {})
EVALUATION_ANCHORS = settings.prompts_yaml.get("evaluation_anchors", {})


@dataclass(frozen=True)
class Evidence:
    """The seam evidence needed by the deterministic grader for one turn."""

    answer: str | None
    tools_called: list[str] | None = None
    sql_text: str | None = None
    execution_accuracy: dict[str, Any] | None = None
    judge_scores: dict[str, Any] | None = None
    returned_rows: list[dict[str, Any]] | None = None
    capture_prompt_version: str | None = None

    @classmethod
    def from_turn(
        cls,
        turn: dict[str, Any],
        execution_accuracy: dict[str, Any] | None = None,
        capture_prompt_version: str | None = None,
    ) -> "Evidence":
        seams = turn.get("seams") or {}
        return cls(
            answer=seams.get("answer"),
            tools_called=seams.get("tools_called"),
            sql_text=seams.get("sql_text"),
            execution_accuracy=execution_accuracy or turn.get("execution_accuracy"),
            judge_scores=turn.get("judge_scores"),
            returned_rows=(
                seams.get("returned_rows")
                or turn.get("returned_rows")
                or (execution_accuracy or turn.get("execution_accuracy") or {}).get("generated_rows")
            ),
            capture_prompt_version=capture_prompt_version,
        )


@dataclass(frozen=True)
class TextRule:
    """Case-insensitive answer constraints expressed as substance, not exact phrases."""

    required_any: tuple[tuple[str, ...], ...] = ()
    forbidden_any: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioRule:
    """The highest-tier assertions for one frozen scenario."""

    # An empty tuple is a real expectation, not an absent one: the scenario
    # requires that no tool ran. Every value comes from the frozen registry.
    expected_tools: tuple[str, ...] = ()
    expected_answer_count: int | None = None
    forbid_single_salary_winner: bool = False
    literal: TextRule | None = None
    semantic: TextRule | None = None
    judge_metric: str | None = None
    judge_threshold: float = 0.5
    require_vietnamese: bool = False

    @property
    def text(self) -> TextRule | None:
        """Compatibility view for callers that inspect semantic assertion terms."""
        return self.semantic


@dataclass
class Check:
    name: str
    passed: bool | None
    detail: str
    tier: str
    outcome: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is None:
            self.outcome = PASS if self.passed is True else FAIL if self.passed is False else INFRA

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "tier": self.tier,
            "outcome": self.outcome,
        }


@dataclass
class Grade:
    scenario_id: str
    status: str
    tier: str
    checks: list[Check] = field(default_factory=list)
    first_failing_seam: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "tier": self.tier,
            "checks": [check.to_dict() for check in self.checks],
            "first_failing_seam": self.first_failing_seam,
        }


def _text(answer: str | None) -> str:
    return (answer or "").casefold()


def _required_check(answer: str, groups: tuple[tuple[str, ...], ...], tier: str) -> list[Check]:
    checks: list[Check] = []
    for index, group in enumerate(groups, start=1):
        matched = next((term for term in group if term.casefold() in answer), None)
        checks.append(
            Check(
                name=f"required_substance_{index}",
                passed=matched is not None,
                detail=(f"matched {matched!r}" if matched else f"none of {group!r} present"),
                tier=tier,
            )
        )
    return checks


def _text_checks(answer: str | None, rule: TextRule, tier: str) -> list[Check]:
    normalized = _text(answer)
    checks = _required_check(normalized, rule.required_any, tier)
    checks.extend(
        Check(
            name="forbidden_phrase_absent",
            passed=term.casefold() not in normalized,
            detail=f"forbidden phrase {term!r} {'absent' if term.casefold() not in normalized else 'present'}",
            tier=tier,
        )
        for term in rule.forbidden_any
    )
    checks.extend(
        Check(
            name="forbidden_pattern_absent",
            passed=re.search(pattern, normalized, flags=re.IGNORECASE) is None,
            detail=f"forbidden pattern {pattern!r} {'absent' if re.search(pattern, normalized, flags=re.IGNORECASE) is None else 'present'}",
            tier=tier,
        )
        for pattern in rule.forbidden_patterns
    )
    return checks


_NUMBER_WORDS = {
    0: ("zero", "không"),
    1: ("one", "một", "mot"),
    2: ("two", "hai"),
    3: ("three", "ba"),
    4: ("four", "bốn", "bon"),
    5: ("five", "năm", "nam"),
    6: ("six", "sáu", "sau"),
    7: ("seven", "bảy", "bay"),
    8: ("eight", "tám", "tam"),
    9: ("nine", "chín", "chin"),
    10: ("ten", "mười", "muoi"),
    11: ("eleven", "mười một", "muoi mot"),
    12: ("twelve", "mười hai", "muoi hai"),
}


def _answer_count(answer: str | None, expected: int) -> bool:
    normalized = _text(answer)
    number = str(expected)
    return bool(
        re.search(rf"\b{re.escape(number)}\b", normalized)
        or any(
            re.search(rf"(?<!\w){re.escape(word)}(?!\w)", normalized)
            for word in _NUMBER_WORDS.get(expected, ())
        )
    )


_ENGLISH_PROSE_WORDS = frozenset(
    "a an and are as at be but by can does for from has have how i in is it job jobs my not of on or that the these this to was were what which with you your".split()
)


def _row_values(rows: list[dict[str, Any]]) -> list[str]:
    values = [str(value) for row in rows for value in row.values() if value is not None]
    return sorted((value for value in values if value), key=len, reverse=True)


@lru_cache(maxsize=1)
def _schema_identifiers() -> tuple[str, ...]:
    """Every table and column name the model is shown, read from the prompt it is shown in.

    The list is derived from ``prompts.schema_context`` rather than restated here, so it
    cannot drift from the schema the agent actually sees.
    """
    context = load_schema_context()
    identifiers = set(re.findall(r"^Table:\s*(\w+)", context, flags=re.MULTILINE))
    identifiers.update(re.findall(r"^-\s+(\w+)\s+\(", context, flags=re.MULTILINE))
    if not identifiers:
        raise ValueError("No table or column identifiers found in prompts.schema_context")
    return tuple(sorted(identifiers))


def _strip_schema_identifiers(text: str) -> str:
    """Remove whole-token schema identifiers, leaving surrounding prose intact.

    ``is_salary_negotiable`` and ``created_on`` are not English prose, but the ASCII token
    probe below splits them on the underscore and finds ``is`` and ``on``. Removing the
    identifier first is what keeps the language check about language.
    """
    for identifier in _schema_identifiers():
        text = re.sub(
            rf"(?<![a-z0-9_]){re.escape(identifier)}(?![a-z0-9_])", " ", text
        )
    return text


def _answer_language_pure(answer: str | None, rows: list[dict[str, Any]] | None) -> bool | None:
    """Check agent prose while allowing canonical and source row values verbatim."""
    if not rows:
        return None
    remaining = _text(answer)
    for value in _row_values(rows):
        remaining = remaining.replace(value.casefold(), " ")
    remaining = _strip_schema_identifiers(remaining)
    # Accented Vietnamese letters are outside this ASCII token probe. Requiring two
    # characters avoids treating fragments such as ``t`` and ``i`` as English words.
    words = set(re.findall(r"[a-z]{2,}", remaining))
    return not bool(words & _ENGLISH_PROSE_WORDS)


# Emoji and dingbat blocks only. Arrows, bullets, the em dash and the dong sign are left out:
# they are punctuation the answers legitimately use, and the prompt rule is about decoration.
_DECORATIVE_SYMBOL_PATTERN = re.compile(
    "["
    "\U0001f000-\U0001faff"  # emoticons, pictographs, transport, symbols extended-A
    "\u2600-\u27bf"  # miscellaneous symbols and dingbats
    "\u2b00-\u2bff"  # miscellaneous symbols and arrows
    "\ufe0f"  # variation selector-16, the emoji presentation marker
    "\u20e3"  # combining enclosing keycap
    "]"
)


def _decorative_symbols(answer: str | None) -> list[str]:
    """Report every emoji or decorative symbol in an answer, in order of appearance."""
    return _DECORATIVE_SYMBOL_PATTERN.findall(answer or "")


def _codepoints(symbols: list[str]) -> list[str]:
    """Name the offending symbols as codepoints.

    A grade lands in a JSON artifact that a person reads. Some of these characters are
    invisible on their own - a variation selector renders as nothing - so the detail
    string names them rather than reprinting them.
    """
    return [f"U+{ord(symbol):04X}" for symbol in symbols]


@lru_cache(maxsize=1)
def _sanctioned_identifier_text() -> str:
    """Every phrasing the project tells the agent to say, as one casefolded haystack."""
    return " ".join(
        [*BEHAVIOR_GLOSSARY.values()]
        + [anchor for anchors in BEHAVIOR_GLOSSARY_ANCHORS.values() for anchor in anchors]
        + [anchor for anchors in EVALUATION_ANCHORS.values() for anchor in anchors]
    ).casefold()


@lru_cache(maxsize=1)
def _leakable_identifiers() -> tuple[str, ...]:
    """The schema identifiers whose presence in an answer can only be leakage.

    Two exclusions, both derived rather than listed, so this cannot drift from the schema
    or from the behavior contract.

    Only compound identifiers qualify. ``id``, ``title``, ``company``, ``role``,
    ``location`` and ``description`` are ordinary words that appear in answers for honest
    reasons - the SQL rules require ``id`` to be selected first so postings can be
    referenced later - so keying on them would manufacture the same false signal this
    check exists to remove.

    An identifier the behavior glossary itself quotes is excluded too. ``CREATED_ON_CAVEAT``
    names ``created_on`` to the user on purpose, and ``HON-CREATED-ON-1`` requires that
    anchor to be present, so forbidding it here would require and forbid the same word in
    one turn.
    """
    sanctioned = _sanctioned_identifier_text()
    return tuple(
        name
        for name in _schema_identifiers()
        if "_" in name and name not in sanctioned
    )


def _leaked_identifiers(answer: str | None) -> list[str]:
    """Report every schema identifier the answer quotes to the user."""
    normalized = _text(answer)
    return [
        identifier
        for identifier in _leakable_identifiers()
        if re.search(rf"(?<![a-z0-9_]){re.escape(identifier)}(?![a-z0-9_])", normalized)
    ]


def _answer_style_checks(evidence: Evidence) -> list[Check]:
    """Cross-scenario answer-style assertions, gated on the capture's prompt version.

    Both rules are properties of the prompt that produced the answer, so a capture frozen
    before the rule existed must not be regraded against it. This is the
    ``vietnamese_agent_prose`` precedent in ``_prompt_is_current``.
    """
    if not _prompt_is_current(evidence):
        return []
    symbols = _decorative_symbols(evidence.answer)
    identifiers = _leaked_identifiers(evidence.answer)
    return [
        Check(
            "no_decorative_symbols",
            not symbols,
            "answer contains no emoji or decorative symbols"
            if not symbols
            else f"answer contains decorative symbols: {_codepoints(symbols)}",
            "structural",
        ),
        Check(
            "no_schema_identifier_leak",
            not identifiers,
            "answer quotes no schema identifier"
            if not identifiers
            else f"answer quotes schema identifiers: {identifiers!r}",
            "structural",
        ),
    ]


def _structural_checks(rule: ScenarioRule, evidence: Evidence) -> list[Check]:
    checks: list[Check] = []
    if evidence.tools_called is None:
        checks.append(Check("tools_recorded", None, "tools_called is absent from the replay record", "structural"))
    elif not rule.expected_tools:
        passed = len(evidence.tools_called) == 0
        checks.append(
            Check(
                "no_tool_called",
                passed,
                "no tool called" if passed else f"unexpected tools: {evidence.tools_called!r}",
                "structural",
            )
        )
    else:
        passed = all(tool in evidence.tools_called for tool in rule.expected_tools)
        checks.append(
            Check(
                "required_tool_called",
                passed,
                f"required {rule.expected_tools!r}; observed {evidence.tools_called!r}",
                "structural",
            )
        )
        accuracy = evidence.execution_accuracy
        if accuracy is None:
            checks.append(Check("execution_accuracy", None, "T0025.5 result is absent", "structural"))
        else:
            accuracy_status = accuracy.get("status")
            if accuracy_status in {PASS, "EXEMPT"}:
                checks.append(Check("execution_accuracy", True, f"execution accuracy {accuracy_status}", "structural"))
            elif accuracy_status in {INFRA, UNRUN}:
                checks.append(Check("execution_accuracy", None, f"execution accuracy is {accuracy_status}", "structural"))
            else:
                checks.append(Check("execution_accuracy", False, f"execution accuracy is {accuracy_status}", "structural"))

    if rule.expected_answer_count is not None:
        checks.append(
            Check(
                "answer_count",
                _answer_count(evidence.answer, rule.expected_answer_count),
                f"expected answer to contain count {rule.expected_answer_count}",
                "structural",
            )
        )

    return checks


def _judge_checks(rule: ScenarioRule, evidence: Evidence) -> list[Check]:
    if rule.judge_metric is None:
        return []
    scores = evidence.judge_scores or {}
    value = scores.get(rule.judge_metric)
    if isinstance(value, dict):
        value = value.get("score")
    if value is None:
        return [Check("judge_metric", None, f"missing judge metric {rule.judge_metric!r}", "judge")]
    try:
        score = float(value)
    except (TypeError, ValueError):
        return [Check("judge_metric", None, f"invalid judge metric {value!r}", "judge")]
    return [
        Check(
            "judge_metric",
            score >= rule.judge_threshold,
            f"{rule.judge_metric}={score:.3f}, threshold={rule.judge_threshold:.3f}",
            "judge",
        )
    ]


@lru_cache(maxsize=1)
def _registry_index() -> dict[str, dict[str, Any]]:
    """Index the frozen registry once; grading calls this per turn."""
    return {scenario["id"]: scenario for scenario in load_scenarios()}


def _term(scenario_id: str, term: str | dict[str, str]) -> tuple[str, ...]:
    """Resolve one glossary reference to its stable paraphrase anchors.

    The canonical sentence is model-facing and is intentionally too long for substring
    matching. Anchors preserve the live prompt vocabulary while accepting faithful paraphrases.
    """
    if isinstance(term, str):
        return (term,)
    if "lexicon" in term:
        lexicon = term["lexicon"]
        if not isinstance(lexicon, list) or not lexicon or not all(isinstance(item, str) for item in lexicon):
            raise ValueError(f"Scenario {scenario_id} has an invalid Vietnamese lexicon")
        return tuple(lexicon)
    name = term["glossary"]
    if name in EVALUATION_ANCHORS:
        anchors = EVALUATION_ANCHORS[name]
        if not isinstance(anchors, list) or not anchors or not all(isinstance(anchor, str) for anchor in anchors):
            raise ValueError(f"Evaluation anchor {name!r} is invalid")
        return tuple(anchors)
    if name not in BEHAVIOR_GLOSSARY:
        raise ValueError(f"Scenario {scenario_id} references unknown glossary term: {name!r}")
    anchors = BEHAVIOR_GLOSSARY_ANCHORS.get(name)
    if not isinstance(anchors, list) or not anchors or not all(isinstance(anchor, str) for anchor in anchors):
        raise ValueError(f"Glossary term {name!r} has no valid anchor terms")
    canonical = BEHAVIOR_GLOSSARY[name].casefold()
    if any(anchor.casefold() not in canonical for anchor in anchors):
        raise ValueError(f"Glossary anchors for {name!r} must be substrings of its canonical sentence")
    return tuple(anchors)


def _text_rule(scenario_id: str, assertion: dict[str, Any]) -> TextRule | None:
    required = tuple(
        tuple(anchor for term in group for anchor in _term(scenario_id, term))
        for group in assertion.get("required_any", ())
    )
    forbidden = tuple(
        anchor for term in assertion.get("forbidden_any", ()) for anchor in _term(scenario_id, term)
    )
    patterns = tuple(assertion.get("forbidden_patterns", ()))
    if not (required or forbidden or patterns):
        return None
    return TextRule(
        required_any=required,
        forbidden_any=forbidden,
        forbidden_patterns=patterns,
    )


def _rule_for(scenario_id: str) -> ScenarioRule:
    """Read one scenario's assertions out of the frozen registry.

    Every field here is registry data (D-041). The grader owns how a rule is
    *applied* - the three tiers, the four outcomes, and the two regexes below that
    are logic rather than data - and owns none of what a given scenario expects.
    """
    scenario = _registry_index().get(scenario_id)
    if scenario is None:
        raise ValueError(f"Unknown scenario id: {scenario_id}")
    grading = scenario.get("grading") or {}
    assertions = grading.get("assertions") or []
    literal = next((item for item in assertions if item["type"] == "literal"), {})
    structural = next((item for item in assertions if item["type"] == "structural"), {})
    semantic = next((item for item in assertions if item["type"] == "semantic"), {})
    return ScenarioRule(
        expected_tools=tuple(scenario["expected_tools"]),
        expected_answer_count=literal.get("expected_answer_count"),
        forbid_single_salary_winner=bool(semantic.get("forbid_single_salary_winner", False)),
        literal=_text_rule(scenario_id, literal),
        semantic=_text_rule(scenario_id, semantic),
        require_vietnamese=bool(structural.get("require_vietnamese", scenario.get("language") == "vi")),
    )


def _prompt_is_current(evidence: Evidence) -> bool:
    """Report whether a capture was taken under the prompt now in config/prompts.yaml.

    Answer language is a property of the prompt that produced it, so a capture frozen before
    the Vietnamese output rule would read as a behaviour failure when it is only a prompt
    change. T0035.1 stamps every capture with its prompt version precisely so a baseline is
    never read across one. An unstamped evidence object (a constructed holdout case, or a
    live turn) is treated as current, so this narrows nothing but stale replays.
    """
    stamped = evidence.capture_prompt_version
    return stamped is None or stamped == load_prompt_version()


def _semantic_checks(rule: ScenarioRule) -> list[Check]:
    if rule.semantic is None and not rule.forbid_single_salary_winner:
        return []
    return [
        Check(
            "semantic_behavior",
            None,
            "semantic assertion retained for the calibrated judge; not evaluated in Phase 1",
            "semantic",
            NOT_EVALUATED,
        )
    ]


def _first_failing_seam(checks: list[Check]) -> str | None:
    return next((check.tier for check in checks if check.outcome == FAIL), None)


def grade_evidence(scenario_id: str, evidence: Evidence) -> Grade:
    """Grade independently evaluated literal and structural assertions for one turn."""
    rule = _rule_for(scenario_id)
    if not evidence.answer:
        return Grade(
            scenario_id,
            INFRA,
            "structural",
            [Check("answer_present", None, "completed turn has no answer", "structural")],
        )

    structural = _structural_checks(rule, evidence)
    structural.extend(_answer_style_checks(evidence))
    if rule.require_vietnamese and evidence.returned_rows is not None and _prompt_is_current(evidence):
        purity = _answer_language_pure(evidence.answer, evidence.returned_rows)
        structural.append(
            Check(
                "vietnamese_agent_prose",
                purity,
                "agent prose excludes English words outside returned row values"
                if purity is not None
                else "returned rows are empty; language purity was not measured",
                "structural",
                NOT_EVALUATED if purity is None else None,
            )
        )
    literal = _text_checks(evidence.answer, rule.literal, "literal") if rule.literal else []
    semantic = _semantic_checks(rule)
    judge = _judge_checks(rule, evidence)
    checks = structural + literal + semantic + judge
    first_failing_seam = _first_failing_seam(checks)
    if first_failing_seam:
        return Grade(scenario_id, FAIL, first_failing_seam, checks, first_failing_seam)
    infra_seam = next((check.tier for check in checks if check.outcome == INFRA), None)
    if infra_seam:
        return Grade(scenario_id, INFRA, infra_seam, checks)
    tier = "judge" if judge else "literal" if literal else "structural"
    return Grade(scenario_id, PASS, tier, checks)


def _execution_for_turn(
    execution_accuracy: dict[str, Any] | None,
    scenario_id: str,
    repeat_number: int,
    turn_number: int,
) -> dict[str, Any] | None:
    if not execution_accuracy:
        return None
    repeats = execution_accuracy.get("scenarios", {}).get(scenario_id, [])
    for repeat in repeats:
        if repeat.get("repeat") == repeat_number:
            turns = repeat.get("turns", [])
            if 0 < turn_number <= len(turns):
                return turns[turn_number - 1]
    return None


def summarize(grades: list[Grade]) -> dict[str, Any]:
    by_class: dict[str, list[Grade]] = defaultdict(list)
    for grade in grades:
        by_class[scenario_category(grade.scenario_id)].append(grade)

    def class_summary(items: list[Grade]) -> dict[str, Any]:
        counts = Counter(item.status for item in items)
        measured = len(items) - sum(counts.get(status, 0) for status in EXCLUDED_FROM_DENOMINATOR)
        return {
            "counts": dict(sorted(counts.items())),
            "measured": measured,
            "pass_rate": counts.get(PASS, 0) / measured if measured else None,
        }

    return {
        "total": len(grades),
        "counts": dict(sorted(Counter(grade.status for grade in grades).items())),
        "empty_answer_count": sum(
            any(check.name == "answer_present" and check.passed is None for check in grade.checks)
            for grade in grades
        ),
        "by_class": {name: class_summary(items) for name, items in sorted(by_class.items())},
    }


def _scenario_outcome(
    scenario: dict[str, Any], turn_grades: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate every required repeat without hiding the individual turn verdicts."""
    by_repeat: dict[int, list[str]] = defaultdict(list)
    for grade in turn_grades:
        if "repeat" in grade:
            by_repeat[int(grade["repeat"])].append(grade["status"])

    repeats: list[dict[str, Any]] = []
    for number in range(1, repeat_count(scenario) + 1):
        statuses = by_repeat.get(number, [])
        if not statuses:
            status = UNRUN
        elif FAIL in statuses:
            status = FAIL
        elif INFRA in statuses:
            status = INFRA
        elif UNRUN in statuses:
            status = UNRUN
        else:
            status = PASS
        repeats.append({"repeat": number, "status": status})

    statuses = [repeat["status"] for repeat in repeats]
    status = (
        FAIL if FAIL in statuses else INFRA if INFRA in statuses else UNRUN if UNRUN in statuses else PASS
    )
    return {"status": status, "repeats": repeats}


def grade_persisted_run(
    run: dict[str, Any],
    execution_accuracy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grade a T0025.3 run artifact and optional T0025.5 result artifact."""
    known_ids = {scenario["id"] for scenario in load_scenarios()}
    capture_prompt_version = (run.get("manifest") or {}).get("prompt_version")
    grades: list[Grade] = []
    results: dict[str, list[dict[str, Any]]] = {}
    scenario_outcomes: dict[str, dict[str, Any]] = {}
    for scenario_id, scenario_record in run.get("scenarios", {}).items():
        if scenario_id not in known_ids:
            grade = Grade(scenario_id, INFRA, "structural", [Check("scenario_known", False, "unknown scenario id", "structural")])
            grades.append(grade)
            results[scenario_id] = [grade.to_dict()]
            scenario_outcomes[scenario_id] = {"status": INFRA, "repeats": []}
            continue
        scenario_grades: list[dict[str, Any]] = []
        if scenario_record.get("status") == UNRUN and not scenario_record.get("repeats"):
            grade = Grade(
                scenario_id,
                UNRUN,
                "structural",
                [Check("scenario_run", None, "scenario was not collected", "structural")],
            )
            grades.append(grade)
            scenario_grades.append(grade.to_dict())
            results[scenario_id] = scenario_grades
            scenario_outcomes[scenario_id] = {"status": UNRUN, "repeats": []}
            continue
        for repeat in scenario_record.get("repeats", []):
            repeat_number = int(repeat.get("repeat", 0))
            if repeat.get("status") == INFRA and not repeat.get("turns"):
                grade = Grade(
                    scenario_id,
                    INFRA,
                    "structural",
                    [Check("repeat_run", None, "repeat ended as infrastructure failure", "structural")],
                )
                grades.append(grade)
                scenario_grades.append({"repeat": repeat_number, **grade.to_dict()})
                continue
            for turn_number, turn in enumerate(repeat.get("turns", []), start=1):
                execution = _execution_for_turn(execution_accuracy, scenario_id, repeat_number, turn_number)
                grade = grade_evidence(
                    scenario_id,
                    Evidence.from_turn(turn, execution, capture_prompt_version),
                )
                grades.append(grade)
                scenario_grades.append({"repeat": repeat_number, "turn": turn_number, **grade.to_dict()})
        results[scenario_id] = scenario_grades
        scenario_outcomes[scenario_id] = _scenario_outcome(
            _registry_index()[scenario_id], scenario_grades
        )

    return {
        "run_id": run.get("manifest", {}).get("run_id"),
        "scenarios": results,
        "scenario_outcomes": scenario_outcomes,
        "summary": summarize(grades),
    }


def grade_observed_answers(path: Path) -> dict[str, Any]:
    """Replay the answer-only 2026-07-14 artifact without making any model calls."""
    observed = json.loads(path.read_text(encoding="utf-8"))
    known_ids = {scenario["id"] for scenario in load_scenarios()}
    grades: list[Grade] = []
    results: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, answers in observed.items():
        if scenario_id not in known_ids:
            continue
        scenario_results = []
        for index, answer in enumerate(answers, start=1):
            if "couldn't produce an answer" in _text(answer):
                grade = Grade(scenario_id, INFRA, "structural", [Check("legacy_answer", None, "recorded fallback has no behavior to grade", "structural")])
            else:
                grade = grade_evidence(scenario_id, Evidence(answer=answer))
            grades.append(grade)
            scenario_results.append({"repeat": index, **grade.to_dict()})
        results[scenario_id] = scenario_results
    return {"scenarios": results, "summary": summarize(grades)}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade recorded evaluation evidence without a model call.")
    parser.add_argument("--run", type=Path, help="T0025.3 persisted run JSON")
    parser.add_argument("--observed", type=Path, help="Answer-only observed artifact")
    parser.add_argument("--execution-accuracy", type=Path)
    args = parser.parse_args()
    if bool(args.run) == bool(args.observed):
        parser.error("choose exactly one of --run or --observed")
    if args.run:
        execution = _load_json(args.execution_accuracy) if args.execution_accuracy else None
        report = grade_persisted_run(_load_json(args.run), execution)
    else:
        report = grade_observed_answers(args.observed)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
