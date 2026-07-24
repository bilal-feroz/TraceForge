from traceforge.signoz_metrics import metric_evidence


def test_metric_evidence_parses_prometheus_series_and_milliseconds() -> None:
    payload = {
        "data": {
            "result": [
                {
                    "metric": {
                        "__name__": "traceforge.demo.request.duration",
                        "traceforge.phase": "candidate",
                    },
                    "values": [[1_721_750_400, "42.5"], [1_721_750_410_000, 51]],
                    "unit": "ms",
                }
            ]
        }
    }

    result = metric_evidence(payload, default_name="fallback")

    assert len(result) == 1
    assert result[0].name == "traceforge.demo.request.duration"
    assert [point[1] for point in result[0].points] == [42.5, 51.0]
    assert result[0].points[0][0] == result[0].points[1][0].replace(second=0)


def test_metric_evidence_ignores_non_series_payloads() -> None:
    assert metric_evidence({"data": {"value": 12}}, default_name="metric") == []
