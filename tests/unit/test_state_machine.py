import pytest

from traceforge.models import Stage, TerminalState
from traceforge.state_machine import IllegalTransition, StateMachine, is_legal


def test_ordered_transition_is_legal() -> None:
    machine = StateMachine()
    result = machine.transition("evt-1", Stage.REPOSITORY_VALIDATED)
    assert result.applied
    assert result.previous == Stage.CREATED
    assert machine.state == Stage.REPOSITORY_VALIDATED


def test_transition_is_idempotent_by_event_id() -> None:
    machine = StateMachine()
    machine.transition("evt-1", Stage.REPOSITORY_VALIDATED)
    replay = machine.transition("evt-1", Stage.REPOSITORY_VALIDATED)
    assert not replay.applied
    assert machine.state == Stage.REPOSITORY_VALIDATED


def test_event_id_cannot_be_reused_for_other_state() -> None:
    machine = StateMachine()
    machine.transition("evt-1", Stage.REPOSITORY_VALIDATED)
    with pytest.raises(IllegalTransition):
        machine.transition("evt-1", TerminalState.FAILED)


def test_illegal_transition_is_rejected() -> None:
    machine = StateMachine()
    with pytest.raises(IllegalTransition):
        machine.transition("evt-1", Stage.CHANGE_INSPECTED)


def test_missing_telemetry_can_publish_review_verdict() -> None:
    assert is_legal(Stage.CANDIDATE_COMPLETED, Stage.VERDICT_PUBLISHED)
    assert is_legal(Stage.VERDICT_PUBLISHED, TerminalState.NEEDS_REVIEW)


def test_ship_cannot_skip_verdict_stage() -> None:
    assert not is_legal(Stage.CANDIDATE_COMPLETED, TerminalState.PASSED)
