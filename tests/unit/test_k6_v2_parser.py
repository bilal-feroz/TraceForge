import json
from pathlib import Path

from traceforge.k6 import parse_summary


def summary_with_threshold(crossed: bool) -> dict:
    return {
        "metrics": {
            "http_reqs": {"count": 10, "rate": 5, "thresholds": {}},
            "http_req_duration": {
                "med": 10,
                "p(90)": 12,
                "p(95)": 15,
                "p(99)": 18,
                "thresholds": {"p(95)<1000": crossed},
            },
            "http_req_failed": {
                "value": 0,
                "passes": 0,
                "fails": 10,
                "thresholds": {"rate<0.05": crossed},
            },
            "checks": {
                "passes": 20,
                "fails": 0,
                "value": 1,
                "thresholds": {"rate>0.95": crossed},
            },
        }
    }


def parse(tmp_path: Path, crossed: bool):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary_with_threshold(crossed)), encoding="utf-8")
    return parse_summary(path, raw_json_path=tmp_path / "samples.json", duration_seconds=2)


def test_k6_v2_false_means_threshold_not_crossed(tmp_path: Path) -> None:
    assert parse(tmp_path, crossed=False).threshold_failures == []


def test_k6_v2_true_means_threshold_crossed(tmp_path: Path) -> None:
    assert len(parse(tmp_path, crossed=True).threshold_failures) == 3
