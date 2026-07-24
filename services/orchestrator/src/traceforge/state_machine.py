from __future__ import annotations

from dataclasses import dataclass, field

from traceforge.models import Stage, TerminalState

State = Stage | TerminalState

_ORDERED_STAGES = list(Stage)
LEGAL_TRANSITIONS: dict[State, set[State]] = {
    stage: ({_ORDERED_STAGES[index + 1]} if index + 1 < len(_ORDERED_STAGES) else set())
    for index, stage in enumerate(_ORDERED_STAGES)
}
LEGAL_TRANSITIONS[Stage.VERDICT_PUBLISHED] = {
    TerminalState.PASSED,
    TerminalState.BLOCKED,
    TerminalState.NEEDS_REVIEW,
    TerminalState.FAILED,
    TerminalState.CANCELLED,
}
LEGAL_TRANSITIONS[Stage.CANDIDATE_COMPLETED] |= {Stage.VERDICT_PUBLISHED}
LEGAL_TRANSITIONS[Stage.REGRESSION_CLASSIFIED] |= {
    Stage.VERDICT_PUBLISHED,
    Stage.VERIFICATION_COMPLETED,
}
LEGAL_TRANSITIONS[Stage.PATCH_AUDITED] |= {Stage.VERDICT_PUBLISHED}
for stage in Stage:
    if stage != Stage.VERDICT_PUBLISHED:
        LEGAL_TRANSITIONS[stage] |= {TerminalState.FAILED, TerminalState.CANCELLED}
for terminal in TerminalState:
    LEGAL_TRANSITIONS[terminal] = set()


class IllegalTransition(ValueError):
    pass


def parse_state(value: str) -> State:
    try:
        return Stage(value)
    except ValueError:
        return TerminalState(value)


def is_legal(previous: State, next_state: State) -> bool:
    return next_state in LEGAL_TRANSITIONS[previous]


@dataclass(slots=True)
class TransitionResult:
    previous: State
    current: State
    applied: bool


@dataclass(slots=True)
class StateMachine:
    state: State = Stage.CREATED
    processed_events: dict[str, State] = field(default_factory=dict)

    def transition(self, event_id: str, next_state: State) -> TransitionResult:
        if event_id in self.processed_events:
            replayed_state = self.processed_events[event_id]
            if replayed_state != next_state:
                raise IllegalTransition(
                    f"event {event_id!r} was already used for {replayed_state.value}"
                )
            return TransitionResult(previous=self.state, current=self.state, applied=False)
        if not is_legal(self.state, next_state):
            raise IllegalTransition(f"illegal transition: {self.state.value} -> {next_state.value}")
        previous = self.state
        self.state = next_state
        self.processed_events[event_id] = next_state
        return TransitionResult(previous=previous, current=next_state, applied=True)
