"""Read-only projection of a persisted run into the evidence a reviewer must audit.

Nothing here re-queries SigNoz or recomputes a verdict. It reshapes stored k6 results,
retrieved telemetry rows, and ledger events so the interface can present per-phase numbers
that are attributed to the exact experiment window instead of the wider ingestion margin.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

from traceforge.ledger import AuditLedger
from traceforge.models import (
    ExperimentWindow,
    K6RunResult,
    LogEvidence,
    Phase,
    RegressionAssessment,
    StrictModel,
    TelemetryEvidence,
    TraceEvidence,
    TraceForgeRun,
    utc_now,
)
from traceforge.signoz import EVIDENCE_ROW_LIMIT

LOCK_ERROR_MARKER = "database is locked"
ERROR_SEVERITIES = {"ERROR", "FATAL", "CRITICAL"}
EvidenceStatus = Literal["confirmed", "partial", "unavailable", "pending"]
MetricDirection = Literal["lower_is_better", "higher_is_better", "neutral"]


class OperationLatency(StrictModel):
    operation: str
    span_count: int
    p95_ms: float


class TraceLink(StrictModel):
    trace_id: str
    span_id: str | None
    operation: str
    duration_ms: float
    status: str
    error: bool
    signoz_url: str | None


class LogSample(StrictModel):
    timestamp: datetime
    severity: str
    trace_id: str | None
    message: str
    lock_error: bool


class PhaseLoad(StrictModel):
    phase: Phase
    successful: bool
    exit_code: int
    request_count: int
    throughput_rps: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    failure_rate: float
    checks_passed: int
    checks_failed: int
    duration_seconds: float
    threshold_failures: list[str]
    ordered_p95_windows_ms: list[float]
    script_digest: str
    window: ExperimentWindow


class PhaseEvidence(StrictModel):
    phase: Phase
    available: bool
    unavailable_reason: str | None
    service_name: str
    window: ExperimentWindow
    trace_rows_retrieved: int
    log_rows_retrieved: int
    row_limit: int
    row_limit_reached: bool
    spans_in_window: int
    error_spans_in_window: int
    logs_in_window: int
    error_logs_in_window: int
    lock_error_logs_in_window: int
    http_status_counts: dict[str, int]
    top_operations: list[OperationLatency]
    metric_series: int
    mcp_tool_calls: int
    mcp_tool_failures: int
    mcp_tools_used: list[str]
    tools_discovered: int
    trace_links: list[TraceLink]
    log_samples: list[LogSample]


class PhaseProof(StrictModel):
    phase: Phase
    load: PhaseLoad | None
    evidence: PhaseEvidence | None


class ComparisonMetric(StrictModel):
    key: str
    label: str
    unit: str
    baseline: float | None
    candidate: float | None
    patched: float | None
    direction: MetricDirection
    caveat: str | None = None


class TimelineEvent(StrictModel):
    sequence: int
    action: str
    previous_state: str
    next_state: str
    occurred_at: datetime
    outcome: str
    elapsed_seconds: float
    event_hash_prefix: str


class LedgerStatus(StrictModel):
    recorded: bool
    valid: bool
    event_count: int
    terminal_state: str | None
    terminal_required: bool
    head_hash_prefix: str | None
    errors: list[str]


class ReleaseProof(StrictModel):
    run_id: str
    generated_at: datetime
    stage: str
    terminal_state: str | None
    verdict: str | None
    verdict_reason: str | None
    repository: str
    base_ref: str
    candidate_ref: str
    base_sha: str | None
    candidate_sha: str | None
    merge_base_sha: str | None
    endpoint: str | None
    profile: str
    scenario: str | None
    created_at: datetime
    updated_at: datetime
    elapsed_seconds: float
    evidence_status: EvidenceStatus
    classification: str | None
    patch_verification_status: str | None
    patch_audit_passed: bool | None
    patch_changed_files: list[str]
    phases: list[PhaseProof]
    comparison: list[ComparisonMetric]
    interpretation: list[str]
    timeline: list[TimelineEvent]
    ledger: LedgerStatus
    signoz_service: str | None
    limitations: list[str]


def _as_datetime(value: Any) -> datetime | None:
    """Normalize the timestamp shapes SigNoz returns for spans and log records."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        seconds = float(value)
        for divisor in (1e9, 1e6, 1e3):
            if seconds > 1e11:
                seconds /= divisor
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _within(moment: datetime | None, window: ExperimentWindow) -> bool:
    if moment is None:
        return False
    return window.started_at <= moment <= window.ended_at


def _string_attributes(record: LogEvidence) -> dict[str, Any]:
    nested = record.attributes.get("attributes_string")
    return nested if isinstance(nested, dict) else {}


def _log_phase(record: LogEvidence) -> str | None:
    value = _string_attributes(record).get("traceforge.phase")
    return value if isinstance(value, str) else None


def _log_in_phase(record: LogEvidence, phase: Phase, window: ExperimentWindow) -> bool:
    declared = _log_phase(record)
    if declared is not None:
        return declared == phase.value
    return _within(record.timestamp, window)


def _span_in_window(trace: TraceEvidence, window: ExperimentWindow) -> bool:
    return _within(_as_datetime(trace.attributes.get("timestamp")), window)


def _span_failed(trace: TraceEvidence) -> bool:
    if trace.attributes.get("has_error") is True:
        return True
    return trace.status.lower() in {"error", "true"}


def _lock_error(record: LogEvidence) -> bool:
    attributes = _string_attributes(record)
    exception = attributes.get("exception.message")
    haystack = f"{record.body} {exception if isinstance(exception, str) else ''}".lower()
    return LOCK_ERROR_MARKER in haystack


def _log_message(record: LogEvidence) -> str:
    exception = _string_attributes(record).get("exception.message")
    if isinstance(exception, str) and exception:
        return f"{record.body} | {exception}"[:400]
    return record.body[:400]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)
    return ordered[max(0, index)]


def _top_operations(spans: list[TraceEvidence], limit: int = 5) -> list[OperationLatency]:
    grouped: dict[str, list[float]] = {}
    for span in spans:
        grouped.setdefault(span.operation, []).append(span.duration_ms)
    items = [
        OperationLatency(
            operation=operation,
            span_count=len(durations),
            p95_ms=round(_percentile(durations, 0.95), 3),
        )
        for operation, durations in grouped.items()
    ]
    items.sort(key=lambda item: (-item.p95_ms, item.operation))
    return items[:limit]


def _status_counts(spans: list[TraceEvidence]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for span in spans:
        code = span.attributes.get("response_status_code")
        counter[str(code) if code not in (None, "") else "unknown"] += 1
    return dict(sorted(counter.items()))


def _phase_load(result: K6RunResult) -> PhaseLoad:
    stats = result.stats
    return PhaseLoad(
        phase=result.phase,
        successful=result.successful,
        exit_code=result.exit_code,
        request_count=stats.count,
        throughput_rps=stats.rate,
        p50_ms=stats.p50_ms,
        p90_ms=stats.p90_ms,
        p95_ms=stats.p95_ms,
        p99_ms=stats.p99_ms,
        failure_rate=stats.failure_rate,
        checks_passed=stats.checks_passed,
        checks_failed=stats.checks_failed,
        duration_seconds=stats.duration_seconds,
        threshold_failures=list(stats.threshold_failures),
        ordered_p95_windows_ms=list(stats.ordered_p95_windows_ms),
        script_digest=result.script_digest,
        window=result.window,
    )


def _phase_evidence(
    phase: Phase, evidence: TelemetryEvidence, window: ExperimentWindow
) -> PhaseEvidence:
    spans = [span for span in evidence.traces if _span_in_window(span, window)]
    logs = [record for record in evidence.logs if _log_in_phase(record, phase, window)]
    error_logs = [record for record in logs if record.severity.upper() in ERROR_SEVERITIES]
    lock_logs = [record for record in logs if _lock_error(record)]
    failed_spans = [span for span in spans if _span_failed(span)]
    interesting = failed_spans or spans
    return PhaseEvidence(
        phase=phase,
        available=evidence.available,
        unavailable_reason=evidence.unavailable_reason,
        service_name=evidence.service_name,
        window=window,
        trace_rows_retrieved=len(evidence.traces),
        log_rows_retrieved=len(evidence.logs),
        row_limit=EVIDENCE_ROW_LIMIT,
        row_limit_reached=len(evidence.traces) >= EVIDENCE_ROW_LIMIT
        or len(evidence.logs) >= EVIDENCE_ROW_LIMIT,
        spans_in_window=len(spans),
        error_spans_in_window=len(failed_spans),
        logs_in_window=len(logs),
        error_logs_in_window=len(error_logs),
        lock_error_logs_in_window=len(lock_logs),
        http_status_counts=_status_counts(spans),
        top_operations=_top_operations(spans),
        metric_series=len(evidence.metrics),
        mcp_tool_calls=len(evidence.mcp_invocations),
        mcp_tool_failures=sum(1 for call in evidence.mcp_invocations if not call.success),
        mcp_tools_used=sorted({call.tool_name for call in evidence.mcp_invocations}),
        tools_discovered=len(evidence.tools_discovered),
        trace_links=[_trace_link(span) for span in interesting[:12]],
        log_samples=[_log_sample(record) for record in (lock_logs or error_logs or logs)[:12]],
    )


def _trace_link(span: TraceEvidence) -> TraceLink:
    url = span.attributes.get("webUrl")
    return TraceLink(
        trace_id=span.trace_id,
        span_id=span.span_id,
        operation=span.operation,
        duration_ms=span.duration_ms,
        status=span.status,
        error=_span_failed(span),
        signoz_url=url if isinstance(url, str) and url.startswith("https://") else None,
    )


def _log_sample(record: LogEvidence) -> LogSample:
    return LogSample(
        timestamp=record.timestamp,
        severity=record.severity,
        trace_id=record.trace_id,
        message=_log_message(record),
        lock_error=_lock_error(record),
    )


def _evidence_status(run: TraceForgeRun) -> EvidenceStatus:
    if not run.telemetry:
        return "pending"
    states = [item.available for item in run.telemetry.values()]
    if all(states):
        return "confirmed"
    if any(states):
        return "partial"
    return "unavailable"


def _metric(
    key: str,
    label: str,
    unit: str,
    direction: MetricDirection,
    loads: dict[Phase, PhaseLoad],
    reader: Any,
    caveat: str | None = None,
) -> ComparisonMetric:
    def value(phase: Phase) -> float | None:
        load = loads.get(phase)
        return None if load is None else float(reader(load))

    return ComparisonMetric(
        key=key,
        label=label,
        unit=unit,
        baseline=value(Phase.BASELINE),
        candidate=value(Phase.CANDIDATE),
        patched=value(Phase.PATCHED),
        direction=direction,
        caveat=caveat,
    )


def _fast_failure_caveat(loads: dict[Phase, PhaseLoad]) -> str | None:
    """Flag the case where a lower candidate P95 is produced by fast failures."""
    baseline = loads.get(Phase.BASELINE)
    candidate = loads.get(Phase.CANDIDATE)
    if baseline is None or candidate is None:
        return None
    if candidate.p95_ms >= baseline.p95_ms:
        return None
    if candidate.failure_rate < max(0.02, baseline.failure_rate + 0.01):
        return None
    return (
        f"Lower is not better here: {candidate.failure_rate * 100:.2f}% of candidate requests "
        "failed, and failed requests return faster than successful work."
    )


def _implied_concurrency(load: PhaseLoad) -> float:
    if load.duration_seconds <= 0:
        return 0.0
    return (load.request_count * (load.p50_ms / 1_000)) / load.duration_seconds


def _closed_loop_caveat(
    loads: dict[Phase, PhaseLoad], assessment: RegressionAssessment | None
) -> str | None:
    """Explain a throughput drop that only restates the latency change."""
    if assessment is None or not assessment.throughput_explained_by_latency:
        return None
    baseline = loads.get(Phase.BASELINE)
    if baseline is None:
        return None
    return (
        "The k6 plan is a closed-loop ramping-VUs schedule, so client concurrency stayed near "
        f"{_implied_concurrency(baseline):.1f} in-flight requests and throughput can only move "
        "inversely with latency. This drop restates the latency comparison instead of proving an "
        "independent throughput regression."
    )


def _comparison(
    loads: dict[Phase, PhaseLoad],
    evidence: dict[Phase, PhaseEvidence],
    assessment: RegressionAssessment | None = None,
) -> list[ComparisonMetric]:
    caveat = _fast_failure_caveat(loads)
    throughput_caveat = _closed_loop_caveat(loads, assessment)
    metrics = [
        _metric(
            "count", "Request count", "requests", "neutral", loads, lambda item: item.request_count
        ),
        _metric("p50", "P50 latency", "ms", "lower_is_better", loads, lambda item: item.p50_ms),
        _metric(
            "p95", "P95 latency", "ms", "lower_is_better", loads, lambda item: item.p95_ms, caveat
        ),
        _metric(
            "p99", "P99 latency", "ms", "lower_is_better", loads, lambda item: item.p99_ms, caveat
        ),
        _metric(
            "failure_rate",
            "Failure rate",
            "%",
            "lower_is_better",
            loads,
            lambda item: item.failure_rate * 100,
        ),
        _metric(
            "throughput",
            "Throughput",
            "req/s",
            "higher_is_better",
            loads,
            lambda item: item.throughput_rps,
            throughput_caveat,
        ),
        _metric(
            "concurrency",
            "Implied client concurrency",
            "in flight",
            "neutral",
            loads,
            _implied_concurrency,
        ),
        _metric(
            "checks_failed",
            "Checks failed",
            "checks",
            "lower_is_better",
            loads,
            lambda item: item.checks_failed,
        ),
    ]

    def evidence_metric(
        key: str, label: str, unit: str, reader: Any, direction: MetricDirection
    ) -> ComparisonMetric:
        def value(phase: Phase) -> float | None:
            item = evidence.get(phase)
            return None if item is None else float(reader(item))

        return ComparisonMetric(
            key=key,
            label=label,
            unit=unit,
            baseline=value(Phase.BASELINE),
            candidate=value(Phase.CANDIDATE),
            patched=value(Phase.PATCHED),
            direction=direction,
        )

    metrics.extend(
        [
            evidence_metric(
                "spans", "Correlated spans", "spans", lambda item: item.spans_in_window, "neutral"
            ),
            evidence_metric(
                "error_spans",
                "Error spans",
                "spans",
                lambda item: item.error_spans_in_window,
                "lower_is_better",
            ),
            evidence_metric(
                "lock_errors",
                "Lock-error logs",
                "logs",
                lambda item: item.lock_error_logs_in_window,
                "lower_is_better",
            ),
        ]
    )
    return metrics


def _interpretation(
    run: TraceForgeRun, loads: dict[Phase, PhaseLoad], evidence: dict[Phase, PhaseEvidence]
) -> list[str]:
    notes: list[str] = []
    baseline = loads.get(Phase.BASELINE)
    candidate = loads.get(Phase.CANDIDATE)
    patched = loads.get(Phase.PATCHED)
    if baseline and candidate:
        if candidate.p95_ms < baseline.p95_ms and candidate.failure_rate >= max(
            0.02, baseline.failure_rate + 0.01
        ):
            notes.append(
                f"The candidate P95 of {candidate.p95_ms:.2f} ms is lower than the baseline "
                f"{baseline.p95_ms:.2f} ms, but that is not an improvement: "
                f"{candidate.failure_rate * 100:.2f}% of candidate requests failed and failed "
                "requests return quickly. The decisive regression signal is the failure rate, "
                "not latency."
            )
        if candidate.throughput_rps > baseline.throughput_rps and candidate.failure_rate >= max(
            0.02, baseline.failure_rate + 0.01
        ):
            notes.append(
                f"Candidate throughput rose to {candidate.throughput_rps:.2f} req/s while "
                f"{candidate.checks_failed} checks failed, so the extra requests per second are "
                "mostly fast failures rather than completed work."
            )
    candidate_evidence = evidence.get(Phase.CANDIDATE)
    if candidate_evidence and candidate_evidence.lock_error_logs_in_window:
        notes.append(
            f"{candidate_evidence.lock_error_logs_in_window} of "
            f"{candidate_evidence.logs_in_window} retrieved candidate log records inside the exact "
            f"experiment window report '{LOCK_ERROR_MARKER}', and "
            f"{candidate_evidence.error_spans_in_window} of "
            f"{candidate_evidence.spans_in_window} correlated spans carry an error status."
        )
    assessment = run.assessment
    if assessment and assessment.throughput_explained_by_latency and baseline and candidate:
        notes.append(
            f"Throughput fell from {baseline.throughput_rps:.2f} to "
            f"{candidate.throughput_rps:.2f} req/s, but implied client concurrency held at "
            f"{_implied_concurrency(baseline):.1f} versus {_implied_concurrency(candidate):.1f} "
            "in-flight requests. In a closed-loop load plan that makes the rate a function of "
            "latency, so it is not counted as an independent regression."
        )
    if assessment and assessment.latency_slope_ms_per_window is not None:
        notes.append(
            "Candidate P95 moved "
            f"{assessment.latency_slope_ms_per_window:+.2f} ms per ordered load window, which is "
            "how TraceForge separates a rising trend from a single slow sample."
        )
    if patched and candidate:
        notes.append(
            f"The patched rerun used the identical load script and returned the failure rate to "
            f"{patched.failure_rate * 100:.2f}% with a P95 of {patched.p95_ms:.2f} ms, compared "
            f"with {candidate.failure_rate * 100:.2f}% for the candidate."
        )
    return notes


def _limitations(evidence: dict[Phase, PhaseEvidence]) -> list[str]:
    limitations: list[str] = []
    if not evidence:
        return limitations
    if any(item.row_limit_reached for item in evidence.values()):
        limitations.append(
            f"Trace and log retrieval is capped at {EVIDENCE_ROW_LIMIT} rows per phase, so span "
            "and log counts describe the retrieved sample, not all server traffic."
        )
    if all(item.metric_series == 0 for item in evidence.values()):
        limitations.append(
            "The custom metric series returned no points through MCP for this run, so latency "
            "evidence comes from spans and k6 rather than from a metric panel."
        )
    limitations.append(
        "SigNoz queries add a small margin around each phase to allow for ingestion delay. Counts "
        "shown here are re-attributed to the exact phase window, so they can be lower than the "
        "number of rows the query returned."
    )
    return limitations


def _timeline(ledger: AuditLedger) -> tuple[list[TimelineEvent], str | None]:
    try:
        events = ledger.events()
    except (ValueError, OSError):
        return [], None
    if not events:
        return [], None
    start = events[0].timestamp
    timeline = [
        TimelineEvent(
            sequence=event.sequence,
            action=event.action,
            previous_state=event.previous_state,
            next_state=event.next_state,
            occurred_at=event.timestamp,
            outcome=event.outcome,
            elapsed_seconds=round((event.timestamp - start).total_seconds(), 3),
            event_hash_prefix=event.event_hash[:12],
        )
        for event in events
    ]
    return timeline, events[-1].event_hash[:12]


def build_release_proof(run: TraceForgeRun, ledger: AuditLedger) -> ReleaseProof:
    loads = {phase: _phase_load(result) for phase, result in run.experiments.items()}
    evidence: dict[Phase, PhaseEvidence] = {}
    for phase, item in run.telemetry.items():
        result = run.experiments.get(phase)
        window = result.window if result else item.window
        evidence[phase] = _phase_evidence(phase, item, window)
    phases = [
        PhaseProof(phase=phase, load=loads.get(phase), evidence=evidence.get(phase))
        for phase in (Phase.BASELINE, Phase.CANDIDATE, Phase.PATCHED)
        if phase in loads or phase in evidence
    ]
    timeline, head_hash = _timeline(ledger)
    verification = ledger.verify(require_terminal=run.terminal_state is not None)
    service = next((item.service_name for item in run.telemetry.values()), None)
    return ReleaseProof(
        run_id=run.run_id,
        generated_at=utc_now(),
        stage=run.stage.value,
        terminal_state=run.terminal_state.value if run.terminal_state else None,
        verdict=run.verdict.value.value if run.verdict else None,
        verdict_reason=run.verdict.reason if run.verdict else None,
        repository=str(run.target.path),
        base_ref=run.target.base_ref,
        candidate_ref=run.target.candidate_ref,
        base_sha=run.change_set.base.sha if run.change_set else None,
        candidate_sha=run.change_set.candidate.sha if run.change_set else None,
        merge_base_sha=run.change_set.merge_base_sha if run.change_set else None,
        endpoint=(
            f"{run.load_plan.endpoint.method} {run.load_plan.endpoint.path}"
            if run.load_plan
            else None
        ),
        profile=run.target.profile.value,
        scenario=run.load_plan.scenario_name if run.load_plan else None,
        created_at=run.created_at,
        updated_at=run.updated_at,
        elapsed_seconds=round((run.updated_at - run.created_at).total_seconds(), 3),
        evidence_status=_evidence_status(run),
        classification=run.assessment.classification.value if run.assessment else None,
        patch_verification_status=run.verification.status.value if run.verification else None,
        patch_audit_passed=run.patch_audit.passed if run.patch_audit else None,
        patch_changed_files=list(run.patch.changed_files) if run.patch else [],
        phases=phases,
        comparison=_comparison(loads, evidence, run.assessment),
        interpretation=_interpretation(run, loads, evidence),
        timeline=timeline,
        ledger=LedgerStatus(
            recorded=bool(timeline),
            valid=verification.valid,
            event_count=verification.event_count,
            terminal_state=verification.terminal_state,
            terminal_required=run.terminal_state is not None,
            head_hash_prefix=head_hash,
            errors=list(verification.errors),
        ),
        signoz_service=service,
        limitations=_limitations(evidence),
    )
