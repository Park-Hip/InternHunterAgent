from evals.telemetry import aggregate_capture


def test_aggregate_capture_is_provenance_stamped_and_offline(monkeypatch):
    monkeypatch.setattr("evals.telemetry._pricing", lambda provider: (0.14, 0.28))
    capture = {
        "manifest": {"run_id": "run-1", "prompt_version": "v3", "provider": "deepseek"},
        "scenarios": {
            "A": {
                "repeats": [{
                    "turns": [
                        {"status": "COMPLETE", "telemetry": {"latency_ms": 100, "provider_token_usage": {"aggregate": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}}}},
                        {"status": "COMPLETE", "telemetry": {"latency_ms": 300, "provider_token_usage": {"aggregate": {"input_tokens": 2000, "output_tokens": 200, "total_tokens": 2200}}}},
                    ]
                }]
            }
        },
    }
    report = aggregate_capture(capture, measured_at="2026-08-19")
    assert report["source_capture"] == "run-1"
    assert report["prompt_version"] == "v3"
    assert report["turns"]["latency_ms"]["p50"] == 200
    assert report["turns"]["latency_ms"]["p95"] == 290
    assert report["cost"]["usd"] == 0.000504


def test_unavailable_telemetry_is_excluded(monkeypatch):
    monkeypatch.setattr("evals.telemetry._pricing", lambda provider: (1, 1))
    capture = {"manifest": {"provider": "deepseek"}, "scenarios": {"A": {"repeats": [{"turns": [{"status": "COMPLETE", "telemetry": {"latency_ms": "unavailable"}}]}]}}}
    report = aggregate_capture(capture, measured_at="2026-08-19")
    assert report["turns"]["latency_ms"] == {"count": 0, "p50": None, "p95": None, "total": 0}
