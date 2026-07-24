import json
from pathlib import Path

from traceforge.k6 import parse_summary


def test_parse_legacy_k6_summary(tmp_path: Path) -> None:
    summary = {
        "metrics": {
            "http_reqs": {"values": {"count": 100, "rate": 20}},
            "http_req_duration": {
                "values": {
                    "med": 25,
                    "p(90)": 80,
                    "p(95)": 100,
                    "p(99)": 180,
                },
                "thresholds": {"p(95)<1000": {"ok": True}},
            },
            "http_req_failed": {"values": {"rate": 0.02}},
            "checks": {"values": {"passes": 196, "fails": 4}},
        }
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    raw = tmp_path / "samples.json"
    raw.write_text("", encoding="utf-8")
    result = parse_summary(path, raw_json_path=raw, duration_seconds=5)
    assert result.count == 100
    assert result.rate == 20
    assert result.p95_ms == 100
    assert result.failure_rate == 0.02
    assert not result.threshold_failures


def test_parse_threshold_failure(tmp_path: Path) -> None:
    summary = {
        "metrics": {
            "http_reqs": {"values": {"count": 1, "rate": 1}},
            "http_req_duration": {
                "values": {"med": 1, "p(90)": 1, "p(95)": 1, "p(99)": 1},
                "thresholds": {"p(95)<1": {"ok": False}},
            },
            "http_req_failed": {"values": {"rate": 0}},
            "checks": {"values": {"passes": 1, "fails": 0}},
        }
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    result = parse_summary(path, raw_json_path=tmp_path / "none", duration_seconds=1)
    assert result.threshold_failures == ["http_req_duration: p(95)<1"]
