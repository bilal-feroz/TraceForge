from __future__ import annotations

from traceforge.models import (
    ChangeSet,
    Diagnosis,
    RegressionAssessment,
    RegressionClassification,
    TelemetryEvidence,
)


def generate_diagnosis(
    *,
    change: ChangeSet,
    assessment: RegressionAssessment,
    evidence: TelemetryEvidence,
    endpoint: str,
) -> Diagnosis:
    changed_file = next((item.path for item in change.files if item.path.endswith(".py")), None)
    trace_ids = [trace.trace_id for trace in evidence.traces if trace.trace_id][:10]
    log_lines = [
        f"{log.severity}: {log.body[:240]}"
        for log in evidence.logs
        if log.severity.upper() in {"ERROR", "FATAL", "CRITICAL", "WARN"}
    ][:10]
    dominant = next(iter(assessment.slow_span_concentration), None)
    classification = assessment.classification
    if classification == RegressionClassification.DATABASE_CONTENTION:
        cause = (
            "candidate requests show concurrent database failures and database spans/logs "
            "concentrate the regression"
        )
        remediation = (
            "reduce the transaction lock-hold interval and preserve safe SQLite concurrency "
            "settings, then rerun the identical load profile"
        )
    elif classification == RegressionClassification.SILENT_DEGRADATION:
        cause = (
            "candidate latency rises across ordered windows without a corresponding HTTP error rise"
        )
        remediation = (
            "remove request-time work that grows with accumulated state or bound that state, "
            "then verify the latency slope under the same staged load"
        )
    elif classification == RegressionClassification.LATENCY_REGRESSION:
        cause = f"server latency is dominated by {dominant or 'the affected operation'}"
        remediation = "minimize work on the measured critical path and rerun the same experiment"
    elif classification == RegressionClassification.ERROR_RATE_REGRESSION:
        cause = "server logs and error spans align with the candidate elevated failure rate"
        remediation = "address the recurring server error in the affected change and rerun"
    elif classification == RegressionClassification.NO_REGRESSION:
        cause = "no material regression crossed the deterministic gates"
        remediation = "no remediation is required"
    else:
        cause = "available evidence cannot isolate a supported root cause"
        remediation = "collect complete SigNoz traces, logs, and metrics before proposing a patch"

    return Diagnosis(
        summary="; ".join(assessment.deterministic_reasons),
        classification=classification,
        affected_endpoint=endpoint,
        first_bad_revision=change.candidate.sha,
        likely_root_cause=cause,
        root_cause_file=changed_file,
        root_cause_lines=[],
        confidence=0.9 if evidence.available and trace_ids else 0.45,
        supporting_metrics=[
            f"P95 {assessment.latency_p95.baseline:.2f} ms -> "
            f"{assessment.latency_p95.candidate:.2f} ms",
            f"failure rate {assessment.error_rate.baseline:.4f} -> "
            f"{assessment.error_rate.candidate:.4f}",
            f"throughput {assessment.throughput.baseline:.2f} -> "
            f"{assessment.throughput.candidate:.2f} req/s",
        ],
        supporting_traces=trace_ids,
        supporting_logs=log_lines,
        rejected_hypotheses=[
            "client-only network delay"
            if assessment.server_client_latency_gap_ms is not None
            else "client/server latency split unavailable"
        ],
        remediation_strategy=remediation,
        unresolved_questions=[] if evidence.available else ["server telemetry is incomplete"],
        evidence_window=evidence.window,
        service_name=evidence.service_name,
        mcp_tools_used=sorted({item.tool_name for item in evidence.mcp_invocations}),
    )
