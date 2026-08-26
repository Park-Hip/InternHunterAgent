from __future__ import annotations

import json
from datetime import date

import pytest

from evals.replay import (
    ARCHIVED_REPLAY_NAMES,
    REPLAY_PATH,
    REPLAY_SCHEMA_VERSION,
    active_replay_paths,
    load_replay,
    run_active_replays,
    run_replay,
    validate_replay,
)


def _expected_execution(replay: dict) -> dict:
    return {
        "scenarios": {
            scenario_id: [
                {
                    "repeat": repeat["repeat"],
                    "turns": [
                        {"status": turn["expected_execution_accuracy"]}
                        for turn in repeat["turns"]
                    ],
                }
                for repeat in scenario_record["repeats"]
            ]
            for scenario_id, scenario_record in replay["scenarios"].items()
        }
    }


def _expected_grades(replay: dict) -> dict:
    return {
        "scenarios": {
            scenario_id: [
                {
                    "repeat": repeat["repeat"],
                    "turn": turn["turn"],
                    "status": turn["expected_grade"],
                }
                for repeat in scenario_record["repeats"]
                for turn in repeat["turns"]
            ]
            for scenario_id, scenario_record in replay["scenarios"].items()
        }
    }


def test_committed_replay_is_sanitized_and_covers_required_cases() -> None:
    replay = load_replay()

    validate_replay(replay)

    assert {
        scenario_id.split("-", maxsplit=1)[0] for scenario_id in replay["scenarios"]
    } == {
        "SAF",
        "HON",
        "HLP",
    }
    assert replay["scenarios"]["HLP-CONTEXT-1"]["scenario_type"] == "conversational"
    encoded = json.dumps(replay).lower()
    assert "trace_id" not in encoded
    assert "postgresql://" not in encoded
    assert "api_key" not in encoded


def test_committed_replay_names_the_prompt_that_produced_it() -> None:
    """Every committed replay carries the prompt version its capture ran (M35)."""
    replay = load_replay()

    assert replay["manifest"]["schema_version"] in {2, 3, REPLAY_SCHEMA_VERSION}
    assert replay["manifest"]["prompt_version"] == "v1"


def test_committed_replay_records_the_cross_currency_failure() -> None:
    replay = load_replay()

    currency_turn = replay["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]

    assert currency_turn["expected_execution_accuracy"] == "FAIL"
    assert currency_turn["expected_grade"] == "FAIL"


def test_replay_rejects_a_manifest_that_cannot_name_its_prompt() -> None:
    """An unlabelled replay is not evidence: it cannot be placed against a prompt change."""
    replay = load_replay()
    del replay["manifest"]["prompt_version"]

    with pytest.raises(ValueError, match="prompt_version"):
        validate_replay(replay)


def test_replay_accepts_named_prompt_lineage_without_rewriting_legacy_artifacts() -> None:
    replay = load_replay()
    replay["manifest"] = {
        **replay["manifest"],
        "schema_version": REPLAY_SCHEMA_VERSION,
        "prompt_versions": {
            "system": "v11",
            "schema_context": "v11",
            "sql_generation": "v11",
        },
    }
    del replay["manifest"]["prompt_version"]
    for scenario in replay["scenarios"].values():
        for repeat in scenario["repeats"]:
            for turn in repeat["turns"]:
                turn["seams"].update({"tool_output": None, "tool_arguments": None})

    validate_replay(replay)


def test_replay_rejects_a_pre_stamp_schema_version() -> None:
    """A schema_version 1 artifact predates the stamp and must not pass as a stamped one."""
    replay = load_replay()
    replay["manifest"]["schema_version"] = 1

    with pytest.raises(ValueError, match="schema_version"):
        validate_replay(replay)


def test_replay_rejects_trace_data() -> None:
    replay = load_replay()
    replay["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]["seams"][
        "trace_id"
    ] = "live-trace"

    with pytest.raises(ValueError, match="credential or live trace"):
        validate_replay(replay)


def test_replay_rejects_secret_like_content() -> None:
    replay = load_replay()
    replay["scenarios"]["HON-SQL-DESCRIBE-1"]["repeats"][0]["turns"][0]["seams"][
        "answer"
    ] = "api_key=not-a-real-secret"

    with pytest.raises(ValueError, match="credential or live trace"):
        validate_replay(replay)


def test_replay_rejects_a_question_that_drifted_from_the_registry() -> None:
    replay = load_replay()
    replay["scenarios"]["HLP-CONTEXT-1"]["repeats"][0]["turns"][1]["seams"][
        "question"
    ] = "Only the ones in Da Nang."

    with pytest.raises(ValueError, match="does not match the frozen registry"):
        validate_replay(replay)


def test_replay_accepts_a_recorded_execution_failure() -> None:
    replay = load_replay()
    replay["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0][
        "expected_execution_accuracy"
    ] = "FAIL"

    validate_replay(replay)


def test_replay_accepts_a_not_evaluated_execution_result() -> None:
    replay = load_replay()
    replay["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0][
        "expected_execution_accuracy"
    ] = "NOT_EVALUATED"

    validate_replay(replay)


def test_replay_runs_execution_accuracy_before_the_deterministic_grader(
    monkeypatch,
) -> None:
    import evals.replay as replay_module

    calls: list[str] = []
    replay = load_replay()
    monkeypatch.setattr(
        replay_module,
        "grade_run",
        lambda run, database_url=None: (
            calls.append("execution") or _expected_execution(run)
        ),
    )
    monkeypatch.setattr(
        replay_module,
        "grade_persisted_run",
        lambda run, execution: calls.append("grader") or _expected_grades(run),
    )

    report = run_replay(REPLAY_PATH)

    assert calls == ["execution", "grader"]
    assert report == {
        "execution_accuracy": _expected_execution(replay),
        "grades": _expected_grades(replay),
    }


def test_replay_fails_when_an_expected_execution_result_drifts(monkeypatch) -> None:
    import evals.replay as replay_module

    monkeypatch.setattr(
        replay_module,
        "grade_run",
        lambda run, database_url=None: {
            **_expected_execution(run),
            "scenarios": {
                **_expected_execution(run)["scenarios"],
                # The frozen expectation for this turn is FAIL, so PASS is the drift.
                "HON-CURRENCY-1": [{"repeat": 1, "turns": [{"status": "PASS"}]}],
            },
        },
    )
    monkeypatch.setattr(
        replay_module,
        "grade_persisted_run",
        lambda run, execution: _expected_grades(run),
    )

    with pytest.raises(ValueError, match="Replay outcome mismatch"):
        run_replay(REPLAY_PATH)


def test_replay_cli_serializes_fixture_values(tmp_path, monkeypatch, capsys) -> None:
    import evals.replay as replay_module

    replay_path = tmp_path / "replay.json"
    replay_path.write_text(json.dumps(load_replay()), encoding="utf-8")
    monkeypatch.setattr(
        replay_module,
        "run_replay",
        lambda path, database_url=None: {"row": {"created_on": date(2026, 8, 13)}},
    )

    replay_module.main(["--replay", str(replay_path)])

    assert json.loads(capsys.readouterr().out) == {"row": {"created_on": "2026-08-13"}}


def test_discovery_finds_every_json_artifact_and_ignores_nothing(tmp_path) -> None:
    (tmp_path / "b-replay.json").write_text("{}", encoding="utf-8")
    (tmp_path / "a-replay.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.md").write_text("not evidence", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.json").write_text("{}", encoding="utf-8")

    assert active_replay_paths(tmp_path) == [
        tmp_path / "a-replay.json",
        tmp_path / "b-replay.json",
    ]


def test_committed_replay_is_never_silently_omitted_from_discovery() -> None:
    discovered = {path.name for path in active_replay_paths()}

    assert REPLAY_PATH.name in discovered
    # Preserved history lives outside the active set and must stay there.
    # iha243-honesty-v9.json joined the active set with issue #243 (prompt-v9
    # honesty-capture freeze, 2026-08-26). iha251-hlp-abstraction-v10.json joined
    # with issue #251 (prompt-v10 abstraction-capture freeze, 2026-08-26).
    assert discovered == {
        REPLAY_PATH.name,
        "iha243-honesty-v9.json",
        "iha251-hlp-abstraction-v10.json",
    }
    for name in ARCHIVED_REPLAY_NAMES:
        assert name not in discovered


def test_every_active_replay_validates_against_the_registry_without_a_model_call() -> None:
    paths = active_replay_paths()

    assert paths, "the active replay set must not be empty"
    for path in paths:
        validate_replay(load_replay(path))


def test_run_active_replays_runs_every_discovered_artifact(monkeypatch) -> None:
    import evals.replay as replay_module

    replayed: list[str] = []

    def fake_grade_run(run, database_url=None):
        replayed.append(next(iter(run["scenarios"])))
        return _expected_execution(run)

    monkeypatch.setattr(replay_module, "grade_run", fake_grade_run)
    monkeypatch.setattr(
        replay_module,
        "grade_persisted_run",
        lambda run, execution: _expected_grades(run),
    )

    report = run_active_replays()

    assert sorted(replayed) == sorted(
        scenario_id
        for path in active_replay_paths()
        for scenario_id in [next(iter(load_replay(path)["scenarios"]))]
    )
    assert set(report) == {path.name for path in active_replay_paths()}


def test_run_active_replays_names_a_stale_artifact_instead_of_stopping(
    tmp_path, monkeypatch
) -> None:
    import evals.replay as replay_module

    stale_artifact = {**load_replay(), "status": "INCOMPLETE"}

    stale = tmp_path / "stale-artifact.json"
    stale.write_text(json.dumps(stale_artifact), encoding="utf-8")
    healthy = tmp_path / "healthy-artifact.json"
    healthy.write_text(json.dumps(load_replay()), encoding="utf-8")
    monkeypatch.setattr(replay_module, "ACTIVE_REPLAY_DIR", tmp_path)
    monkeypatch.setattr(
        replay_module, "grade_run", lambda run, database_url=None: _expected_execution(run)
    )
    monkeypatch.setattr(
        replay_module,
        "grade_persisted_run",
        lambda run, execution: _expected_grades(run),
    )

    with pytest.raises(ValueError, match="stale-artifact.json.*must be COMPLETE"):
        run_active_replays()

    # Both artifacts were examined; the failure did not stop at the first.
    assert stale.exists() and healthy.exists()
