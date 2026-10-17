"""The reviewed SQL statements and verdicts behind ADR-0060's SQL-path table.

This is the retained SQL half of the Stage 4 probe. The typed half went with the
typed core; what remains is the 27 reviewed SQL statements, the reviewer-written
verdict function on each one, the pinned fixture, the seven-row alternate seed,
and the guard. It is the same artifact the credential-free gate grew from - the
gate pins the reviewed cases, this script reproduces the measured table.

Every probe carries a **reviewer-written verdict function**. The script never
decides on its own whether an answer is right: it runs the SQL, hands the
observation to that function, and records what it says. A probe whose truth is
"this must not be answered" grades a data answer as a false success, which is the
class the decision turns on.

Each probe runs twice: once on the pinned 24-row fixture, and once with seven
extra rows carrying the conditions the fixture cannot express (a null link, a
null technology list, a lower-bound-only salary, two exact ties, a
prefix-colliding technology name, and an unrecorded city). A probe that is right
on the fixture and wrong once NULLs and ties exist is a coincidental match, and
the report names the ones that are.

Not measured, and recorded as unavailable rather than estimated: model token
cost and end-to-end latency, because this machine has no provider credential and
no model was called. Each candidate SQL is hand-authored as the plausible model
output for its question and is reviewed, not generated.

Run against a live fixture (no agent role is needed; every statement runs through
the guard and the fixture owner):

    docker compose up -d postgres
    uv run python -m evals.fixtures.loader
    uv run python scripts/v0_sql_path_probe.py
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.env import bind_fixture_environment  # noqa: E402

bind_fixture_environment()

from sqlalchemy import create_engine, text  # noqa: E402

from src.services.query.sql_validator import validate_sql  # noqa: E402

# ---------------------------------------------------------------------------
# The alternate seed: the conditions the engineered fixture cannot express
# ---------------------------------------------------------------------------

EDGE_ROWS = [
    ("v0-probe-null-link", None, "Data Analyst", "Hanoi", "SQL", None, None, None, "false", "false"),
    ("v0-probe-null-stack", "https://example.invalid/no-stack", "AI Engineer", "Hanoi", None, None, None, None, "false", "false"),
    ("v0-probe-floor-only", "https://example.invalid/floor", "Data Scientist", "Hanoi", "SQL", 9000000, None, "VND", "false", "false"),
    ("v0-probe-tie-a", "https://example.invalid/tie-a", "Data Engineer", "Hanoi", "SQL", 2500, 3000, "USD", "false", "false"),
    ("v0-probe-tie-b", "https://example.invalid/tie-b", "Data Engineer", "Da Nang", "SQL", 2500, 3000, "USD", "false", "false"),
    # a technology name that is a prefix of a real one, and a city the data never recorded
    ("v0-probe-substring", "https://example.invalid/sub", "AI Engineer", "Hanoi", "Pythonic, Sparkly", None, None, None, "false", "false"),
    ("v0-probe-null-city", "https://example.invalid/nullcity", "Other", None, "SQL", None, None, None, "false", "false"),
]

EDGE_INSERT = """
INSERT INTO clean_jobs
  (source, external_id, source_url, title, company, role, description, tech_stack, job_level,
   location, posted_date, listing_expires_on, created_on, is_internship, salary_min, salary_max,
   salary_currency, is_salary_negotiable)
VALUES
  ('vietnamworks', :id, :url, 'Probe row', 'Probe Co', :role, 'Probe text.', :stack,
   'Experienced (non-manager)', :location, NULL, NULL, DATE '2026-06-01', :intern,
   :smin, :smax, :currency, :negotiable)
"""


# ---------------------------------------------------------------------------
# Verdict vocabulary
# ---------------------------------------------------------------------------

CORRECT = "correct"
FALSE_SUCCESS = "false-success"
REJECTED_CORRECT = "rejected-correct"
REJECTED_LOST = "rejected-lost"
RAISED = "raised"

Check = Callable[[dict[str, Any]], str]


def _is_answer(observation: dict[str, Any]) -> bool:
    return observation.get("verdict") == "answered"


def _scalar(observation: dict[str, Any], key: str) -> Any:
    return observation.get(key)


def _count_is(value: Any) -> Check:
    def check(observation: dict[str, Any]) -> str:
        if observation.get("verdict") == "answered" and _scalar(observation, "count") == value:
            return CORRECT
        if observation.get("verdict") == "answered":
            return FALSE_SUCCESS
        if observation.get("verdict") == "rejected":
            return REJECTED_LOST
        return observation.get("verdict", "unknown")

    return check


def _no_single_figure(observation: dict[str, Any]) -> str:
    """The truth for a salary question spanning two currencies: no one number."""
    if observation.get("verdict") != "answered":
        return observation.get("verdict", "unknown")
    aggregate = observation.get("aggregate")
    if aggregate and len([item for item, value in aggregate.items() if value is not None]) >= 1:
        if observation.get("count", 0) > 1 or "(not disclosed)" in aggregate:
            return CORRECT
    return FALSE_SUCCESS


def _share_is(denominator: Any, numerator: Any) -> Check:
    def check(observation: dict[str, Any]) -> str:
        if observation.get("verdict") != "answered":
            return observation.get("verdict", "unknown")
        if _scalar(observation, "denominator") == denominator and _scalar(observation, "numerator") == numerator:
            return CORRECT
        return FALSE_SUCCESS

    return check


def _rows_are(value: Any) -> Check:
    def check(observation: dict[str, Any]) -> str:
        if observation.get("verdict") == "answered":
            seen = observation.get("count", observation.get("rows"))
            return CORRECT if seen == value else FALSE_SUCCESS
        if observation.get("verdict") == "rejected":
            return REJECTED_LOST
        return observation.get("verdict", "unknown")

    return check


def _must_not_answer_with_a_number(observation: dict[str, Any]) -> str:
    """A question whose correct answer is a refusal, an error, or a clause."""
    if observation.get("verdict") == "rejected":
        return REJECTED_CORRECT
    if observation.get("verdict") == "answered":
        return FALSE_SUCCESS
    return RAISED if observation.get("verdict") == "error" else observation.get("verdict", "unknown")


def _accepted_is_a_coverage_gain(observation: dict[str, Any]) -> str:
    """A novel question the typed plan could not express: an answer is a gain here."""
    if observation.get("verdict") == "answered":
        return CORRECT
    if observation.get("verdict") == "rejected":
        return REJECTED_LOST
    return observation.get("verdict", "unknown")


def _retrieved_payload_is_data(observation: dict[str, Any]) -> str:
    """Retrieving the injected text is correct; obeying it is not this script's job."""
    return CORRECT if observation.get("verdict") == "answered" else observation.get("verdict", "unknown")


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


@dataclass
class Probe:
    id: str
    klass: str
    question: str
    intended: str
    candidate_sql: str
    check: Check
    note: str = ""


PROBES: list[Probe] = [
    # -- the reviewed v0 questions: the typed core's own coverage -----------
    Probe(
        "R01-list-role-city", "reviewed", "Có tin tuyển dụng AI Engineer nào ở Hà Nội không?",
        "3 postings: ids 1, 2 and 5.",
        "SELECT id FROM clean_jobs WHERE role ILIKE '%AI Engineer%' AND location ILIKE '%Hanoi%' ORDER BY id",
        _rows_are(3),
    ),
    Probe(
        "R02-count-corpus", "reviewed", "Có bao nhiêu tin tuyển dụng trong dữ liệu?",
        "24 postings.",
        "SELECT count(*) AS count FROM clean_jobs",
        _count_is(24),
    ),
    Probe(
        "R03-group-city", "reviewed", "Ở mỗi thành phố có bao nhiêu tin tuyển dụng?",
        "Hanoi 11, Ho Chi Minh City 9, Da Nang 4, total 24.",
        "SELECT location, count(*) AS count FROM clean_jobs GROUP BY location ORDER BY count DESC",
        lambda o: CORRECT
        if o.get("groups") == {"Hanoi": 11, "Ho Chi Minh City": 9, "Da Nang": 4}
        else (FALSE_SUCCESS if _is_answer(o) else o.get("verdict", "unknown")),
    ),
    Probe(
        "R04-share-python", "reviewed", "Bao nhiêu phần trăm tin AI Engineer có ghi nhận Python?",
        "5 of 5 AI Engineer postings, 0 excluded.",
        "SELECT count(*) AS denominator, count(*) FILTER (WHERE tech_stack ILIKE '%Python%') AS numerator "
        "FROM clean_jobs WHERE role ILIKE '%AI Engineer%'",
        _share_is(5, 5),
        note="The denominator is the whole role, not the rows that happen to have a stack.",
    ),
    Probe(
        "R05-salary-by-currency", "reviewed", "Mức lương trung bình cho Data Scientist là bao nhiêu?",
        "No single figure. USD 2500 over 1 row, VND 23333333.3 over 3 rows, 1 row excluded.",
        "SELECT avg(salary_min) AS count FROM clean_jobs WHERE role ILIKE '%Data Scientist%'",
        _no_single_figure,
        note="The one-currency number this returns is the number the contract forbids.",
    ),
    Probe(
        "R06-top5-usd", "reviewed", "5 tin có mức lương tối thiểu cao nhất, tính bằng USD?",
        "ids 1, 6, 14, 3, 10 out of 6 USD postings.",
        "SELECT id FROM clean_jobs WHERE salary_currency = 'USD' ORDER BY salary_min DESC LIMIT 5",
        _rows_are(5),
    ),
    Probe(
        "R07-compare-python-city", "reviewed", "So sánh số tin có Python ở Hà Nội và ở TP.HCM.",
        "7 in Hanoi, 3 in Ho Chi Minh City.",
        "SELECT count(*) AS count FROM clean_jobs WHERE tech_stack ILIKE '%Python%' AND location ILIKE '%Hanoi%'",
        _count_is(7),
    ),
    # -- novel compositions the typed language cannot express ----------------
    Probe(
        "N01-median-by-level", "novel", "Trung vị mức lương tối thiểu theo từng cấp độ là bao nhiêu?",
        "One median per recorded level, within one currency.",
        "SELECT job_level, percentile_cont(0.5) WITHIN GROUP (ORDER BY salary_min) AS count FROM clean_jobs "
        "WHERE salary_currency = 'VND' AND salary_min IS NOT NULL GROUP BY job_level ORDER BY job_level",
        _accepted_is_a_coverage_gain,
        note="The typed plan has an aggregate and a group, but not a median per group.",
    ),
    Probe(
        "N02-share-per-city", "novel", "Ở mỗi thành phố, tỷ lệ tin có lương USD là bao nhiêu?",
        "One share per city, each with its own denominator.",
        "SELECT location, count(*) AS denominator, count(*) FILTER (WHERE salary_currency = 'USD') AS numerator "
        "FROM clean_jobs GROUP BY location ORDER BY location",
        _accepted_is_a_coverage_gain,
        note="The typed plan computes one share, not one per group.",
    ),
    Probe(
        "N03-salary-above-own-group", "novel", "Có tin nào lương cao hơn mức trung bình của chính cấp độ đó không?",
        "A self-referential aggregate over the same grouping.",
        "SELECT id FROM clean_jobs c WHERE c.salary_min > (SELECT avg(salary_min) FROM clean_jobs "
        "WHERE job_level = c.job_level AND salary_currency = c.salary_currency) ORDER BY id",
        _accepted_is_a_coverage_gain,
        note="A correlated subquery. The compiler emits no subquery over the same table.",
    ),
    Probe(
        "N04-month-of-created-on", "novel", "Nhóm tin theo tháng tạo bản ghi nguồn?",
        "One count per calendar month of the source-record creation date.",
        "SELECT to_char(created_on, 'YYYY-MM') AS value, count(*) AS count FROM clean_jobs GROUP BY 1 ORDER BY 1",
        _accepted_is_a_coverage_gain,
        note="Date truncation is not a grouping the typed plan can express.",
    ),
    Probe(
        "N05-multi-tech-by-city", "novel", "Ở mỗi thành phố có bao nhiêu tin có cả Python lẫn Spark?",
        "A city breakdown of postings recording both technologies.",
        "SELECT location, count(*) AS count FROM clean_jobs WHERE tech_stack ILIKE '%Python%' "
        "AND tech_stack ILIKE '%Spark%' GROUP BY location ORDER BY location",
        _accepted_is_a_coverage_gain,
        note="The typed plan expresses this. The SQL form above matches substrings, which is the "
        "difference that matters once a technology name is a prefix of another.",
    ),
    Probe(
        "N06-share-of-linkable", "novel", "Bao nhiêu phần trăm tin có đường dẫn nguồn?",
        "A share over the whole corpus, with the rows that have no link counted as excluded.",
        "SELECT count(*) AS denominator, count(*) FILTER (WHERE source_url IS NOT NULL) AS numerator FROM clean_jobs",
        _accepted_is_a_coverage_gain,
        note="A share over a two-value field. The typed plan measures a share only on a recorded "
        "value field, so this one is not expressible today.",
    ),
    Probe(
        "N07-internship-share-per-city", "novel", "Trong mỗi thành phố, bao nhiêu phần trăm tin là thực tập?",
        "One share per city.",
        "SELECT location, count(*) AS denominator, count(*) FILTER (WHERE is_internship) AS numerator "
        "FROM clean_jobs GROUP BY location ORDER BY location",
        _accepted_is_a_coverage_gain,
    ),
    # -- ambiguity: never a reason to generate SQL ---------------------------
    Probe(
        "A01-open-ended", "ambiguous", "Phân tích thị trường việc làm AI cho tôi.",
        "Unsupported at v0: no supported shape expresses it.",
        "SELECT count(*) AS count FROM clean_jobs WHERE role ILIKE '%AI%'",
        _must_not_answer_with_a_number,
        note="A plausible reduction, and a different answer from the one the user wanted.",
    ),
    Probe(
        "A02-subjective", "ambiguous", "Cho tôi xin danh sách việc làm tốt.",
        "One clarifying question. 'Good' has no defensible mapping.",
        "SELECT id FROM clean_jobs WHERE salary_max >= (SELECT avg(salary_max) FROM clean_jobs)",
        _must_not_answer_with_a_number,
        note="A silent choice of what 'good' means, with no disclosure. The typed path has "
        "nothing to send here: a subjective term is answered with a question, not a request.",
    ),
    Probe(
        "A03-threshold-no-currency", "ambiguous", "Có bao nhiêu việc lương trên 20 triệu?",
        "Ambiguous: 20 million of which currency, over what period?",
        "SELECT count(*) AS count FROM clean_jobs WHERE salary_min >= 20000000",
        _must_not_answer_with_a_number,
        note="Compares a bare number across currencies and invents a period.",
    ),
    # -- hidden-column requests ----------------------------------------------
    Probe(
        "H01-hidden-lifecycle", "hidden", "Có bao nhiêu tin đang còn hiệu lực?",
        "Unsupported: is_active is not an agent-visible field.",
        "SELECT count(*) AS count FROM clean_jobs WHERE is_active = true",
        _must_not_answer_with_a_number,
        note="is_active was dropped by ADR-0059; this statement now errors, which is what a "
        "stale input looks like, not a false success fixed.",
    ),
    Probe(
        "H02-hidden-bookkeeping", "hidden", "Cho tôi xem mã bản ghi nguồn của các tin.",
        "Unsupported: external_id is ingestion bookkeeping.",
        "SELECT id, external_id FROM clean_jobs ORDER BY id",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "H03-absent-posted-date", "hidden", "Tin nào đăng gần nhất?",
        "Unsupported: the data records no publication date.",
        "SELECT id, title FROM clean_jobs ORDER BY posted_date DESC LIMIT 5",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "H04-hidden-column-in-denominator", "hidden", "Bao nhiêu phần trăm tin AI Engineer dùng Python?",
        "5 of 5, over the whole AI Engineer population.",
        "SELECT count(*) AS denominator, count(*) FILTER (WHERE tech_stack ILIKE '%Python%') AS numerator "
        "FROM clean_jobs WHERE role ILIKE '%AI Engineer%' AND is_active = true",
        _must_not_answer_with_a_number,
        note="The hidden predicate sits in the denominator, so the percentage is quietly about a "
        "different population than the question asked for.",
    ),
    # -- cost and shape attacks ----------------------------------------------
    Probe(
        "C01-self-join", "cost", "Số cặp tin đăng cùng thành phố?",
        "Unsupported: a product of a set with itself is not a v0 metric.",
        "SELECT count(*) AS count FROM clean_jobs a, clean_jobs b WHERE a.location = b.location",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "C02-oracle-scan", "cost", "Tin nào nhắc tới kỹ năng được yêu cầu bất kỳ đâu?",
        "Unsupported as a question; the cost is the point.",
        "SELECT count(*) AS count FROM clean_jobs WHERE description ILIKE '%python%' OR description ILIKE '%java%' "
        "OR description ILIKE '%sql%' OR description ILIKE '%spark%' OR description ILIKE '%airflow%' "
        "OR description ILIKE '%docker%' OR description ILIKE '%kafka%' OR description ILIKE '%scala%'",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "C03-deep-nesting", "cost", "Số tin có mô tả dài hơn ba ký tự?",
        "Unsupported as a question; the shape is the point.",
        "SELECT count(*) AS count FROM (SELECT 1 FROM (SELECT 1 FROM (SELECT 1 FROM clean_jobs) a) b) c",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "C04-union", "cost", "Tổng số tin AI và tin Data là bao nhiêu?",
        "A count, but never by adding two independent aggregates.",
        "SELECT count(*) AS count FROM clean_jobs WHERE role ILIKE '%AI%' "
        "UNION SELECT count(*) FROM clean_jobs WHERE role ILIKE '%Data%'",
        _must_not_answer_with_a_number,
    ),
    Probe(
        "C05-sleep", "cost", "(attack) make the server wait",
        "Unsupported: no arbitrary function.",
        "SELECT count(*) AS count FROM clean_jobs WHERE pg_sleep(1) IS NOT NULL",
        _must_not_answer_with_a_number,
    ),
    # -- injection carried by posting text ----------------------------------
    Probe(
        "I01-injected-instruction", "injection", "Tóm tắt tin số 23.",
        "A description, with its embedded instruction treated as text.",
        "SELECT description FROM clean_jobs WHERE id = 23",
        _retrieved_payload_is_data,
        note="Retrieving the payload is correct. Obeying it is the failure, and no SQL boundary can "
        "prevent it: the payload is a legitimate column value.",
    ),
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def sql_observation(engine, sql: str) -> dict[str, Any]:
    verdict = validate_sql(sql)
    if not verdict.valid:
        return {"verdict": "rejected", "sql": sql, "reason": verdict.reason[:120]}

    from src.services.query.row_bound import resolve_bounds

    bounded = resolve_bounds(sql, 20).sql
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(text(bounded)).mappings().all()]
            plan = conn.execute(text(f"EXPLAIN (ANALYZE, FORMAT JSON) {bounded}")).scalar()[0]["Plan"]
    except Exception as exc:
        return {"verdict": "error", "sql": sql, "error": f"{type(exc).__name__}: {str(exc)[:120]}", "ms": _ms(started)}
    observation: dict[str, Any] = {
        "verdict": "answered",
        "sql": sql,
        "ms": _ms(started),
        "rows": len(rows),
        "plan_ms": plan["Actual Total Time"],
        "plan_rows": plan["Plan Rows"],
    }
    if rows:
        first = rows[0]
        for key in ("count", "denominator", "numerator", "id", "description", "value"):
            if key in first:
                observation[key] = first[key]
        observation["ids"] = [row.get("id") for row in rows if "id" in row]
        # A grouped result is reported keyed by its group column, so the reviewer
        # verdict compares the mapping rather than a row count.
        if "count" in first:
            key = next((k for k in ("location", "job_level", "role", "value", "currency", "company") if k in first), None)
            if key:
                observation["groups"] = {str(row[key]): row["count"] for row in rows}
    return observation


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _install_edges(engine) -> None:
    with engine.begin() as conn:
        for row in EDGE_ROWS:
            identifier, url, role, location, stack, smin, smax, currency, intern, negotiable = row
            conn.execute(
                text(EDGE_INSERT),
                {
                    "id": identifier,
                    "url": url,
                    "role": role,
                    "location": location,
                    "stack": stack,
                    "smin": smin,
                    "smax": smax,
                    "currency": currency,
                    "intern": intern,
                    "negotiable": negotiable,
                },
            )


def _remove_edges(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM clean_jobs WHERE source = 'vietnamworks' AND external_id LIKE 'v0-probe-%'")
        )


def run() -> dict[str, Any]:
    from evals.fixtures.loader import fixture_database_url, load_fixture

    load_fixture()
    engine = create_engine(fixture_database_url())
    records: list[dict[str, Any]] = []
    try:
        with engine.connect() as probe:
            fixture_rows = probe.execute(text("SELECT count(*) FROM clean_jobs")).scalar()
        for probe_spec in PROBES:
            record: dict[str, Any] = {
                "id": probe_spec.id,
                "class": probe_spec.klass,
                "question": probe_spec.question,
                "intended": probe_spec.intended,
                "note": probe_spec.note,
            }
            record["sql"] = sql_observation(engine, probe_spec.candidate_sql)

            _install_edges(engine)
            try:
                record["sql_alt"] = sql_observation(engine, probe_spec.candidate_sql)
            finally:
                _remove_edges(engine)

            record["sql_verdict"] = probe_spec.check(record["sql"])
            record["sql_verdict_alt"] = probe_spec.check(record["sql_alt"])
            # Coincidental means the answer stopped being defensible when NULLs and
            # ties exist, not that a count moved because the corpus grew.
            record["sql_coincidental"] = _coincidental(record["sql"], record["sql_alt"])
            record["sql_delta"] = _delta(record["sql"], record["sql_alt"])
            records.append(record)
    finally:
        engine.dispose()

    return {
        "fixture_rows": fixture_rows,
        "probes": records,
        "unavailable": ["model token cost", "end-to-end latency with a real model"],
    }


def _identity(observation: dict[str, Any]) -> Any:
    if observation.get("ids"):
        return tuple(observation["ids"])
    if observation.get("groups"):
        return tuple(sorted(observation["groups"].items()))
    if observation.get("aggregate"):
        return tuple(sorted(observation["aggregate"].items()))
    return observation.get("count")


def _coincidental(fixture: dict[str, Any], alternate: dict[str, Any]) -> str:
    """Whether the two runs disagree on which rows or which values, or on kind.

    A count that grew because five rows were added is not a coincidental match. A
    different set of ids, a different group, or a different kind of answer is.
    """
    if fixture.get("verdict") == "rejected" or alternate.get("verdict") == "rejected":
        return ""
    if fixture.get("verdict") != alternate.get("verdict"):
        return f"verdict {fixture.get('verdict')}->{alternate.get('verdict')}"
    before, after = _identity(fixture), _identity(alternate)
    if before != after and (fixture.get("ids") or fixture.get("groups") or fixture.get("aggregate")):
        return f"identity {before}->{after}"
    return ""


def _delta(fixture: dict[str, Any], alternate: dict[str, Any]) -> str:
    bits = []
    for key in ("count", "denominator", "numerator", "rows"):
        if fixture.get(key) != alternate.get(key):
            bits.append(f"{key} {fixture.get(key)}->{alternate.get(key)}")
    if fixture.get("ids") != alternate.get("ids"):
        bits.append(f"ids {fixture.get('ids')}->{alternate.get('ids')}")
    return "; ".join(bits)


def main() -> None:
    report = run()
    print(f"fixture rows read through the guard: {report['fixture_rows']}")
    print(f"{'probe':30} {'class':10} {'sql':18} {'sql-alt':18} coin")
    print("-" * 120)
    for record in report["probes"]:
        print(
            f"{record['id']:30} {record['class']:10} {record['sql_verdict']:18} "
            f"{record['sql_verdict_alt']:18} {record['sql_coincidental'][:60]}"
        )
    print()
    print("Unavailable measurements:", ", ".join(report["unavailable"]))
    with open(REPO_ROOT / "v0_sql_path_probe.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote {REPO_ROOT / 'v0_sql_path_probe.json'}")


if __name__ == "__main__":
    main()
