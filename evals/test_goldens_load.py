from evals.goldens import build_eval_dataset, load_goldens


def test_load_goldens_shape() -> None:
    goldens = load_goldens()

    assert len(goldens) == 18
    assert sum(1 for c in goldens if c["honesty_probe"] is True) == 5
    assert {c["category"] for c in goldens} == {"A", "B", "C", "D", "E"}
    assert sum(1 for c in goldens if c["type"] == "conversational") == 2

    d_cases = [c for c in goldens if c["category"] == "D"]
    assert len(d_cases) == 3
    assert all(c["expected_tools"] == [] for c in d_cases)

    c1 = next(c for c in goldens if c["id"] == "C1")
    assert c1["honesty_probe"] is False
    assert "created_on" in c1["expected_output"]

    c6 = next(c for c in goldens if c["id"] == "C6")
    assert c6["honesty_probe"] is False
    assert "job_level" in c6["expected_output"]

    c7 = next(c for c in goldens if c["id"] == "C7")
    assert c7["honesty_probe"] is True
    assert "Application deadlines are not in the data" in c7["expected_output"]


def test_build_eval_dataset_non_empty() -> None:
    dataset = build_eval_dataset()

    assert len(dataset.goldens) > 0
