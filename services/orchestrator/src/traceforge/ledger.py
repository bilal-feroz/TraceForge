from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from traceforge.models import LedgerEvent, TerminalState, utc_now
from traceforge.state_machine import is_legal, parse_state

GENESIS_HASH = "0" * 64


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def calculate_event_hash(previous_hash: str, event_without_hash: dict[str, Any]) -> str:
    payload = previous_hash + canonical_json(event_without_hash)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LedgerVerification:
    valid: bool
    event_count: int
    terminal_state: str | None
    errors: list[str]


class AuditLedger:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_dicts(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at ledger line {number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"ledger line {number} is not an object")
            records.append(item)
        return records

    def append(
        self,
        *,
        previous_state: str,
        next_state: str,
        action: str,
        actor_type: str,
        actor_name: str,
        input_value: Any,
        output_value: Any,
        evidence_ids: list[str] | None = None,
        tool_name: str | None = None,
        outcome: str = "success",
        error: str | None = None,
        timestamp: datetime | None = None,
    ) -> LedgerEvent:
        records = self._read_dicts()
        sequence = len(records) + 1
        previous_hash = records[-1]["event_hash"] if records else GENESIS_HASH
        event_without_hash: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "sequence": sequence,
            "timestamp": (timestamp or utc_now()).isoformat(),
            "previous_state": previous_state,
            "next_state": next_state,
            "action": action,
            "actor_type": actor_type,
            "actor_name": actor_name,
            "tool_name": tool_name,
            "input_digest": digest(input_value),
            "output_digest": digest(output_value),
            "evidence_ids": sorted(evidence_ids or []),
            "previous_hash": previous_hash,
            "outcome": outcome,
            "error": error,
        }
        event_hash = calculate_event_hash(previous_hash, event_without_hash)
        record = {**event_without_hash, "event_hash": event_hash}
        event = LedgerEvent.model_validate(record)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")
            handle.flush()
        return event

    def events(self) -> list[LedgerEvent]:
        return [LedgerEvent.model_validate(item) for item in self._read_dicts()]

    def verify(self, *, require_terminal: bool = True) -> LedgerVerification:
        errors: list[str] = []
        try:
            records = self._read_dicts()
        except ValueError as exc:
            return LedgerVerification(False, 0, None, [str(exc)])
        previous_hash = GENESIS_HASH
        previous_next_state: str | None = None
        terminal: str | None = None
        for index, record in enumerate(records, start=1):
            try:
                event = LedgerEvent.model_validate(record)
            except Exception as exc:
                errors.append(f"event {index}: schema invalid: {exc}")
                continue
            if event.run_id != self.run_id:
                errors.append(f"event {index}: wrong run ID")
            if event.sequence != index:
                errors.append(f"event {index}: sequence is {event.sequence}")
            if event.previous_hash != previous_hash:
                errors.append(f"event {index}: previous hash mismatch")
            if previous_next_state is not None and event.previous_state != previous_next_state:
                errors.append(f"event {index}: state continuity mismatch")
            without_hash = {key: value for key, value in record.items() if key != "event_hash"}
            expected = calculate_event_hash(event.previous_hash, without_hash)
            if event.event_hash != expected:
                errors.append(f"event {index}: event hash mismatch")
            try:
                previous = parse_state(event.previous_state)
                next_state = parse_state(event.next_state)
                if not is_legal(previous, next_state):
                    errors.append(
                        f"event {index}: illegal transition "
                        f"{event.previous_state} -> {event.next_state}"
                    )
                if isinstance(next_state, TerminalState):
                    terminal = next_state.value
            except ValueError:
                errors.append(f"event {index}: unknown state")
            previous_hash = event.event_hash
            previous_next_state = event.next_state
        if require_terminal and terminal is None:
            errors.append("ledger has no terminal status")
        return LedgerVerification(not errors, len(records), terminal, errors)
