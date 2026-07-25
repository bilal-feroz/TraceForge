from datetime import UTC, datetime, timedelta
from pathlib import Path

from traceforge.database import RunStore
from traceforge.models import (
    ExperimentWindow,
    Phase,
    Profile,
    RepositoryTarget,
    Stage,
    TelemetryEvidence,
    TerminalState,
    TraceForgeRun,
    Verdict,
    VerdictValue,
)

START = datetime(2026, 7, 25, 19, 22, 50, tzinfo=UTC)


def run(run_id: str, *, evidence: bool) -> TraceForgeRun:
    window = ExperimentWindow(
        phase=Phase.CANDIDATE, started_at=START, ended_at=START + timedelta(seconds=60)
    )
    return TraceForgeRun(
        run_id=run_id,
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
        telemetry={
            Phase.CANDIDATE: TelemetryEvidence(
                run_id=run_id,
                service_name="traceforge-demo-target",
                window=window,
                endpoint="/api/visits",
                available=evidence,
            )
        },
        verdict=Verdict(value=VerdictValue.SHIP, reason="verified improvement"),
    )


def test_summaries_project_only_list_fields(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "traceforge.sqlite3")
    store.save(run("first", evidence=True))
    store.save(run("second", evidence=False))

    summaries = store.list_summaries()

    assert [item["run_id"] for item in summaries] == ["first", "second"]
    first = summaries[0]
    assert first["stage"] == Stage.VERDICT_PUBLISHED.value
    assert first["terminal_state"] == TerminalState.PASSED.value
    assert first["verdict"] == VerdictValue.SHIP.value
    assert first["base_ref"] == "demo-baseline"
    assert first["candidate_ref"] == "demo-lock"
    assert first["telemetry"] == {"candidate": {"available": True}}
    assert summaries[1]["telemetry"] == {"candidate": {"available": False}}
    assert "experiments" not in first
    assert "k6_script" not in first


def test_summaries_match_the_full_list_for_shared_fields(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "traceforge.sqlite3")
    store.save(run("only", evidence=True))

    full = store.list()[0]
    summary = store.list_summaries()[0]

    assert summary["run_id"] == full.run_id
    assert summary["stage"] == full.stage.value
    assert full.verdict is not None
    assert summary["verdict"] == full.verdict.value.value
    assert summary["candidate_ref"] == full.target.candidate_ref
