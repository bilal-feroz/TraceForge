from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import fmean

from traceforge.models import (
    K6RunResult,
    NumericDelta,
    RegressionAssessment,
    RegressionClassification,
    TelemetryEvidence,
)


def numeric_delta(baseline: float, candidate: float) -> NumericDelta:
    relative = None if baseline == 0 else ((candidate - baseline) / baseline) * 100
    return NumericDelta(
        baseline=baseline,
        candidate=candidate,
        absolute=candidate - baseline,
        relative_percent=relative,
    )


def latency_slope(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    x_mean = (len(values) - 1) / 2
    y_mean = fmean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator == 0:
        return None
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    return numerator / denominator


def _slow_spans(evidence: TelemetryEvidence | None) -> dict[str, float]:
    if evidence is None or not evidence.traces:
        return {}
    totals: defaultdict[str, float] = defaultdict(float)
    overall = 0.0
    for trace in evidence.traces:
        totals[trace.operation] += trace.duration_ms
        overall += trace.duration_ms
    if overall <= 0:
        return {}
    return {
        operation: round(duration / overall, 4)
        for operation, duration in sorted(totals.items(), key=lambda item: -item[1])[:10]
    }


def _errors(evidence: TelemetryEvidence | None) -> dict[str, int]:
    if evidence is None:
        return {}
    counter: Counter[str] = Counter()
    for log in evidence.logs:
        if log.severity.upper() in {"ERROR", "FATAL", "CRITICAL"}:
            counter[log.body[:160]] += 1
    return dict(counter.most_common(10))


def _server_client_gap(candidate: K6RunResult, evidence: TelemetryEvidence | None) -> float | None:
    if evidence is None or not evidence.traces:
        return None
    durations = [trace.duration_ms for trace in evidence.traces]
    durations.sort()
    index = min(len(durations) - 1, math.ceil(len(durations) * 0.95) - 1)
    return candidate.stats.p95_ms - durations[index]


def assess_regression(
    baseline: K6RunResult,
    candidate: K6RunResult,
    *,
    candidate_evidence: TelemetryEvidence | None = None,
) -> RegressionAssessment:
    p95 = numeric_delta(baseline.stats.p95_ms, candidate.stats.p95_ms)
    p99 = numeric_delta(baseline.stats.p99_ms, candidate.stats.p99_ms)
    errors = numeric_delta(baseline.stats.failure_rate, candidate.stats.failure_rate)
    throughput = numeric_delta(baseline.stats.rate, candidate.stats.rate)
    slope = latency_slope(candidate.stats.ordered_p95_windows_ms)
    threshold_violations = list(candidate.stats.threshold_failures)
    reasons: list[str] = []

    enough_client_samples = baseline.stats.count >= 20 and candidate.stats.count >= 20
    telemetry_available = candidate_evidence is not None and candidate_evidence.available
    sufficient = enough_client_samples and telemetry_available

    error_regression = (
        candidate.stats.failure_rate >= max(0.02, baseline.stats.failure_rate + 0.01)
        and errors.absolute >= 0.01
    )
    latency_regression = (
        p95.absolute >= 50 and (p95.relative_percent or 0) >= 20 and candidate.stats.p95_ms >= 100
    )
    throughput_regression = throughput.absolute < 0 and (throughput.relative_percent or 0) <= -20
    rising_latency = slope is not None and slope >= 10
    errors_text = " ".join(_errors(candidate_evidence)).lower()
    trace_operations = " ".join(_slow_spans(candidate_evidence)).lower()

    if not sufficient:
        classification = RegressionClassification.INSUFFICIENT_EVIDENCE
        if not enough_client_samples:
            reasons.append("fewer than 20 client requests were measured in one or both phases")
        if not telemetry_available:
            reasons.append(
                "SigNoz server-side telemetry was not confirmed for the exact run window"
            )
    elif error_regression and (
        "database is locked" in errors_text or "sqlite" in errors_text or "db." in trace_operations
    ):
        classification = RegressionClassification.DATABASE_CONTENTION
        reasons.append("error rate rose and database contention evidence dominates server signals")
    elif error_regression:
        classification = RegressionClassification.ERROR_RATE_REGRESSION
        reasons.append("candidate HTTP failure rate materially exceeds the baseline")
    elif latency_regression and rising_latency and candidate.stats.failure_rate < 0.01:
        classification = RegressionClassification.SILENT_DEGRADATION
        reasons.append("latency regressed with a positive slope while the error rate remained low")
    elif latency_regression:
        classification = RegressionClassification.LATENCY_REGRESSION
        reasons.append("candidate P95 latency is at least 20% and 50 ms above baseline")
    elif throughput_regression:
        classification = RegressionClassification.THROUGHPUT_REGRESSION
        reasons.append("candidate throughput is at least 20% below baseline")
    else:
        classification = RegressionClassification.NO_REGRESSION
        reasons.append(
            "deterministic latency, error, and throughput gates found no material regression"
        )

    return RegressionAssessment(
        classification=classification,
        latency_p95=p95,
        latency_p99=p99,
        error_rate=errors,
        throughput=throughput,
        latency_slope_ms_per_window=slope,
        server_client_latency_gap_ms=_server_client_gap(candidate, candidate_evidence),
        threshold_violations=threshold_violations,
        slow_span_concentration=_slow_spans(candidate_evidence),
        error_concentration=_errors(candidate_evidence),
        deterministic_reasons=reasons,
        sufficient_evidence=sufficient,
    )
