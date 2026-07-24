from datetime import UTC, datetime, timedelta
from pathlib import Path

from traceforge.models import (
    ExperimentWindow,
    K6RunResult,
    MetricStats,
    Phase,
    RegressionClassification,
    TelemetryEvidence,
    TraceEvidence,
)
from traceforge.regression import assess_regression, latency_slope


def result(
    phase: Phase,
    *,
    p95: float,
    failures: float,
    rate: float,
    windows: list[float] | None = None,
) -> K6RunResult:
    started = datetime.now(UTC)
    return K6RunResult(
        phase=phase,
        window=ExperimentWindow(
            phase=phase,
            started_at=started,
            ended_at=started + timedelta(seconds=10),
        ),
        exit_code=0,
        stats=MetricStats(
            count=200,
            rate=rate,
            p50_ms=p95 / 2,
            p90_ms=p95 * 0.8,
            p95_ms=p95,
            p99_ms=p95 * 1.5,
            failure_rate=failures,
            checks_passed=200,
            checks_failed=0,
            duration_seconds=10,
            ordered_p95_windows_ms=windows or [],
        ),
        summary_path=Path("summary.json"),
        raw_output_path=Path("output.log"),
        script_digest="abc",
        successful=True,
    )


def evidence(phase: Phase) -> TelemetryEvidence:
    now = datetime.now(UTC)
    return TelemetryEvidence(
        run_id="run",
        service_name="service",
        endpoint="/api/items",
        window=ExperimentWindow(
            phase=phase,
            started_at=now,
            ended_at=now + timedelta(seconds=10),
        ),
        available=True,
        traces=[
            TraceEvidence(
                trace_id="a" * 32,
                operation="POST /api/items",
                duration_ms=100,
                status="ok",
            )
        ],
    )


def test_latency_slope_uses_linear_regression() -> None:
    assert latency_slope([10, 20, 30, 40]) == 10
    assert latency_slope([10, 20]) is None


def test_missing_signoz_forces_insufficient_evidence() -> None:
    assessment = assess_regression(
        result(Phase.BASELINE, p95=100, failures=0, rate=20),
        result(Phase.CANDIDATE, p95=300, failures=0, rate=20),
    )
    assert assessment.classification == RegressionClassification.INSUFFICIENT_EVIDENCE
    assert not assessment.sufficient_evidence


def test_silent_degradation_requires_latency_slope_and_low_errors() -> None:
    assessment = assess_regression(
        result(Phase.BASELINE, p95=100, failures=0, rate=20),
        result(
            Phase.CANDIDATE,
            p95=300,
            failures=0,
            rate=20,
            windows=[100, 130, 170, 220],
        ),
        candidate_evidence=evidence(Phase.CANDIDATE),
    )
    assert assessment.classification == RegressionClassification.SILENT_DEGRADATION


def test_no_regression_control() -> None:
    assessment = assess_regression(
        result(Phase.BASELINE, p95=100, failures=0, rate=20),
        result(Phase.CANDIDATE, p95=105, failures=0, rate=21),
        candidate_evidence=evidence(Phase.CANDIDATE),
    )
    assert assessment.classification == RegressionClassification.NO_REGRESSION
