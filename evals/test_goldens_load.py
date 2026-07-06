from evals.goldens import build_eval_dataset, load_goldens


def test_load_goldens_shape() -> None:
    goldens = load_goldens()

    assert len(goldens) == 17
    assert sum(1 for c in goldens if c["honesty_probe"] is True) == 6
    assert {c["category"] for c in goldens} == {"A", "B", "C", "D", "E"}
    assert sum(1 for c in goldens if c["type"] == "conversational") == 2

    d_cases = [c for c in goldens if c["category"] == "D"]
    assert len(d_cases) == 3
    assert all(c["expected_tools"] == [] for c in d_cases)


def test_build_eval_dataset_non_empty() -> None:
    dataset = build_eval_dataset()

    assert len(dataset.goldens) > 0
