from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from traceforge.ledger import AuditLedger
from traceforge.models import (
    ExperimentWindow,
    K6RunResult,
    LogEvidence,
    MetricStats,
    Phase,
    Profile,
    RepositoryTarget,
    Stage,
    TelemetryEvidence,
    TerminalState,
    TraceEvidence,
    TraceForgeRun,
)
from traceforge.release_proof import build_release_proof
from traceforge.signoz import EVIDENCE_ROW_LIMIT

START = datetime(2026, 7, 24, 18, 57, 5, tzinfo=UTC)


def window(phase: Phase, *, offset: int = 0) -> ExperimentWindow:
    started = START + timedelta(seconds=offset)
    return ExperimentWindow(
        phase=phase, started_at=started, ended_at=started + timedelta(seconds=60)
    )


def load_result(
    phase: Phase, *, p95: float, failure_rate: float, rate: float, offset: int = 0
) -> K6RunResult:
    return K6RunResult(
        phase=phase,
        window=window(phase, offset=offset),
        exit_code=0 if failure_rate < 0.5 else 99,
        stats=MetricStats(
            count=6000,
            rate=rate,
            p50_ms=p95 / 4,
            p90_ms=p95 * 0.8,
            p95_ms=p95,
            p99_ms=p95 * 1.2,
            failure_rate=failure_rate,
            checks_passed=6000,
            checks_failed=0 if failure_rate < 0.5 else 6000,
            duration_seconds=60,
            ordered_p95_windows_ms=[10, 20, 30],
        ),
        summary_path=Path("summary.json"),
        raw_output_path=Path("output.log"),
        script_digest="digest",
        successful=failure_rate < 0.5,
    )


def span(*, seconds_into_window: float, error: bool, offset: int = 0) -> TraceEvidence:
    moment = START + timedelta(seconds=offset + seconds_into_window)
    return TraceEvidence(
        trace_id="a" * 32,
        span_id="b" * 16,
        operation="POST /api/visits",
        duration_ms=120,
        status="Error" if error else "Unset",
        attributes={
            "timestamp": moment.isoformat(),
            "has_error": error,
            "response_status_code": "500" if error else "201",
            "webUrl": "https://example.signoz.cloud/trace/" + "a" * 32,
        },
    )


def log_record(*, phase: str, lock: bool, seconds_into_window: float = 5) -> LogEvidence:
    attributes: dict[str, Any] = {"traceforge.phase": phase}
    if lock:
        attributes["exception.message"] = "database is locked"
    return LogEvidence(
        timestamp=START + timedelta(seconds=seconds_into_window),
        body='{"message":"request failed"}' if lock else '{"event":"request.complete"}',
        severity="ERROR" if lock else "INFO",
        trace_id="a" * 32,
        attributes={"attributes_string": attributes},
    )


def telemetry(
    phase: Phase,
    *,
    traces: list[TraceEvidence],
    logs: list[LogEvidence],
    offset: int = 0,
) -> TelemetryEvidence:
    return TelemetryEvidence(
        run_id="run",
        service_name="traceforge-demo-target",
        window=window(phase, offset=offset),
        endpoint="/api/visits",
        available=True,
        traces=traces,
        logs=logs,
    )


def lock_run() -> TraceForgeRun:
    baseline = load_result(Phase.BASELINE, p95=462.36, failure_rate=0.0016, rate=105.2)
    candidate = load_result(
        Phase.CANDIDATE, p95=329.02, failure_rate=0.9449, rate=117.32, offset=61
    )
    return TraceForgeRun(
        run_id="run",
        target=RepositoryTarget(
            path=Path("repo"),
            base_ref="demo-baseline",
            candidate_ref="demo-lock",
            target_url="http://127.0.0.1:8099",
            profile=Profile.DEMO,
        ),
        stage=Stage.VERDICT_PUBLISHED,
        terminal_state=TerminalState.PASSED,
        created_at=START,
        updated_at=START + timedelta(seconds=200),
        experiments={Phase.BASELINE: baseline, Phase.CANDIDATE: candidate},
        telemetry={
            Phase.BASELINE: telemetry(
                Phase.BASELINE,
                traces=[
                    span(seconds_into_window=10, error=False),
                    # Inside the query margin but after the baseline window closed.
                    span(seconds_into_window=65, error=True),
                ],
                logs=[log_record(phase="baseline", lock=False)],
            ),
            Phase.CANDIDATE: telemetry(
                Phase.CANDIDATE,
                traces=[span(seconds_into_window=10, error=True, offset=61)],
                logs=[
                    log_record(phase="candidate", lock=True, seconds_into_window=70),
                    log_record(phase="candidate", lock=False, seconds_into_window=75),
                ],
                offset=61,
            ),
        },
    )


def test_evidence_is_attributed_to_the_exact_phase_window(tmp_path: Path) -> None:
    proof = build_release_proof(lock_run(), AuditLedger(tmp_path / "run.jsonl", "run"))
    phases = {item.phase: item.evidence for item in proof.phases}
    baseline = phases[Phase.BASELINE]
    candidate = phases[Phase.CANDIDATE]
    assert baseline is not None and candidate is not None
    assert baseline.trace_rows_retrieved == 2
    assert baseline.spans_in_window == 1
    assert baseline.error_spans_in_window == 0
    assert candidate.error_spans_in_window == 1


def test_lock_errors_are_counted_from_exception_attributes(tmp_path: Path) -> None:
    proof = build_release_proof(lock_run(), AuditLedger(tmp_path / "run.jsonl", "run"))
    candidate = next(item.evidence for item in proof.phases if item.phase == Phase.CANDIDATE)
    assert candidate is not None
    assert candidate.logs_in_window == 2
    assert candidate.error_logs_in_window == 1
    assert candidate.lock_error_logs_in_window == 1
    assert candidate.log_samples[0].lock_error is True
    assert "database is locked" in candidate.log_samples[0].message


def test_lower_candidate_p95_with_fast_failures_is_flagged(tmp_path: Path) -> None:
    proof = build_release_proof(lock_run(), AuditLedger(tmp_path / "run.jsonl", "run"))
    p95 = next(item for item in proof.comparison if item.key == "p95")
    assert p95.caveat is not None
    assert "Lower is not better" in p95.caveat
    assert any(
        "decisive regression signal is the failure rate" in note for note in proof.interpretation
    )


def test_no_caveat_when_candidate_latency_rises(tmp_path: Path) -> None:
    run = lock_run()
    run.experiments[Phase.CANDIDATE] = load_result(
        Phase.CANDIDATE, p95=2383.58, failure_rate=0.0, rate=20.45, offset=61
    )
    proof = build_release_proof(run, AuditLedger(tmp_path / "run.jsonl", "run"))
    p95 = next(item for item in proof.comparison if item.key == "p95")
    assert p95.caveat is None


def test_row_limit_is_reported_when_retrieval_is_capped(tmp_path: Path) -> None:
    run = lock_run()
    evidence = run.telemetry[Phase.CANDIDATE]
    run.telemetry[Phase.CANDIDATE] = evidence.model_copy(
        update={
            "traces": [
                span(seconds_into_window=10, error=True, offset=61)
                for _ in range(EVIDENCE_ROW_LIMIT)
            ]
        }
    )
    proof = build_release_proof(run, AuditLedger(tmp_path / "run.jsonl", "run"))
    candidate = next(item.evidence for item in proof.phases if item.phase == Phase.CANDIDATE)
    assert candidate is not None
    assert candidate.row_limit_reached is True
    assert any(str(EVIDENCE_ROW_LIMIT) in note for note in proof.limitations)


def test_ledger_status_reflects_the_recorded_chain(tmp_path: Path) -> None:
    ledger = AuditLedger(tmp_path / "run.jsonl", "run")
    ledger.append(
        previous_state="CREATED",
        next_state="REPOSITORY_VALIDATED",
        action="repository.validate",
        actor_type="system",
        actor_name="traceforge-state-machine",
        input_value={"event": 1},
        output_value={"ok": True},
    )
    run = lock_run()
    run.terminal_state = None
    run.stage = Stage.REPOSITORY_VALIDATED
    proof = build_release_proof(run, ledger)
    assert proof.ledger.recorded is True
    assert proof.ledger.valid is True
    assert proof.ledger.terminal_required is False
    assert proof.ledger.event_count == 1
    assert len(proof.timeline) == 1
    assert proof.timeline[0].action == "repository.validate"


def test_tampered_ledger_fails_release_proof_verification(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    ledger = AuditLedger(path, "run")
    ledger.append(
        previous_state="CREATED",
        next_state="REPOSITORY_VALIDATED",
        action="repository.validate",
        actor_type="system",
        actor_name="traceforge-state-machine",
        input_value={"event": 1},
        output_value={"ok": True},
    )
    text = path.read_text(encoding="utf-8").replace("repository.validate", "repository.validaXe")
    path.write_text(text, encoding="utf-8", newline="\n")
    run = lock_run()
    run.terminal_state = None
    proof = build_release_proof(run, AuditLedger(path, "run"))
    assert proof.ledger.valid is False
    assert proof.ledger.errors
