from traceforge.signoz import (
    SigNozMCPClient,
    _contains_correlation,
    _rows,
)


def test_rows_unwraps_current_mcp_content_and_query_envelopes() -> None:
    payload = [
        {
            "status": "success",
            "data": {
                "data": {
                    "results": [
                        {
                            "queryName": "A",
                            "rows": [
                                {
                                    "timestamp": "2026-07-24T18:00:00Z",
                                    "data": {
                                        "trace_id": "trace-1",
                                        "span_id": "span-1",
                                        "name": "POST /api/visits",
                                    },
                                }
                            ],
                        }
                    ]
                }
            },
        },
        "Result truncated to the requested limit.",
    ]

    rows = _rows(payload)

    assert len(rows) == 1
    assert rows[0]["data"]["trace_id"] == "trace-1"


def test_current_trace_and_log_rows_are_normalized() -> None:
    trace = SigNozMCPClient._trace_evidence(
        {
            "timestamp": "2026-07-24T18:00:00Z",
            "data": {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "name": "POST /api/visits",
                "duration_nano": 12_500_000,
                "status_code_string": "Error",
            },
        }
    )
    log_row = {
        "data": {
            "timestamp": 1_784_916_000_000_000_000,
            "trace_id": "trace-1",
            "span_id": "span-1",
            "severity_text": "ERROR",
            "body": {"event": "request.failed", "message": "database is locked"},
            "attributes_string": {
                "traceforge.run.id": "run-1",
                "traceforge.phase": "candidate",
            },
        }
    }
    log = SigNozMCPClient._log_evidence(log_row)

    assert trace.trace_id == "trace-1"
    assert trace.duration_ms == 12.5
    assert trace.status == "Error"
    assert log.trace_id == "trace-1"
    assert log.severity == "ERROR"
    assert "database is locked" in log.body
    assert _contains_correlation(log_row, "run-1")
